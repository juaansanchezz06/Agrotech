"""
MÓDULO PRINCIPAL DE LA APLICACIÓN AGROTECH (panel_web.py)
---------------------------------------------------------
Dashboard unificado en vista de cuadrícula (KPIs, Gráfica única con resaltado
de errores, Sensores, Mis Parcelas y Alertas Recientes) conservando la lógica
de BD actualizada, el botón oculto #btn-actualizar y la paleta Agrotech.
"""

import asyncio
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import reflex as rx
import websockets

try:
    from gestor_parcelas import GestorParcelasState, panel_gestor_parcelas
    from gestor_usuarios import GestorUsuariosState, panel_gestor_usuarios
    from login import BaseState, asegurar_bd_agrotech, login_page
except ImportError:
    from .gestor_parcelas import GestorParcelasState, panel_gestor_parcelas
    from .gestor_usuarios import GestorUsuariosState, panel_gestor_usuarios
    from .login import BaseState, asegurar_bd_agrotech, login_page


# ==============================================================================
# 1. CONFIGURACIÓN GLOBAL Y CONSTANTES DE MAPEO
# ==============================================================================

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_RAIZ = os.path.abspath(os.path.join(DIR_ACTUAL, "..", ".."))
RUTA_DB = os.path.join(RUTA_RAIZ, "agrotech.db")
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

ESTILOS_TEMA = """
<style>
    :root, .light, .light-theme {
        color-scheme: light;
        --gray-1: #F4F7F8 !important;
        --gray-2: #EBF0F2 !important;
        --gray-3: #E1E8EC !important;
        --gray-4: #D3DEE3 !important;
        --gray-5: #C5D4DC !important;
        --gray-11: #4A636E !important;
        --gray-12: #1A2E35 !important;
    }
    .dark, .dark-theme, [data-theme="dark"] {
        color-scheme: dark;
        --gray-1: #0D2F3A !important;
        --gray-2: #09242E !important;
        --gray-3: #123C4A !important;
        --gray-4: #174859 !important;
        --gray-5: #1D566B !important;
        --gray-6: #2A718B !important;
        --gray-11: #B8D4DF !important;
        --gray-12: #F0F8FA !important;
    }
</style>
"""

ESTILO_TARJETA_BASE: dict[str, Any] = {
    "padding": "1.5em",
    "border_radius": "16px",
    "background_color": "var(--gray-2)",
    "box_shadow": "0 2px 10px rgba(0, 0, 0, 0.03)",
    "width": "100%",
    "min_width": "0",
}


def _conectar_db() -> sqlite3.Connection:
    return sqlite3.connect(RUTA_DB, timeout=15.0)


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
            asegurar_bd_agrotech()
            with _conectar_db() as conexion:
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

    def _asegurar_columnas_parcelas(self, cursor: sqlite3.Cursor, conexion: sqlite3.Connection) -> None:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parcels'")
        if cursor.fetchone() is None:
            return

        cursor.execute("PRAGMA table_info(parcels)")
        existentes = {fila[1] for fila in cursor.fetchall()}

        columnas_necesarias = {
            col: f"REAL DEFAULT {default}"
            for m in METRICAS_CONFIG
            for col, default in ((m.col_min, m.default_min), (m.col_max, m.default_max))
        }

        modificado = False
        for col, definicion in columnas_necesarias.items():
            if col not in existentes:
                cursor.execute(f"ALTER TABLE parcels ADD COLUMN {col} {definicion}")
                modificado = True

        if modificado:
            conexion.commit()

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
            with _conectar_db() as conexion:
                cursor = conexion.cursor()
                self._asegurar_columnas_parcelas(cursor, conexion)
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
            asegurar_bd_agrotech()
            with _conectar_db() as conexion:
                cursor = conexion.cursor()
                self._asegurar_columnas_parcelas(cursor, conexion)

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
                    with _conectar_db() as conexion:
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


# ==============================================================================
# 3. COMPONENTES VISUALES DEL DASHBOARD
# ==============================================================================

def tarjeta_kpi_superior(
    titulo: str,
    valor: str,
    unidad: str,
    estado_txt: str,
    es_critico: bool,
    icono: str,
    color_icono: str,
    metrica_key: str,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(
                        tag=icono,
                        size=18,
                        color=rx.cond(es_critico, "var(--red-11)", color_icono),
                    ),
                    width="34px",
                    height="34px",
                    border_radius="10px",
                    background_color=rx.cond(es_critico, "var(--red-3)", "var(--gray-3)"),
                    border=rx.cond(es_critico, "1px solid var(--red-7)", "1px solid var(--gray-5)"),
                ),
                rx.text(titulo, size="2", weight="medium", color="var(--gray-11)"),
                rx.spacer(),
                rx.cond(
                    es_critico,
                    rx.icon("triangle-alert", size=16, color="var(--red-11)"),
                    rx.box(),
                ),
                align="center",
                width="100%",
                spacing="2",
            ),
            rx.hstack(
                rx.text(
                    valor,
                    size="7",
                    weight="bold",
                    color=rx.cond(es_critico, "var(--red-11)", "var(--gray-12)"),
                    line_height="1.1",
                ),
                rx.text(unidad, size="3", weight="medium", color="var(--gray-11)"),
                align="baseline",
                spacing="1",
                margin_y="0.25em",
            ),
            rx.text(
                estado_txt,
                size="1",
                weight="bold",
                color=rx.cond(es_critico, "var(--red-11)", "var(--grass-11)"),
            ),
            align="start",
            spacing="2",
            width="100%",
        ),
        on_click=lambda: EstadoAgrotech.set_grafica_tipo(metrica_key),
        cursor="pointer",
        padding="1.15em 1.25em",
        border_radius="16px",
        background_color="var(--gray-2)",
        border=rx.cond(
            es_critico,
            "1.5px solid var(--red-9)",
            rx.cond(
                EstadoAgrotech.grafica_tipo == metrica_key,
                "1.5px solid var(--grass-9)",
                "1px solid var(--gray-5)",
            ),
        ),
        box_shadow="0 2px 10px rgba(0, 0, 0, 0.03)",
        _hover={"border_color": "var(--grass-9)"},
        transition="all 0.15s ease",
        width="100%",
        min_width="0",
    )


def _tab_metrica_grafica(etiqueta: str, valor_key: str) -> rx.Component:
    activo = EstadoAgrotech.grafica_tipo == valor_key
    return rx.button(
        etiqueta,
        on_click=lambda: EstadoAgrotech.set_grafica_tipo(valor_key),
        size="1",
        variant=rx.cond(activo, "solid", "soft"),
        color_scheme=rx.cond(activo, "grass", "gray"),
        border_radius="8px",
        height="28px",
        padding_x="0.85em",
        display="inline-flex",
        align_items="center",
        justify_content="center",
        cursor="pointer",
        font_weight="600",
    )


def _controles_fecha_y_zoom() -> rx.Component:
    return rx.hstack(
        rx.input(
            type="date",
            value=EstadoAgrotech.grafica_fecha_inicio,
            max=EstadoAgrotech.grafica_fecha_fin,
            on_change=EstadoAgrotech.set_grafica_fecha_inicio,
            variant="soft",
            color_scheme="grass",
            size="1",
        ),
        rx.input(
            type="date",
            value=EstadoAgrotech.grafica_fecha_fin,
            min=EstadoAgrotech.grafica_fecha_inicio,
            on_change=EstadoAgrotech.set_grafica_fecha_fin,
            variant="soft",
            color_scheme="grass",
            size="1",
        ),
        rx.icon_button(
            rx.icon("minus", size=14),
            on_click=EstadoAgrotech.reducir_zoom_grafica,
            disabled=EstadoAgrotech.zoom_grafica <= 100,
            variant="soft",
            color_scheme="grass",
            size="1",
            cursor=rx.cond(EstadoAgrotech.zoom_grafica <= 100, "not-allowed", "pointer"),
            title="Desampliar gráfica",
        ),
        rx.text(
            EstadoAgrotech.ancho_grafica,
            size="1",
            weight="bold",
            color="var(--gray-12)",
            min_width="3em",
            text_align="center",
        ),
        rx.icon_button(
            rx.icon("plus", size=14),
            on_click=EstadoAgrotech.aumentar_zoom_grafica,
            disabled=EstadoAgrotech.zoom_grafica >= 400,
            variant="soft",
            color_scheme="grass",
            size="1",
            cursor=rx.cond(EstadoAgrotech.zoom_grafica >= 400, "not-allowed", "pointer"),
            title="Ampliar gráfica",
        ),
        wrap="wrap",
        align="center",
        spacing="2",
    )


def _lienzo_recharts() -> rx.Component:
    return rx.box(
        rx.box(
            rx.recharts.line_chart(
                rx.recharts.cartesian_grid(
                    stroke_dasharray="3 3",
                    stroke="var(--gray-5)",
                ),
                rx.recharts.line(
                    data_key="Valor",
                    stroke="#64B5F6",
                    stroke_width=3,
                    dot={"fill": "#64B5F6", "stroke": "var(--gray-12)", "strokeWidth": 1, "r": 3.5},
                    active_dot={"r": 6, "fill": "var(--grass-9)", "stroke": "var(--gray-12)"},
                ),
                rx.recharts.line(
                    data_key="Error",
                    stroke="none",
                    stroke_width=0,
                    connect_nulls=False,
                    dot={"fill": "#ff5252", "stroke": "#ffffff", "strokeWidth": 2, "r": 6.5},
                    active_dot={"r": 8, "fill": "#ff1744", "stroke": "#ffffff", "strokeWidth": 2},
                ),
                rx.recharts.reference_line(
                    y=EstadoAgrotech.valor_medio,
                    stroke="var(--grass-9)",
                    stroke_dasharray="4 4",
                    stroke_width=2,
                ),
                rx.recharts.reference_line(
                    y=EstadoAgrotech.grafica_rango_min,
                    stroke="#ff5252",
                    stroke_dasharray="5 5",
                    stroke_width=2,
                ),
                rx.recharts.reference_line(
                    y=EstadoAgrotech.grafica_rango_max,
                    stroke="#ff5252",
                    stroke_dasharray="5 5",
                    stroke_width=2,
                ),
                rx.recharts.x_axis(
                    data_key="hora",
                    stroke="var(--gray-6)",
                    tick={"fill": "var(--gray-12)", "fontSize": 12},
                ),
                rx.recharts.y_axis(
                    domain=["auto", "auto"],
                    stroke="var(--gray-6)",
                    tick={"fill": "var(--gray-12)", "fontSize": 12},
                ),
                rx.recharts.graphing_tooltip(
                    content_style={
                        "backgroundColor": "var(--gray-3)",
                        "borderColor": "var(--gray-5)",
                        "borderRadius": "10px",
                        "color": "var(--gray-12)",
                    },
                    label_style={"color": "var(--gray-12)", "fontWeight": "bold"},
                    item_style={"fontWeight": "bold"},
                ),
                data=EstadoAgrotech.datos_grafica,
                height=280,
                width="100%",
            ),
            width=EstadoAgrotech.ancho_grafica,
            min_width="100%",
            overflow="hidden",
        ),
        id="scroll-grafica",
        width="100%",
        min_width="0",
        overflow_x=rx.cond(EstadoAgrotech.zoom_grafica > 100, "auto", "hidden"),
        padding_bottom="0.5em",
    )


def tarjeta_evolucion_grafica() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Evolución de mediciones", size="4", weight="bold", color="var(--gray-12)"),
                    rx.text(
                        EstadoAgrotech.grafica_nombre_metrica,
                        " · ",
                        EstadoAgrotech.parcela_seleccionada,
                        size="2",
                        color="var(--gray-11)",
                    ),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                _controles_fecha_y_zoom(),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="3",
            ),
            rx.hstack(
                *[_tab_metrica_grafica(m.nombre, m.clave_ui) for m in METRICAS_CONFIG],
                padding="0.35em",
                border_radius="10px",
                background_color="var(--gray-3)",
                border="1px solid var(--gray-5)",
                align="center",
                wrap="wrap",
                spacing="2",
                width="100%",
            ),
            rx.cond(
                EstadoAgrotech.grafica_tiene_excesos,
                rx.callout.root(
                    rx.callout.icon(rx.icon("triangle-alert", size=16)),
                    rx.callout.text(
                        "Límite superado: ",
                        rx.text.span(EstadoAgrotech.grafica_resumen_excesos, weight="bold"),
                    ),
                    color_scheme="red",
                    variant="surface",
                    size="1",
                    width="100%",
                ),
            ),
            _lienzo_recharts(),
            rx.hstack(
                rx.hstack(
                    rx.box(width="8px", height="8px", border_radius="50%", background_color="#64B5F6"),
                    rx.text(EstadoAgrotech.grafica_nombre_metrica, size="1", color="var(--gray-11)"),
                    rx.text(
                        "· Media: ",
                        EstadoAgrotech.valor_medio,
                        " ",
                        EstadoAgrotech.grafica_unidad,
                        size="1",
                        weight="bold",
                        color="var(--gray-12)",
                    ),
                    rx.cond(
                        EstadoAgrotech.grafica_tiene_excesos,
                        rx.hstack(
                            rx.box(width="8px", height="8px", border_radius="50%", background_color="#ff5252"),
                            rx.text("Fuera de rango", size="1", weight="bold", color="var(--red-11)"),
                            align="center",
                            spacing="1",
                            margin_left="0.5em",
                        ),
                    ),
                    align="center",
                    spacing="2",
                    wrap="wrap",
                ),
                rx.spacer(),
                rx.text(
                    "Rango recomendado: ",
                    EstadoAgrotech.grafica_rango_min,
                    " – ",
                    EstadoAgrotech.grafica_rango_max,
                    " ",
                    EstadoAgrotech.grafica_unidad,
                    size="1",
                    weight="medium",
                    color=rx.cond(EstadoAgrotech.grafica_tiene_excesos, "var(--red-11)", "var(--gray-11)"),
                ),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="2",
            ),
            spacing="4",
            width="100%",
            min_width="0",
        ),
        border=rx.cond(
            EstadoAgrotech.grafica_tiene_excesos,
            "1.5px solid var(--red-8)",
            "1px solid var(--gray-5)",
        ),
        **ESTILO_TARJETA_BASE,
    )


def fila_sensor_panel(item: list[str]) -> rx.Component:
    return rx.hstack(
        rx.center(
            rx.icon(tag=item[4], size=18, color="var(--grass-11)"),
            width="38px",
            height="38px",
            border_radius="10px",
            background_color="var(--gray-3)",
            border="1px solid var(--gray-5)",
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(item[0], size="2", weight="bold", color="var(--gray-12)"),
            rx.text(item[1], size="1", color="var(--gray-11)"),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.vstack(
            rx.hstack(
                rx.box(
                    width="7px",
                    height="7px",
                    border_radius="50%",
                    background_color=rx.cond(item[3] == "Conectado", "var(--grass-9)", "var(--amber-9)"),
                ),
                rx.text(
                    item[3],
                    size="1",
                    weight="bold",
                    color=rx.cond(item[3] == "Conectado", "var(--grass-11)", "var(--gray-11)"),
                ),
                align="center",
                spacing="1",
            ),
            rx.text(item[2], size="1", weight="medium", color="var(--gray-12)"),
            spacing="0",
            align="end",
        ),
        width="100%",
        align="center",
        padding_y="0.65em",
        border_bottom="1px solid var(--gray-4)",
    )


def tarjeta_sensores_derecha() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Sensores", size="4", weight="bold", color="var(--gray-12)"),
                    rx.text("Dispositivos de ", EstadoAgrotech.parcela_seleccionada, size="2", color="var(--gray-11)"),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.badge("5 / 5 activos", color_scheme="grass", variant="soft", size="2"),
                width="100%",
                align="start",
            ),
            rx.vstack(
                rx.foreach(EstadoAgrotech.sensores_parcela, fila_sensor_panel),
                spacing="0",
                width="100%",
            ),
            rx.spacer(),
            rx.cond(
                EstadoAgrotech.puede_gestionar_parcelas,
                rx.hstack(
                    rx.link(
                        rx.hstack(
                            rx.text("Gestionar parcelas y rangos", size="2", weight="bold", color="var(--grass-11)"),
                            rx.icon("arrow-right", size=15, color="var(--grass-11)"),
                            align="center",
                            spacing="1",
                        ),
                        on_click=rx.redirect("/gestor-parcelas"),
                        cursor="pointer",
                    ),
                    width="100%",
                    padding_top="0.5em",
                ),
            ),
            spacing="3",
            height="100%",
            width="100%",
        ),
        border="1px solid var(--gray-5)",
        **ESTILO_TARJETA_BASE,
    )


def fila_mi_parcela(fila: list[str]) -> rx.Component:
    es_roja = fila[5] == "red"
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.center(
                    rx.icon(
                        "box",
                        size=16,
                        color=rx.cond(es_roja, "var(--red-11)", "var(--grass-11)"),
                    ),
                    width="32px",
                    height="32px",
                    border_radius="8px",
                    background_color=rx.cond(es_roja, "var(--red-3)", "var(--gray-3)"),
                    border=rx.cond(es_roja, "1px solid var(--red-7)", "1px solid var(--gray-5)"),
                ),
                rx.vstack(
                    rx.text(fila[0], size="2", weight="bold", color="var(--gray-12)"),
                    rx.text(fila[1], size="1", color="var(--gray-11)"),
                    spacing="0",
                    align="start",
                ),
                align="center",
                spacing="2",
            )
        ),
        rx.table.cell(rx.text(fila[2], size="2", color="var(--gray-11)")),
        rx.table.cell(rx.text(fila[3], size="2", weight="bold", color="var(--gray-12)")),
        rx.table.cell(rx.badge(fila[4], color_scheme=fila[5], variant="soft")),
        rx.table.cell(
            rx.icon_button(
                rx.icon("arrow-right", size=14),
                on_click=lambda: EstadoAgrotech.set_parcela_seleccionada(fila[0]),
                variant="ghost",
                color_scheme="gray",
                size="1",
                cursor="pointer",
                title="Seleccionar parcela",
            )
        ),
        on_click=lambda: EstadoAgrotech.set_parcela_seleccionada(fila[0]),
        cursor="pointer",
        _hover={"background_color": "var(--gray-3)"},
    )


def tarjeta_mis_parcelas() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Mis parcelas", size="4", weight="bold", color="var(--gray-12)"),
                    rx.text("Pulsa sobre una parcela para ver sus métricas y gráfica", size="2", color="var(--gray-11)"),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.cond(
                    EstadoAgrotech.puede_gestionar_parcelas,
                    rx.link(
                        rx.hstack(
                            rx.text("Ver todas", size="2", weight="bold", color="var(--grass-11)"),
                            rx.icon("arrow-right", size=15, color="var(--grass-11)"),
                            align="center",
                            spacing="1",
                        ),
                        on_click=rx.redirect("/gestor-parcelas"),
                        cursor="pointer",
                    ),
                ),
                width="100%",
                align="center",
            ),
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("PARCELA"),
                            rx.table.column_header_cell("DISPOSITIVOS"),
                            rx.table.column_header_cell("H. SUELO"),
                            rx.table.column_header_cell("ESTADO"),
                            rx.table.column_header_cell(""),
                        )
                    ),
                    rx.table.body(rx.foreach(EstadoAgrotech.parcelas_resumen, fila_mi_parcela)),
                    variant="ghost",
                    size="2",
                    width="100%",
                ),
                width="100%",
                overflow_x="auto",
            ),
            spacing="3",
            width="100%",
        ),
        border="1px solid var(--gray-5)",
        **ESTILO_TARJETA_BASE,
    )


def item_alerta_reciente(alerta: list[str]) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.icon("triangle-alert", size=18, color="var(--red-11)", flex_shrink="0"),
            rx.vstack(
                rx.text(alerta[0], size="2", weight="bold", color="var(--red-11)"),
                rx.text(alerta[1], size="1", color="var(--gray-11)"),
                spacing="1",
                align="start",
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        on_click=lambda: EstadoAgrotech.set_parcela_seleccionada(alerta[2]),
        cursor="pointer",
        padding="0.85em 1em",
        border_radius="12px",
        background_color="var(--red-3)",
        border="1px solid var(--red-7)",
        width="100%",
    )


def tarjeta_alertas_recientes() -> rx.Component:
    tiene_alertas = EstadoAgrotech.alertas_recientes_lista.length() > 0
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Alertas recientes", size="4", weight="bold", color="var(--gray-12)"),
                rx.spacer(),
                rx.cond(
                    tiene_alertas,
                    rx.badge(
                        EstadoAgrotech.alertas_recientes_lista.length(),
                        " activas",
                        color_scheme="red",
                        variant="soft",
                        size="2",
                    ),
                    rx.badge("0 activas", color_scheme="grass", variant="soft", size="2"),
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                tiene_alertas,
                rx.vstack(
                    rx.foreach(EstadoAgrotech.alertas_recientes_lista, item_alerta_reciente),
                    spacing="2",
                    width="100%",
                    max_height="260px",
                    overflow_y="auto",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("circle-check", size=28, color="var(--grass-9)"),
                        rx.text(
                            "Todas las parcelas están dentro de rango",
                            size="2",
                            weight="medium",
                            color="var(--gray-11)",
                        ),
                        align="center",
                        spacing="2",
                    ),
                    padding="2.5em 1em",
                    border_radius="12px",
                    background_color="var(--gray-3)",
                    border="1px solid var(--gray-4)",
                    width="100%",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        border=rx.cond(tiene_alertas, "1.5px solid var(--red-8)", "1px solid var(--gray-5)"),
        **ESTILO_TARJETA_BASE,
    )


def fila_lectura(fila: list[str]) -> rx.Component:
    unidad = rx.cond(
        fila[0].contains("temp"),
        " ºC",
        rx.cond(
            fila[0].contains("humedad"),
            " %",
            rx.cond(
                fila[0].contains("lux"),
                " lux",
                rx.cond(fila[0].contains("ph"), " pH", ""),
            ),
        ),
    )
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="blue", variant="soft")),
        rx.table.cell(rx.text(fila[1], size="2", color="var(--gray-11)")),
        rx.table.cell(rx.text(fila[2] + unidad, weight="bold", color=fila[3])),
        rx.table.cell(rx.badge(fila[4], color_scheme=fila[5], variant="soft")),
    )


def _barra_navegacion() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.icon(tag="leaf", color="var(--grass-9)", size=28),
            rx.heading("Catálogo Agrotech", size="5", color="var(--grass-11)", weight="bold"),
            align_items="center",
            spacing="3",
        ),
        rx.hstack(
            rx.color_mode.button(),
            rx.menu.root(
                rx.menu.trigger(
                    rx.hstack(
                        rx.avatar(
                            fallback=BaseState.usuario_actual[:1].upper(),
                            size="1",
                            color_scheme="grass",
                            variant="solid",
                        ),
                        rx.vstack(
                            rx.text(BaseState.usuario_actual, weight="bold", size="2", color="var(--gray-12)"),
                            rx.text(
                                rx.match(
                                    EstadoAgrotech.rol_usuario,
                                    ("administrador", "Administrador"),
                                    ("tecnico_agricola", "Técnico Agrícola"),
                                    "Usuario",
                                ),
                                size="1",
                                color="var(--grass-10)",
                            ),
                            spacing="0",
                            align_items="start",
                        ),
                        padding="0.35em 0.75em",
                        border_radius="12px",
                        background_color="var(--gray-3)",
                        border="1px solid var(--gray-5)",
                        align_items="center",
                        spacing="2",
                        cursor="pointer",
                        _hover={"background_color": "var(--gray-4)"},
                    )
                ),
                rx.menu.content(
                    rx.cond(
                        EstadoAgrotech.rol_usuario == "administrador",
                        rx.menu.item(
                            rx.icon("users", size=16),
                            "Gestión de usuarios",
                            on_click=rx.redirect("/gestor-usuarios"),
                        ),
                    ),
                    rx.cond(
                        EstadoAgrotech.puede_gestionar_parcelas,
                        rx.menu.item(
                            rx.icon("map-pin", size=16),
                            "Gestión de parcelas",
                            on_click=rx.redirect("/gestor-parcelas"),
                        ),
                    ),
                    rx.cond(
                        EstadoAgrotech.puede_gestionar_parcelas,
                        rx.menu.separator(),
                    ),
                    rx.menu.item(
                        rx.icon("log-out", size=16),
                        "Cerrar Sesión",
                        on_click=BaseState.cerrar_sesion,
                        color="red",
                    ),
                ),
            ),
            spacing="4",
            align_items="center",
        ),
        justify_content="space-between",
        align_items="center",
        wrap="wrap",
        spacing="3",
        width="100%",
        min_width="0",
        padding=["0.8em 1em", "0.8em 2em"],
        border_bottom="1px solid var(--gray-5)",
        background_color="var(--gray-2)",
    )


# ==============================================================================
# 4. INTERFAZ PRINCIPAL DEL PANEL (/panel)
# ==============================================================================

def index() -> rx.Component:
    return rx.box(
        rx.html(ESTILOS_TEMA),
        _barra_navegacion(),
        rx.vstack(
            # 1. CABECERA PRINCIPAL + BOTÓN OCULTO #btn-actualizar CONSERVADO
            rx.hstack(
                rx.vstack(
                    rx.heading("Tu campo, de un vistazo", size="8", weight="bold", color="var(--gray-12)"),
                    rx.text("Monitoriza tus parcelas, sensores y alertas en tiempo real.", size="3", color="var(--gray-11)"),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.select(
                        EstadoAgrotech.opciones_parcelas,
                        value=EstadoAgrotech.parcela_seleccionada,
                        on_change=EstadoAgrotech.set_parcela_seleccionada,
                        variant="surface",
                        size="3",
                    ),
                    rx.button(
                        "Actualizar Datos",
                        id="btn-actualizar",
                        on_click=EstadoAgrotech.obtener_datos,
                        display="none",
                    ),
                    wrap="wrap",
                    align="center",
                    spacing="3",
                ),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="4",
                margin_bottom="0.5em",
            ),

            # 2. FILA DE TARJETAS KPI SUPERIORES
            rx.grid(
                tarjeta_kpi_superior(
                    "Tª Ambiente",
                    EstadoAgrotech.temp_amb_val,
                    "ºC",
                    EstadoAgrotech.temp_amb_estado,
                    EstadoAgrotech.temp_amb_critico,
                    "thermometer",
                    "#66cdaa",
                    "temperaturaAmb",
                ),
                tarjeta_kpi_superior(
                    "Tª Suelo",
                    EstadoAgrotech.temp_suelo_val,
                    "ºC",
                    EstadoAgrotech.temp_suelo_estado,
                    EstadoAgrotech.temp_suelo_critico,
                    "sprout",
                    "#66cdaa",
                    "temperaturaSuelo",
                ),
                tarjeta_kpi_superior(
                    "Humedad del suelo",
                    EstadoAgrotech.humedad_val,
                    "%",
                    EstadoAgrotech.humedad_estado,
                    EstadoAgrotech.humedad_critico,
                    "droplets",
                    "#4dd0e1",
                    "humedadSuelo",
                ),
                tarjeta_kpi_superior(
                    "Luminosidad",
                    EstadoAgrotech.lux_val,
                    "lx",
                    EstadoAgrotech.lux_estado,
                    EstadoAgrotech.lux_critico,
                    "sun",
                    "#ffd54f",
                    "luminosidad",
                ),
                tarjeta_kpi_superior(
                    "pH del suelo",
                    EstadoAgrotech.ph_val,
                    "pH",
                    EstadoAgrotech.ph_estado,
                    EstadoAgrotech.ph_critico,
                    "flask-conical",
                    "#b39ddb",
                    "ph",
                ),
                columns=rx.breakpoints(initial="1", sm="2", md="3", lg="5"),
                spacing="4",
                width="100%",
            ),

            # 3. FILA CENTRAL: GRÁFICA ÚNICA + SENSORES
            rx.grid(
                tarjeta_evolucion_grafica(),
                tarjeta_sensores_derecha(),
                columns=rx.breakpoints(initial="1", lg="2"),
                grid_template_columns=rx.breakpoints(initial="1fr", lg="1.65fr 1fr"),
                spacing="5",
                width="100%",
            ),

            # 4. FILA INFERIOR: MIS PARCELAS + ALERTAS RECIENTES
            rx.grid(
                tarjeta_mis_parcelas(),
                tarjeta_alertas_recientes(),
                columns=rx.breakpoints(initial="1", lg="2"),
                grid_template_columns=rx.breakpoints(initial="1fr", lg="1.65fr 1fr"),
                spacing="5",
                width="100%",
            ),

            # 5. REGISTRO DE ÚLTIMAS LECTURAS
            rx.accordion.root(
                rx.accordion.item(
                    header="Ver registro detallado de últimas 15 lecturas",
                    content=rx.box(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("ID Sensor"),
                                    rx.table.column_header_cell("Fecha / Hora"),
                                    rx.table.column_header_cell("Valor"),
                                    rx.table.column_header_cell("Estado"),
                                )
                            ),
                            rx.table.body(rx.foreach(EstadoAgrotech.lecturas, fila_lectura)),
                            variant="surface",
                            size="2",
                            width="100%",
                        ),
                        width="100%",
                        overflow_x="auto",
                    ),
                ),
                type="single",
                collapsible=True,
                variant="surface",
                width="100%",
            ),

            width="100%",
            max_width="1240px",
            min_width="0",
            margin="0 auto",
            padding=["1.5em 1em", "2em 1.5em"],
            spacing="5",
        ),
        width="100%",
        min_height="100vh",
        overflow_x="clip",
        background_color="var(--gray-1)",
    )


# ==============================================================================
# 5. CONFIGURACIÓN DE LA APP Y REGISTRO DE RUTAS
# ==============================================================================

app = rx.App()
app.add_page(login_page, route="/", title="Login | Agrotech")
app.add_page(index, route="/panel", on_load=EstadoAgrotech.comprobar_acceso, title="Panel Agrotech")
app.add_page(
    panel_gestor_usuarios,
    route="/gestor-usuarios",
    on_load=GestorUsuariosState.comprobar_acceso_admin,
    title="Gestor de Usuarios",
)
app.add_page(
    panel_gestor_parcelas,
    route="/gestor-parcelas",
    on_load=GestorParcelasState.comprobar_acceso_parcelas,
    title="Gestión de Parcelas",
)