import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import reflex as rx
import websockets

try:
    from login import BaseState
except ImportError:
    from .login import BaseState

from funcs import conectar_db, init_db



MAX_PUNTOS_GRAFICA = 250


@dataclass(frozen=True)
class ConfigMetrica:
    clave_ui: str
    sufijo_sensor: str
    nombre: str
    nombre_corto: str
    unidad: str
    unidad_kpi: str
    icono: str
    color_icono: str
    col_min: str
    col_max: str
    default_min: float
    default_max: float


METRICAS_CONFIG: tuple[ConfigMetrica, ...] = (
    ConfigMetrica(
        clave_ui="temperaturaAmb",
        sufijo_sensor="temp_amb",
        nombre="Tª Ambiente",
        nombre_corto="Tª Ambiente",
        unidad="ºC",
        unidad_kpi="ºC",
        icono="thermometer",
        color_icono="#66cdaa",
        col_min="temp_amb_min",
        col_max="temp_amb_max",
        default_min=15.0,
        default_max=32.0,
    ),
    ConfigMetrica(
        clave_ui="temperaturaSuelo",
        sufijo_sensor="temp_suelo",
        nombre="Tª Suelo",
        nombre_corto="Tª Suelo",
        unidad="ºC",
        unidad_kpi="ºC",
        icono="sprout",
        color_icono="#66cdaa",
        col_min="temp_suelo_min",
        col_max="temp_suelo_max",
        default_min=12.0,
        default_max=28.0,
    ),
    ConfigMetrica(
        clave_ui="humedadSuelo",
        sufijo_sensor="humedad",
        nombre="Humedad Suelo",
        nombre_corto="Humedad",
        unidad="%",
        unidad_kpi="%",
        icono="droplets",
        color_icono="#4dd0e1",
        col_min="humedad_min",
        col_max="humedad_max",
        default_min=40.0,
        default_max=85.0,
    ),
    ConfigMetrica(
        clave_ui="luminosidad",
        sufijo_sensor="lux",
        nombre="Luminosidad",
        nombre_corto="Luminosidad",
        unidad="Lux",
        unidad_kpi="lx",
        icono="sun",
        color_icono="#ffd54f",
        col_min="lux_min",
        col_max="lux_max",
        default_min=200.0,
        default_max=50000.0,
    ),
    ConfigMetrica(
        clave_ui="ph",
        sufijo_sensor="ph",
        nombre="pH Suelo",
        nombre_corto="pH Suelo",
        unidad="pH",
        unidad_kpi="pH",
        icono="flask-conical",
        color_icono="#b39ddb",
        col_min="ph_min",
        col_max="ph_max",
        default_min=5.5,
        default_max=7.5,
    ),
)

METRICAS_POR_UI: dict[str, ConfigMetrica] = {m.clave_ui: m for m in METRICAS_CONFIG}
METRICAS_POR_SUFIJO: dict[str, ConfigMetrica] = {m.sufijo_sensor: m for m in METRICAS_CONFIG}
RANGOS_DEFECTO_PARCELA: dict[str, tuple[float, float]] = {
    m.sufijo_sensor: (m.default_min, m.default_max) for m in METRICAS_CONFIG
}

PARCELAS_DEFECTO: list[tuple[int, str, str]] = [
    (1, "Parcela Norte", "Sector A"),
    (2, "Parcela Sur", "Sector B"),
    (3, "Invernadero Principal", "Sector C"),
    (4, "Viñedo Este", "Sector D"),
    (5, "Huerto Central", "Sector E"),
]

MAPA_PARCELAS_DEFECTO: dict[str, int] = {
    nombre: pid for pid, nombre, _ in PARCELAS_DEFECTO
}

def _script_ajuste_zoom(reset_scroll: bool) -> str:
    if reset_scroll:
        return """
            const el = document.getElementById('scroll-grafica');
            if (el) { el.scrollLeft = 0; }
            window.dispatchEvent(new Event('resize'));
            requestAnimationFrame(() => {
                const el2 = document.getElementById('scroll-grafica');
                if (el2) { el2.scrollLeft = 0; }
            });
        """
    return """
        const el = document.getElementById('scroll-grafica');
        if (el) {
            const maxScroll = Math.max(0, el.scrollWidth - el.clientWidth);
            if (el.scrollLeft > maxScroll) { el.scrollLeft = maxScroll; }
        }
        window.dispatchEvent(new Event('resize'));
    """


def _formatear_etiqueta_tiempo(timestamp_raw: Any, mismo_dia: bool) -> str:
    fecha = str(timestamp_raw) if timestamp_raw else ""
    if len(fecha) < 19:
        return fecha
    if mismo_dia:
        return fecha[11:19]
    return f"{fecha[8:10]}/{fecha[5:7]} {fecha[11:16]}"


def _reducir_puntos_grafica(
    puntos: list[dict[str, Any]], max_puntos: int = MAX_PUNTOS_GRAFICA
) -> list[dict[str, Any]]:
    """Reduce puntos enviados al navegador conservando extremos y errores."""
    total = len(puntos)
    if total <= max_puntos:
        return puntos

    indices_clave: set[int] = {0, total - 1}
    for i, punto in enumerate(puntos):
        if "Error" in punto:
            indices_clave.add(i)

    restantes = max(10, max_puntos - len(indices_clave))
    num_tramos = max(1, restantes // 2)
    tam_tramo = total / num_tramos

    for tramo in range(num_tramos):
        inicio = int(tramo * tam_tramo)
        fin = min(total, int((tramo + 1) * tam_tramo))
        if inicio < fin:
            indices_clave.add(min(range(inicio, fin), key=lambda i: puntos[i]["Valor"]))
            indices_clave.add(max(range(inicio, fin), key=lambda i: puntos[i]["Valor"]))

    return [puntos[i] for i in sorted(indices_clave)]


# ==============================================================================
# 2. ESTADO DEL PANEL Y OBTENCIÓN DINÁMICA DE DATOS
# ==============================================================================

class EstadoAgrotech(BaseState):
    _token_streaming: int = 0
    _ultimo_id_sensor: int = -1
    _firma_rangos_bd: str = ""
    _firma_grafica: str = ""

    parcelas_resumen: list[list[str]] = []
    sensores_parcela: list[list[str]] = []
    lecturas: list[list[str]] = []
    alertas_recientes_lista: list[list[str]] = []

    mapa_parcelas: dict[str, int] = dict(MAPA_PARCELAS_DEFECTO)
    opciones_parcelas: list[str] = list(MAPA_PARCELAS_DEFECTO.keys())
    rangos_parcelas_cache: dict[int, dict[str, list[float]]] = {}

    rol_usuario: str = ""
    parcela_seleccionada: str = "Parcela Norte"

    # Valores y estados para las tarjetas KPI superiores
    temp_amb_val: str = "--"
    temp_amb_estado: str = "Sin datos"
    temp_amb_critico: bool = False

    temp_suelo_val: str = "--"
    temp_suelo_estado: str = "Sin datos"
    temp_suelo_critico: bool = False

    humedad_val: str = "--"
    humedad_estado: str = "Sin datos"
    humedad_critico: bool = False

    lux_val: str = "--"
    lux_estado: str = "Sin datos"
    lux_critico: bool = False

    ph_val: str = "--"
    ph_estado: str = "Sin datos"
    ph_critico: bool = False

    es_parcela_critica: bool = False
    parcelas_criticas_global: list[str] = []

    # Variables de estado de la gráfica
    datos_grafica: list[dict[str, Any]] = []
    grafica_tipo: str = "temperaturaAmb"
    grafica_fecha_inicio: str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    grafica_fecha_fin: str = datetime.now().strftime("%Y-%m-%d")
    valor_medio: str = "0.0"
    grafica_rango_min: str = "15.0"
    grafica_rango_max: str = "32.0"
    grafica_unidad: str = "ºC"
    grafica_nombre_metrica: str = "Tª Ambiente"
    grafica_tiene_excesos: bool = False
    grafica_resumen_excesos: str = ""
    zoom_grafica: int = 100

    @rx.var
    def ancho_grafica(self) -> str:
        return f"{self.zoom_grafica}%"

    @rx.var
    def puede_gestionar_parcelas(self) -> bool:
        return self.rol_usuario in ("administrador", "tecnico_agricola")

    # --------------------------------------------------------------------------
    # Acciones de interfaz
    # --------------------------------------------------------------------------

    def aumentar_zoom_grafica(self):
        if self.zoom_grafica < 400:
            self.zoom_grafica += 50
            return rx.call_script("window.dispatchEvent(new Event('resize'));")

    def reducir_zoom_grafica(self):
        if self.zoom_grafica > 100:
            self.zoom_grafica -= 50
            return rx.call_script(_script_ajuste_zoom(self.zoom_grafica <= 100))

    def set_parcela_seleccionada(self, valor: str):
        self.parcela_seleccionada = valor
        self._firma_grafica = ""
        self.obtener_datos()

    def set_grafica_tipo(self, valor: str):
        self.grafica_tipo = valor
        self._firma_grafica = ""
        self.actualizar_grafica()

    def set_grafica_fecha_inicio(self, valor: str):
        if valor and self.grafica_fecha_fin and valor > self.grafica_fecha_fin:
            self.grafica_fecha_inicio = self.grafica_fecha_fin
        else:
            self.grafica_fecha_inicio = valor
        self._firma_grafica = ""
        self.actualizar_grafica()

    def set_grafica_fecha_fin(self, valor: str):
        if valor and self.grafica_fecha_inicio and valor < self.grafica_fecha_inicio:
            self.grafica_fecha_fin = self.grafica_fecha_inicio
        else:
            self.grafica_fecha_fin = valor
        self._firma_grafica = ""
        self.actualizar_grafica()

    def comprobar_acceso(self):
        if self.usuario_actual == "":
            return rx.redirect("/")
        try:
            init_db()
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT role FROM users WHERE username = ?", (self.usuario_actual,))
                resultado = cursor.fetchone()
                self.rol_usuario = resultado[0] if resultado else "usuario"
        except sqlite3.Error:
            self.rol_usuario = "usuario"

        self.obtener_datos()
        return EstadoAgrotech.iniciar_streaming

    # --------------------------------------------------------------------------
    # Helpers internos de base de datos y procesamiento
    # --------------------------------------------------------------------------

    def _evaluar_estado_kpi(self, valor: float | None, v_min: float, v_max: float) -> tuple[str, bool]:
        if valor is None:
            return ("Sin lecturas", False)
        if valor > v_max:
            return (f"Crítico alto (> {v_max})", True)
        if valor < v_min:
            return (f"Crítico bajo (< {v_min})", True)
        return ("En rango óptimo", False)

    def _obtener_rango_metrica(
        self, cursor: sqlite3.Cursor, parcel_id: int, metrica: ConfigMetrica
    ) -> tuple[float, float]:
        cursor.execute(
            f"SELECT {metrica.col_min}, {metrica.col_max} FROM parcels WHERE id = ?",
            (parcel_id,),
        )
        fila_rango = cursor.fetchone()
        if fila_rango and fila_rango[0] is not None and fila_rango[1] is not None:
            return float(fila_rango[0]), float(fila_rango[1])

        cache_parcela = self.rangos_parcelas_cache.get(parcel_id, {})
        if metrica.sufijo_sensor in cache_parcela:
            r_min, r_max = cache_parcela[metrica.sufijo_sensor]
            return float(r_min), float(r_max)

        return metrica.default_min, metrica.default_max

    def _cargar_grafica_con_cursor(self, cursor: sqlite3.Cursor) -> None:
        p_id = self.mapa_parcelas.get(self.parcela_seleccionada, 1)
        metrica = METRICAS_POR_UI.get(self.grafica_tipo, METRICAS_CONFIG[0])
        s_suffix = metrica.sufijo_sensor
        target_sensor_id = f"p{p_id}_{s_suffix}"

        self.grafica_unidad = metrica.unidad
        self.grafica_nombre_metrica = metrica.nombre

        r_min_f, r_max_f = self._obtener_rango_metrica(cursor, p_id, metrica)
        self.grafica_rango_min = str(r_min_f)
        self.grafica_rango_max = str(r_max_f)

        condiciones = ["sensor_id = ?"]
        parametros: list[Any] = [target_sensor_id]

        if self.grafica_fecha_inicio:
            condiciones.append("substr(timestamp, 1, 10) >= ?")
            parametros.append(self.grafica_fecha_inicio)
        if self.grafica_fecha_fin:
            condiciones.append("substr(timestamp, 1, 10) <= ?")
            parametros.append(self.grafica_fecha_fin)

        cursor.execute(
            f"SELECT timestamp, value FROM sensor_data WHERE {' AND '.join(condiciones)} ORDER BY id ASC",
            tuple(parametros),
        )
        datos_raw = cursor.fetchall()

        ultimo_registro = datos_raw[-1] if datos_raw else ("", 0)
        nueva_firma = (
            f"{target_sensor_id}|{len(datos_raw)}|{ultimo_registro[0]}|{ultimo_registro[1]}"
            f"|{r_min_f}|{r_max_f}|{self.grafica_fecha_inicio}|{self.grafica_fecha_fin}"
        )
        if nueva_firma == self._firma_grafica:
            return
        self._firma_grafica = nueva_firma

        mismo_dia = bool(self.grafica_fecha_inicio) and self.grafica_fecha_inicio == self.grafica_fecha_fin
        grafica_formateada: list[dict[str, Any]] = []
        suma = 0.0
        total_sobre_max = 0
        total_bajo_min = 0

        for timestamp_raw, valor_raw in datos_raw:
            valor_g = float(valor_raw) if valor_raw is not None else 0.0
            suma += valor_g

            punto: dict[str, Any] = {
                "hora": _formatear_etiqueta_tiempo(timestamp_raw, mismo_dia),
                "Valor": valor_g,
            }
            if valor_g > r_max_f:
                total_sobre_max += 1
                punto["Error"] = valor_g
            elif valor_g < r_min_f:
                total_bajo_min += 1
                punto["Error"] = valor_g

            grafica_formateada.append(punto)

        self.datos_grafica = _reducir_puntos_grafica(grafica_formateada)
        self.valor_medio = str(round(suma / len(datos_raw), 2) if datos_raw else 0.0)

        total_excesos = total_sobre_max + total_bajo_min
        self.grafica_tiene_excesos = total_excesos > 0
        if total_excesos > 0:
            partes_aviso = []
            if total_sobre_max > 0:
                partes_aviso.append(f"{total_sobre_max} sobre máx. ({r_max_f} {self.grafica_unidad})")
            if total_bajo_min > 0:
                partes_aviso.append(f"{total_bajo_min} bajo mín. ({r_min_f} {self.grafica_unidad})")
            self.grafica_resumen_excesos = " · ".join(partes_aviso)
        else:
            self.grafica_resumen_excesos = ""

    def actualizar_grafica(self):
        try:
            init_db()
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                self._cargar_grafica_con_cursor(cursor)
        except sqlite3.Error as e:
            print(f"Error al actualizar gráfica: {e}")
            self.datos_grafica = []
            self.valor_medio = "0.0"
            self.grafica_tiene_excesos = False

    def _cargar_parcelas_y_rangos(
        self, cursor: sqlite3.Cursor
    ) -> tuple[list[tuple[Any, ...]], dict[int, dict[str, tuple[float, float]]]]:
        cursor.execute("""
            SELECT id, name, location,
                   COALESCE(temp_amb_min, 15.0), COALESCE(temp_amb_max, 32.0),
                   COALESCE(temp_suelo_min, 12.0), COALESCE(temp_suelo_max, 28.0),
                   COALESCE(ph_min, 5.5), COALESCE(ph_max, 7.5),
                   COALESCE(lux_min, 200.0), COALESCE(lux_max, 50000.0),
                   COALESCE(humedad_min, 40.0), COALESCE(humedad_max, 85.0)
            FROM parcels ORDER BY id ASC
        """)
        filas_parcelas = cursor.fetchall()

        if not filas_parcelas:
            filas_parcelas = [
                (pid, nombre, sector, 15.0, 32.0, 12.0, 28.0, 5.5, 7.5, 200.0, 50000.0, 40.0, 85.0)
                for pid, nombre, sector in PARCELAS_DEFECTO
            ]

        rangos_por_parcela: dict[int, dict[str, tuple[float, float]]] = {}
        cache_serializable: dict[int, dict[str, list[float]]] = {}
        nuevo_mapa: dict[str, int] = {}
        nuevas_opciones: list[str] = []

        for fila in filas_parcelas:
            pid = int(fila[0])
            nombre_p = str(fila[1])
            nuevo_mapa[nombre_p] = pid
            nuevas_opciones.append(nombre_p)

            rangos_parcela = {
                "temp_amb": (float(fila[3]), float(fila[4])),
                "temp_suelo": (float(fila[5]), float(fila[6])),
                "ph": (float(fila[7]), float(fila[8])),
                "lux": (float(fila[9]), float(fila[10])),
                "humedad": (float(fila[11]), float(fila[12])),
            }
            rangos_por_parcela[pid] = rangos_parcela
            cache_serializable[pid] = {k: [v[0], v[1]] for k, v in rangos_parcela.items()}

        self.mapa_parcelas = nuevo_mapa
        self.opciones_parcelas = nuevas_opciones
        self.rangos_parcelas_cache = cache_serializable

        if self.parcela_seleccionada not in self.mapa_parcelas and nuevas_opciones:
            self.parcela_seleccionada = nuevas_opciones[0]

        return filas_parcelas, rangos_por_parcela

    def _obtener_ultimas_lecturas(
        self, cursor: sqlite3.Cursor
    ) -> tuple[dict[str, float], dict[str, str]]:
        cursor.execute("""
            SELECT sensor_id, value, timestamp FROM sensor_data
            WHERE id IN (SELECT MAX(id) FROM sensor_data GROUP BY sensor_id)
        """)
        ultimos_valores: dict[str, float] = {}
        ultimos_ts: dict[str, str] = {}
        for sid, val, ts in cursor.fetchall():
            if val is not None:
                sid_str = str(sid)
                ultimos_valores[sid_str] = float(val)
                ultimos_ts[sid_str] = str(ts)[11:19] if ts and len(str(ts)) >= 19 else "--:--"
        return ultimos_valores, ultimos_ts

    def _actualizar_kpis(
        self,
        parcel_id: int,
        ultimos_valores: dict[str, float],
        rangos_activos: dict[str, tuple[float, float]],
    ) -> dict[str, float | None]:
        valores_parcela = {
            m.sufijo_sensor: ultimos_valores.get(f"p{parcel_id}_{m.sufijo_sensor}")
            for m in METRICAS_CONFIG
        }

        v_amb = valores_parcela["temp_amb"]
        v_suelo = valores_parcela["temp_suelo"]
        v_hum = valores_parcela["humedad"]
        v_lux = valores_parcela["lux"]
        v_ph = valores_parcela["ph"]

        self.temp_amb_val = f"{v_amb}" if v_amb is not None else "--"
        self.temp_suelo_val = f"{v_suelo}" if v_suelo is not None else "--"
        self.humedad_val = f"{v_hum}" if v_hum is not None else "--"
        self.lux_val = f"{v_lux}" if v_lux is not None else "--"
        self.ph_val = f"{v_ph}" if v_ph is not None else "--"

        self.temp_amb_estado, self.temp_amb_critico = self._evaluar_estado_kpi(v_amb, *rangos_activos["temp_amb"])
        self.temp_suelo_estado, self.temp_suelo_critico = self._evaluar_estado_kpi(v_suelo, *rangos_activos["temp_suelo"])
        self.humedad_estado, self.humedad_critico = self._evaluar_estado_kpi(v_hum, *rangos_activos["humedad"])
        self.lux_estado, self.lux_critico = self._evaluar_estado_kpi(v_lux, *rangos_activos["lux"])
        self.ph_estado, self.ph_critico = self._evaluar_estado_kpi(v_ph, *rangos_activos["ph"])

        self.es_parcela_critica = any((
            self.temp_amb_critico,
            self.temp_suelo_critico,
            self.humedad_critico,
            self.lux_critico,
            self.ph_critico,
        ))
        return valores_parcela

    def _construir_sensores_parcela(
        self,
        parcel_id: int,
        valores_parcela: dict[str, float | None],
        ultimos_ts: dict[str, str],
    ) -> None:
        lista_sensores: list[list[str]] = []
        for metrica in METRICAS_CONFIG:
            sid = f"p{parcel_id}_{metrica.sufijo_sensor}"
            val = valores_parcela[metrica.sufijo_sensor]
            hora = ultimos_ts.get(sid, "--:--")
            valor_txt = f"{val} {metrica.unidad}" if val is not None else "Sin datos"
            estado_conn = "Conectado" if val is not None else "Esperando"
            lista_sensores.append([metrica.nombre, f"{sid} · {hora}", valor_txt, estado_conn, metrica.icono])
        self.sensores_parcela = lista_sensores

    def _construir_resumen_y_alertas(
        self,
        filas_parcelas: list[tuple[Any, ...]],
        rangos_por_parcela: dict[int, dict[str, tuple[float, float]]],
        ultimos_valores: dict[str, float],
        ultimos_ts: dict[str, str],
    ) -> None:
        criticas_globales: list[str] = []
        alertas_items: list[list[str]] = []
        resumen_p: list[list[str]] = []

        for fila in filas_parcelas:
            pid = int(fila[0])
            nombre_p = str(fila[1])
            ubicacion_p = str(fila[2] or "Sector asignado")
            rangos_p = rangos_por_parcela.get(pid, {})
            tiene_alerta_p = False

            for tipo_s, (r_min, r_max) in rangos_p.items():
                sid_check = f"p{pid}_{tipo_s}"
                val_s = ultimos_valores.get(sid_check)
                if val_s is None:
                    continue

                metrica = METRICAS_POR_SUFIJO[tipo_s]
                hora_a = ultimos_ts.get(sid_check, "--:--")
                if val_s > r_max:
                    tiene_alerta_p = True
                    alertas_items.append([
                        f"{metrica.nombre_corto} alta en {nombre_p}",
                        f"Valor: {val_s} {metrica.unidad} (máx. {r_max} {metrica.unidad}) · {hora_a}",
                        nombre_p,
                    ])
                elif val_s < r_min:
                    tiene_alerta_p = True
                    alertas_items.append([
                        f"{metrica.nombre_corto} baja en {nombre_p}",
                        f"Valor: {val_s} {metrica.unidad} (mín. {r_min} {metrica.unidad}) · {hora_a}",
                        nombre_p,
                    ])

            if tiene_alerta_p:
                criticas_globales.append(nombre_p)

            hum_p = ultimos_valores.get(f"p{pid}_humedad")
            hum_txt = f"{hum_p} %" if hum_p is not None else "-- %"
            estado_txt = "Revisar alerta" if tiene_alerta_p else "Óptimo"
            estado_color = "red" if tiene_alerta_p else "grass"
            resumen_p.append([nombre_p, ubicacion_p, "5 sensores", hum_txt, estado_txt, estado_color])

        self.parcelas_criticas_global = criticas_globales
        self.alertas_recientes_lista = alertas_items
        self.parcelas_resumen = resumen_p

    def _cargar_historial_lecturas(
        self,
        cursor: sqlite3.Cursor,
        rangos_por_parcela: dict[int, dict[str, tuple[float, float]]],
    ) -> None:
        cursor.execute("""
            SELECT sensor_id, timestamp, value
            FROM sensor_data
            ORDER BY id DESC LIMIT 15
        """)
        datos_formateados: list[list[str]] = []

        for fila in cursor.fetchall():
            sensor = str(fila[0]) if fila[0] else "Desconocido"
            fecha_cruda = str(fila[1]) if fila[1] else ""
            fecha_limpia = fecha_cruda[:19].replace("T", " ") if len(fecha_cruda) >= 19 else fecha_cruda
            valor_real = float(fila[2]) if fila[2] is not None else 0.0

            color_texto = "#66cdaa"
            estado_txt = "En rango"
            estado_color = "grass"

            if sensor.startswith("p") and "_" in sensor:
                prefijo, tipo_sensor = sensor.split("_", 1)
                try:
                    pid_sensor = int(prefijo[1:])
                    r_parcela = rangos_por_parcela.get(pid_sensor, {})
                    if tipo_sensor in r_parcela:
                        r_min, r_max = r_parcela[tipo_sensor]
                        if valor_real > r_max:
                            color_texto = "#ff8da1"
                            estado_txt = f"Crítico alto (> {r_max})"
                            estado_color = "red"
                        elif valor_real < r_min:
                            color_texto = "#82b1ff"
                            estado_txt = f"Crítico bajo (< {r_min})"
                            estado_color = "red"
                except ValueError:
                    pass

            datos_formateados.append([sensor, fecha_limpia, str(valor_real), color_texto, estado_txt, estado_color])

        self.lecturas = datos_formateados

    def obtener_datos(self):
        try:
            init_db()
            with conectar_db() as conexion:
                cursor = conexion.cursor()

                filas_parcelas, rangos_por_parcela = self._cargar_parcelas_y_rangos(cursor)
                ultimos_valores, ultimos_ts = self._obtener_ultimas_lecturas(cursor)

                p_id = self.mapa_parcelas.get(self.parcela_seleccionada, 1)
                rangos_activos = rangos_por_parcela.get(p_id, RANGOS_DEFECTO_PARCELA)
                valores_parcela = self._actualizar_kpis(p_id, ultimos_valores, rangos_activos)

                self._construir_sensores_parcela(p_id, valores_parcela, ultimos_ts)
                self._construir_resumen_y_alertas(filas_parcelas, rangos_por_parcela, ultimos_valores, ultimos_ts)
                self._cargar_historial_lecturas(cursor, rangos_por_parcela)
                self._cargar_grafica_con_cursor(cursor)

        except sqlite3.Error as e:
            print(f"Error en la base de datos: {e}")

    # --------------------------------------------------------------------------
    # Streaming WebSocket y sondeo en segundo plano
    # --------------------------------------------------------------------------

    async def _escuchar_ws_parcela(self, pid: int, token: int):
        uri = f"ws://localhost:8001/ws/parcels/{pid}"
        while True:
            async with self:
                if self._token_streaming != token or self.usuario_actual == "":
                    return
            try:
                async with websockets.connect(uri) as websocket:
                    while True:
                        async with self:
                            if self._token_streaming != token or self.usuario_actual == "":
                                return
                        await websocket.recv()
                        async with self:
                            if self._token_streaming != token or self.usuario_actual == "":
                                return
                            self.obtener_datos()
            except asyncio.CancelledError:
                return
            except Exception:
                await asyncio.sleep(2.0)

    @rx.event(background=True)
    async def iniciar_streaming(self):
        async with self:
            self._token_streaming += 1
            mi_token = self._token_streaming

        tareas_ws: dict[int, asyncio.Task] = {}

        try:
            while True:
                async with self:
                    if self._token_streaming != mi_token or self.usuario_actual == "":
                        break
                    ids_parcelas = list(self.mapa_parcelas.values())

                for pid in ids_parcelas:
                    if pid not in tareas_ws or tareas_ws[pid].done():
                        tareas_ws[pid] = asyncio.create_task(self._escuchar_ws_parcela(pid, mi_token))

                try:
                    with conectar_db() as conexion:
                        cursor = conexion.cursor()
                        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM sensor_data")
                        fila_max = cursor.fetchone()
                        max_id_actual = int(fila_max[0]) if fila_max else 0

                        cursor.execute("""
                            SELECT id, name, temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                                   ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
                            FROM parcels ORDER BY id ASC
                        """)
                        firma_actual = str(cursor.fetchall())

                    async with self:
                        if self._token_streaming != mi_token:
                            break
                        if max_id_actual != self._ultimo_id_sensor or firma_actual != self._firma_rangos_bd:
                            self._ultimo_id_sensor = max_id_actual
                            self._firma_rangos_bd = firma_actual
                            self.obtener_datos()
                except sqlite3.Error:
                    pass

                await asyncio.sleep(1.5)
        finally:
            for tarea in tareas_ws.values():
                if not tarea.done():
                    tarea.cancel()