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
from datetime import datetime, timedelta
from typing import Any

import reflex as rx
import websockets

try:
    from login import BaseState, login_page, asegurar_bd_agrotech
    from gestor_usuarios import GestorUsuariosState, panel_gestor_usuarios
    from gestor_parcelas import GestorParcelasState, panel_gestor_parcelas
except ImportError:
    from .login import BaseState, login_page, asegurar_bd_agrotech
    from .gestor_usuarios import GestorUsuariosState, panel_gestor_usuarios
    from .gestor_parcelas import GestorParcelasState, panel_gestor_parcelas


# ==============================================================================
# 1. CONFIGURACIÓN GLOBAL Y CONSTANTES DE MAPEO
# ==============================================================================

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_RAIZ = os.path.abspath(os.path.join(DIR_ACTUAL, "..", ".."))
RUTA_DB = os.path.join(RUTA_RAIZ, "agrotech.db")

PARCELAS_DEFECTO: list[list[str]] = [
    ["1", "Parcela Norte", "Sector A"],
    ["2", "Parcela Sur", "Sector B"],
    ["3", "Invernadero Principal", "Sector C"],
    ["4", "Viñedo Este", "Sector D"],
    ["5", "Huerto Central", "Sector E"],
]

MAPA_PARCELAS_DEFECTO: dict[str, int] = {
    fila[1]: int(fila[0]) for fila in PARCELAS_DEFECTO
}

MAPA_TIPOS: dict[str, str] = {
    "temperaturaAmb": "temp_amb",
    "humedadSuelo": "humedad",
    "luminosidad": "lux",
    "temperaturaSuelo": "temp_suelo",
    "ph": "ph",
}

NOMBRES_METRICAS: dict[str, str] = {
    "temperaturaAmb": "Tª Ambiente",
    "temperaturaSuelo": "Tª Suelo",
    "humedadSuelo": "Humedad Suelo",
    "luminosidad": "Luminosidad",
    "ph": "pH Suelo",
}

UNIDADES_TIPO: dict[str, str] = {
    "temperaturaAmb": "ºC",
    "humedadSuelo": "%",
    "luminosidad": "Lux",
    "temperaturaSuelo": "ºC",
    "ph": "pH",
}

COLUMNAS_RANGOS: dict[str, tuple[str, str]] = {
    "temp_amb": ("temp_amb_min", "temp_amb_max"),
    "temp_suelo": ("temp_suelo_min", "temp_suelo_max"),
    "humedad": ("humedad_min", "humedad_max"),
    "lux": ("lux_min", "lux_max"),
    "ph": ("ph_min", "ph_max"),
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

    def aumentar_zoom_grafica(self):
        if self.zoom_grafica < 400:
            self.zoom_grafica += 50
            return rx.call_script("window.dispatchEvent(new Event('resize'));")

    def reducir_zoom_grafica(self):
        if self.zoom_grafica > 100:
            self.zoom_grafica -= 50
            return rx.call_script(_script_ajuste_zoom(self.zoom_grafica <= 100))

    def _asegurar_columnas_parcelas(self, cursor: sqlite3.Cursor, conexion: sqlite3.Connection):
        columnas_necesarias = {
            "temp_amb_min": "REAL DEFAULT 15.0",
            "temp_amb_max": "REAL DEFAULT 32.0",
            "temp_suelo_min": "REAL DEFAULT 12.0",
            "temp_suelo_max": "REAL DEFAULT 28.0",
            "ph_min": "REAL DEFAULT 5.5",
            "ph_max": "REAL DEFAULT 7.5",
            "lux_min": "REAL DEFAULT 200.0",
            "lux_max": "REAL DEFAULT 50000.0",
            "humedad_min": "REAL DEFAULT 40.0",
            "humedad_max": "REAL DEFAULT 85.0",
        }
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parcels'")
        if cursor.fetchone() is None:
            return
        cursor.execute("PRAGMA table_info(parcels)")
        existentes = {fila[1] for fila in cursor.fetchall()}
        modificado = False
        for col, definicion in columnas_necesarias.items():
            if col not in existentes:
                cursor.execute(f"ALTER TABLE parcels ADD COLUMN {col} {definicion}")
                modificado = True
        if modificado:
            conexion.commit()

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

    def _evaluar_estado_kpi(self, valor: float | None, v_min: float, v_max: float) -> tuple[str, bool]:
        if valor is None:
            return ("Sin lecturas", False)
        if valor > v_max:
            return (f"Crítico alto (> {v_max})", True)
        if valor < v_min:
            return (f"Crítico bajo (< {v_min})", True)
        return ("En rango óptimo", False)
        
    def _cargar_grafica_con_cursor(self, cursor: sqlite3.Cursor):
        p_id = self.mapa_parcelas.get(self.parcela_seleccionada, 1)
        s_suffix = MAPA_TIPOS.get(self.grafica_tipo, "temp_amb")
        self.grafica_unidad = UNIDADES_TIPO.get(self.grafica_tipo, "")
        self.grafica_nombre_metrica = NOMBRES_METRICAS.get(self.grafica_tipo, "Tª Ambiente")
        target_sensor_id = f"p{p_id}_{s_suffix}"

        col_min, col_max = COLUMNAS_RANGOS.get(s_suffix, ("temp_amb_min", "temp_amb_max"))
        r_min_f = 15.0
        r_max_f = 32.0

        cursor.execute(f"SELECT {col_min}, {col_max} FROM parcels WHERE id = ?", (p_id,))
        fila_rango = cursor.fetchone()
        if fila_rango and fila_rango[0] is not None and fila_rango[1] is not None:
            r_min_f = float(fila_rango[0])
            r_max_f = float(fila_rango[1])
        elif p_id in self.rangos_parcelas_cache and s_suffix in self.rangos_parcelas_cache[p_id]:
            r_min_f, r_max_f = self.rangos_parcelas_cache[p_id][s_suffix]

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

        query = f"""
            SELECT timestamp, value
            FROM sensor_data
            WHERE {' AND '.join(condiciones)}
            ORDER BY id ASC
        """
        cursor.execute(query, tuple(parametros))
        datos_raw = cursor.fetchall()

        ultimo_registro = datos_raw[-1] if datos_raw else ("", 0)
        nueva_firma = (
            f"{target_sensor_id}|{len(datos_raw)}|{ultimo_registro[0]}|{ultimo_registro[1]}"
            f"|{r_min_f}|{r_max_f}|{self.grafica_fecha_inicio}|{self.grafica_fecha_fin}"
        )
        if nueva_firma == self._firma_grafica:
            return
        self._firma_grafica = nueva_firma

        grafica_formateada: list[dict[str, Any]] = []
        suma = 0.0
        mismo_dia = (
            bool(self.grafica_fecha_inicio)
            and self.grafica_fecha_inicio == self.grafica_fecha_fin
        )

        total_sobre_max = 0
        total_bajo_min = 0

        for timestamp_raw, valor_raw in datos_raw:
            fecha_cruda_g = str(timestamp_raw) if timestamp_raw else ""
            if len(fecha_cruda_g) >= 19:
                if mismo_dia:
                    etiqueta_tiempo = fecha_cruda_g[11:19]
                else:
                    etiqueta_tiempo = f"{fecha_cruda_g[8:10]}/{fecha_cruda_g[5:7]} {fecha_cruda_g[11:16]}"
            else:
                etiqueta_tiempo = fecha_cruda_g

            valor_g = float(valor_raw) if valor_raw is not None else 0.0
            suma += valor_g

            es_fuera_rango = False
            if valor_g > r_max_f:
                total_sobre_max += 1
                es_fuera_rango = True
            elif valor_g < r_min_f:
                total_bajo_min += 1
                es_fuera_rango = True

            punto: dict[str, Any] = {
                "hora": etiqueta_tiempo,
                "Valor": valor_g,
            }
            if es_fuera_rango:
                punto["Error"] = valor_g

            grafica_formateada.append(punto)

        # Reducir puntos enviados al navegador (máx. 250) manteniendo errores y picos
        total_puntos = len(grafica_formateada)
        max_puntos = 250
        if total_puntos > max_puntos:
            indices_clave: set[int] = {0, total_puntos - 1}
            for i, p in enumerate(grafica_formateada):
                if "Error" in p:
                    indices_clave.add(i)

            restantes = max(10, max_puntos - len(indices_clave))
            num_tramos = max(1, restantes // 2)
            tam_tramo = total_puntos / num_tramos

            for t in range(num_tramos):
                inicio = int(t * tam_tramo)
                fin = min(total_puntos, int((t + 1) * tam_tramo))
                if inicio < fin:
                    indices_clave.add(min(range(inicio, fin), key=lambda i: grafica_formateada[i]["Valor"]))
                    indices_clave.add(max(range(inicio, fin), key=lambda i: grafica_formateada[i]["Valor"]))

            self.datos_grafica = [grafica_formateada[i] for i in sorted(indices_clave)]
        else:
            self.datos_grafica = grafica_formateada

        media_calculada = round(suma / len(datos_raw), 2) if datos_raw else 0.0
        self.valor_medio = str(media_calculada)

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
                        tareas_ws[pid] = asyncio.create_task(
                            self._escuchar_ws_parcela(pid, mi_token)
                        )

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
            for t in tareas_ws.values():
                if not t.done():
                    t.cancel()

    def obtener_datos(self):
        try:
            asegurar_bd_agrotech()
            with _conectar_db() as conexion:
                cursor = conexion.cursor()
                self._asegurar_columnas_parcelas(cursor, conexion)

                # 1. Cargar parcelas y rangos desde Gestión de Parcelas
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
                        (int(f[0]), f[1], f[2], 15.0, 32.0, 12.0, 28.0, 5.5, 7.5, 200.0, 50000.0, 40.0, 85.0)
                        for f in PARCELAS_DEFECTO
                    ]

                rangos_por_parcela: dict[int, dict[str, tuple[float, float]]] = {}
                cache_serializable: dict[int, dict[str, list[float]]] = {}
                nuevo_mapa: dict[str, int] = {}
                nuevas_opciones: list[str] = []

                for r in filas_parcelas:
                    pid = int(r[0])
                    nombre_p = str(r[1])
                    nuevo_mapa[nombre_p] = pid
                    nuevas_opciones.append(nombre_p)
                    rangos_por_parcela[pid] = {
                        "temp_amb": (float(r[3]), float(r[4])),
                        "temp_suelo": (float(r[5]), float(r[6])),
                        "ph": (float(r[7]), float(r[8])),
                        "lux": (float(r[9]), float(r[10])),
                        "humedad": (float(r[11]), float(r[12])),
                    }
                    cache_serializable[pid] = {
                        "temp_amb": [float(r[3]), float(r[4])],
                        "temp_suelo": [float(r[5]), float(r[6])],
                        "ph": [float(r[7]), float(r[8])],
                        "lux": [float(r[9]), float(r[10])],
                        "humedad": [float(r[11]), float(r[12])],
                    }

                self.mapa_parcelas = nuevo_mapa
                self.opciones_parcelas = nuevas_opciones
                self.rangos_parcelas_cache = cache_serializable

                if self.parcela_seleccionada not in self.mapa_parcelas and nuevas_opciones:
                    self.parcela_seleccionada = nuevas_opciones[0]

                # 2. Último valor registrado por sensor
                cursor.execute("""
                    SELECT sensor_id, value, timestamp FROM sensor_data
                    WHERE id IN (SELECT MAX(id) FROM sensor_data GROUP BY sensor_id)
                """)
                ultimos_todos: dict[str, float] = {}
                ultimos_ts: dict[str, str] = {}
                for sid, val, ts in cursor.fetchall():
                    if val is not None:
                        ultimos_todos[str(sid)] = float(val)
                        ultimos_ts[str(sid)] = str(ts)[11:19] if ts and len(str(ts)) >= 19 else "--:--"

                # 3. Tarjetas KPI de la parcela activa
                p_id = self.mapa_parcelas.get(self.parcela_seleccionada, 1)
                rangos_activos = rangos_por_parcela.get(p_id, {
                    "temp_amb": (15.0, 32.0),
                    "temp_suelo": (12.0, 28.0),
                    "humedad": (40.0, 85.0),
                    "lux": (200.0, 50000.0),
                    "ph": (5.5, 7.5),
                })

                v_amb = ultimos_todos.get(f"p{p_id}_temp_amb")
                v_suelo = ultimos_todos.get(f"p{p_id}_temp_suelo")
                v_hum = ultimos_todos.get(f"p{p_id}_humedad")
                v_lux = ultimos_todos.get(f"p{p_id}_lux")
                v_ph = ultimos_todos.get(f"p{p_id}_ph")

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

                self.es_parcela_critica = (
                    self.temp_amb_critico
                    or self.temp_suelo_critico
                    or self.humedad_critico
                    or self.lux_critico
                    or self.ph_critico
                )

                # 4. Panel derecho: Sensores de la parcela seleccionada
                defs_sensores = [
                    ("Tª Ambiente", f"p{p_id}_temp_amb", v_amb, "ºC", "thermometer"),
                    ("Tª Suelo", f"p{p_id}_temp_suelo", v_suelo, "ºC", "sprout"),
                    ("Humedad Suelo", f"p{p_id}_humedad", v_hum, "%", "droplets"),
                    ("Luminosidad", f"p{p_id}_lux", v_lux, "Lux", "sun"),
                    ("pH Suelo", f"p{p_id}_ph", v_ph, "pH", "flask-conical"),
                ]
                lista_sensores_p: list[list[str]] = []
                for nom_s, sid_s, val_s, uni_s, ico_s in defs_sensores:
                    hora_s = ultimos_ts.get(sid_s, "--:--")
                    valor_txt = f"{val_s} {uni_s}" if val_s is not None else "Sin datos"
                    estado_conn = "Conectado" if val_s is not None else "Esperando"
                    lista_sensores_p.append([nom_s, f"{sid_s} · {hora_s}", valor_txt, estado_conn, ico_s])
                self.sensores_parcela = lista_sensores_p

                # 5. Bloque inferior izquierdo: Resumen de Mis Parcelas + Alertas Recientes
                criticas_globales: list[str] = []
                alertas_items: list[list[str]] = []
                resumen_p: list[list[str]] = []

                etiquetas_cortas = {
                    "temp_amb": ("Tª Ambiente", "ºC"),
                    "temp_suelo": ("Tª Suelo", "ºC"),
                    "humedad": ("Humedad", "%"),
                    "lux": ("Luminosidad", "Lux"),
                    "ph": ("pH Suelo", "pH"),
                }

                for r in filas_parcelas:
                    pid = int(r[0])
                    nombre_p = str(r[1])
                    ubicacion_p = str(r[2] or "Sector asignado")
                    r_p = rangos_por_parcela.get(pid, {})
                    tiene_alerta_p = False

                    for tipo_s, (r_min, r_max) in r_p.items():
                        sid_check = f"p{pid}_{tipo_s}"
                        val_s = ultimos_todos.get(sid_check)
                        if val_s is not None:
                            nom_m, uni_m = etiquetas_cortas[tipo_s]
                            hora_a = ultimos_ts.get(sid_check, "--:--")
                            if val_s > r_max:
                                tiene_alerta_p = True
                                alertas_items.append([
                                    f"{nom_m} alta en {nombre_p}",
                                    f"Valor: {val_s} {uni_m} (máx. {r_max} {uni_m}) · {hora_a}",
                                    nombre_p,
                                ])
                            elif val_s < r_min:
                                tiene_alerta_p = True
                                alertas_items.append([
                                    f"{nom_m} baja en {nombre_p}",
                                    f"Valor: {val_s} {uni_m} (mín. {r_min} {uni_m}) · {hora_a}",
                                    nombre_p,
                                ])

                    if tiene_alerta_p:
                        criticas_globales.append(nombre_p)

                    hum_p = ultimos_todos.get(f"p{pid}_humedad")
                    hum_txt = f"{hum_p} %" if hum_p is not None else "-- %"
                    estado_p_txt = "Revisar alerta" if tiene_alerta_p else "Óptimo"
                    estado_p_color = "red" if tiene_alerta_p else "grass"
                    resumen_p.append([nombre_p, ubicacion_p, "5 sensores", hum_txt, estado_p_txt, estado_p_color])

                self.parcelas_criticas_global = criticas_globales
                self.alertas_recientes_lista = alertas_items
                self.parcelas_resumen = resumen_p

                # 6. Historial reciente de lecturas
                cursor.execute("""
                    SELECT sensor_id, timestamp, value
                    FROM sensor_data
                    ORDER BY id DESC LIMIT 15
                """)
                datos_formateados = []
                for fila in cursor.fetchall():
                    sensor = str(fila[0]) if fila[0] else "Desconocido"
                    fecha_cruda = str(fila[1]) if fila[1] else ""
                    fecha_limpia = fecha_cruda[:19].replace("T", " ") if len(fecha_cruda) >= 19 else fecha_cruda
                    valor_real = float(fila[2]) if fila[2] is not None else 0.0

                    color_texto = "#66cdaa"
                    estado_txt = "En rango"
                    estado_color = "grass"

                    if sensor.startswith("p") and "_" in sensor:
                        partes = sensor.split("_", 1)
                        try:
                            pid_sensor = int(partes[0][1:])
                            tipo_sensor = partes[1]
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

                # 7. Actualizar la gráfica única
                self._cargar_grafica_con_cursor(cursor)

        except sqlite3.Error as e:
            print(f"Error en la base de datos: {e}")


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
                rx.hstack(
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
                ),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="3",
            ),

            rx.hstack(
                _tab_metrica_grafica("Tª Ambiente", "temperaturaAmb"),
                _tab_metrica_grafica("Tª Suelo", "temperaturaSuelo"),
                _tab_metrica_grafica("Humedad Suelo", "humedadSuelo"),
                _tab_metrica_grafica("Luminosidad", "luminosidad"),
                _tab_metrica_grafica("pH Suelo", "ph"),
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

            rx.box(
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
                        # Puntos de error resaltados en rojo grande sobre la línea cuando salen de rango
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
            ),

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
        padding="1.5em",
        border_radius="16px",
        background_color="var(--gray-2)",
        border=rx.cond(
            EstadoAgrotech.grafica_tiene_excesos,
            "1.5px solid var(--red-8)",
            "1px solid var(--gray-5)",
        ),
        box_shadow="0 2px 10px rgba(0, 0, 0, 0.03)",
        width="100%",
        min_width="0",
    )
    MAX_PUNTOS_GRAFICA = 250


    def _reducir_puntos_grafica(
        puntos: list[dict[str, Any]], max_puntos: int = MAX_PUNTOS_GRAFICA
    ) -> list[dict[str, Any]]:
        total = len(puntos)
        if total <= max_puntos:
            return puntos

        indices_clave: set[int] = {0, total - 1}
        for i, p in enumerate(puntos):
            if "Error" in p:
                indices_clave.add(i)

        restantes = max(10, max_puntos - len(indices_clave))
        num_tramos = max(1, restantes // 2)
        tam_tramo = total / num_tramos

        for t in range(num_tramos):
            inicio = int(t * tam_tramo)
            fin = min(total, int((t + 1) * tam_tramo))
            if inicio >= fin:
                continue
            idx_min = min(range(inicio, fin), key=lambda i: puntos[i]["Valor"])
            idx_max = max(range(inicio, fin), key=lambda i: puntos[i]["Valor"])
            indices_clave.add(idx_min)
            indices_clave.add(idx_max)

        return [puntos[i] for i in sorted(indices_clave)]

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
        padding="1.5em",
        border_radius="16px",
        background_color="var(--gray-2)",
        border="1px solid var(--gray-5)",
        box_shadow="0 2px 10px rgba(0, 0, 0, 0.03)",
        width="100%",
        min_width="0",
    )


def fila_mi_parcela(fila: list[str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.center(
                    rx.icon(
                        "box",
                        size=16,
                        color=rx.cond(fila[5] == "red", "var(--red-11)", "var(--grass-11)"),
                    ),
                    width="32px",
                    height="32px",
                    border_radius="8px",
                    background_color=rx.cond(fila[5] == "red", "var(--red-3)", "var(--gray-3)"),
                    border=rx.cond(fila[5] == "red", "1px solid var(--red-7)", "1px solid var(--gray-5)"),
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
        padding="1.5em",
        border_radius="16px",
        background_color="var(--gray-2)",
        border="1px solid var(--gray-5)",
        box_shadow="0 2px 10px rgba(0, 0, 0, 0.03)",
        width="100%",
        min_width="0",
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
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Alertas recientes", size="4", weight="bold", color="var(--gray-12)"),
                rx.spacer(),
                rx.cond(
                    EstadoAgrotech.alertas_recientes_lista.length() > 0,
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
                EstadoAgrotech.alertas_recientes_lista.length() > 0,
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
                        rx.text("Todas las parcelas están dentro de rango", size="2", weight="medium", color="var(--gray-11)"),
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
        padding="1.5em",
        border_radius="16px",
        background_color="var(--gray-2)",
        border=rx.cond(
            EstadoAgrotech.alertas_recientes_lista.length() > 0,
            "1.5px solid var(--red-8)",
            "1px solid var(--gray-5)",
        ),
        box_shadow="0 2px 10px rgba(0, 0, 0, 0.03)",
        width="100%",
        min_width="0",
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


# ==============================================================================
# 4. INTERFAZ PRINCIPAL DEL PANEL (/panel)
# ==============================================================================

def index() -> rx.Component:
    return rx.box(
        rx.html(ESTILOS_TEMA),

        # Barra de navegación superior
        rx.hstack(
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
        ),

        # Contenedor principal en cuadrícula
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

            # 5. REGISTRO DE ÚLTIMAS LECTURAS (desplegable limpio)
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