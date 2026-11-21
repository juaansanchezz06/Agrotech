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

ETIQUETAS_SENSORES: dict[str, tuple[str, str, str]] = {
    "humedad": ("humedadSuelo", "%", "Sensor Humedad Suelo"),
    "lux": ("luminosidad", "lux", "Sensor Luz Solar"),
    "ph": ("ph", "pH", "Sensor pH Suelo"),
    "temp_amb": ("temperaturaAmb", "ºC", "Sensor Temp. Ambiente"),
    "temp_suelo": ("temperaturaSuelo", "ºC", "Sensor Temp. Suelo"),
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


def _color_temperatura(sensor_id: str, valor: float) -> str:
    if "temp" not in sensor_id:
        return "var(--gray-12)"
    if valor > 30:
        return "#ff8da1"
    if valor < 20:
        return "#82b1ff"
    return "#66cdaa"


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


def _construir_catalogo_sensores(
    cursor: sqlite3.Cursor,
    nombres_parcelas: dict[int, str],
) -> list[list[str]]:
    resultado: list[list[str]] = []
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sensors'")
    if cursor.fetchone() is not None:
        cursor.execute("PRAGMA table_info(sensors)")
        columnas = {fila[1] for fila in cursor.fetchall()}
        col_id = "sensor_id" if "sensor_id" in columnas and "id" not in columnas else "id"
        cursor.execute(f"SELECT {col_id}, parcel_id, type, unit FROM sensors ORDER BY parcel_id ASC, {col_id} ASC")
        for sid, pid, tipo, unidad in cursor.fetchall():
            sid_str = str(sid)
            sufijo = sid_str.split("_", 1)[1] if "_" in sid_str else ""
            meta = ETIQUETAS_SENSORES.get(sufijo)
            desc_base = meta[2] if meta else f"Sensor {tipo}"
            nombre_p = nombres_parcelas.get(int(pid), f"Parcela #{pid}") if pid is not None else ""
            descripcion = f"{desc_base} ({nombre_p})" if nombre_p else desc_base
            resultado.append([sid_str, str(tipo), str(unidad), descripcion])

    if not resultado:
        for pid, nombre_p in sorted(nombres_parcelas.items()):
            for sufijo, (tipo, unidad, desc_base) in ETIQUETAS_SENSORES.items():
                resultado.append([f"p{pid}_{sufijo}", tipo, unidad, f"{desc_base} ({nombre_p})"])

    return resultado


class EstadoAgrotech(BaseState):
    _token_streaming: int = 0
    _firma_grafica: str = ""

    parcelas: list[list[str]] = []
    sensores: list[list[str]] = []
    lecturas: list[list[str]] = []

    mapa_parcelas: dict[str, int] = dict(MAPA_PARCELAS_DEFECTO)
    opciones_parcelas: list[str] = list(MAPA_PARCELAS_DEFECTO.keys())

    rol_usuario: str = ""
    parcela_seleccionada: str = "Parcela Norte"

    temp_amb: str = "-- ºC"
    temp_suelo: str = "-- ºC"
    lux: str = "-- Lux"
    ph: str = "-- pH"
    humedad: str = "-- %"

    datos_grafica: list[dict[str, Any]] = []
    grafica_parcela: str = "Parcela Norte"
    grafica_tipo: str = "temperaturaAmb"
    grafica_fecha_inicio: str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    grafica_fecha_fin: str = datetime.now().strftime("%Y-%m-%d")
    valor_medio: str = "0.0"
    zoom_grafica: int = 100
    opciones_tipos: list[str] = list(MAPA_TIPOS.keys())

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
        self.obtener_datos()
        return EstadoAgrotech.iniciar_streaming

    def set_grafica_parcela(self, valor: str):
        self.grafica_parcela = valor
        self._firma_grafica = ""
        self.actualizar_grafica()

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

    def _cargar_grafica_con_cursor(self, cursor: sqlite3.Cursor):
        p_id = self.mapa_parcelas.get(self.grafica_parcela, 1)
        s_suffix = MAPA_TIPOS.get(self.grafica_tipo, "temp_amb")
        target_sensor_id = f"p{p_id}_{s_suffix}"

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
        nueva_firma = f"{target_sensor_id}|{len(datos_raw)}|{ultimo_registro[0]}|{ultimo_registro[1]}"
        if nueva_firma == self._firma_grafica:
            return
        self._firma_grafica = nueva_firma

        mismo_dia = bool(self.grafica_fecha_inicio) and self.grafica_fecha_inicio == self.grafica_fecha_fin
        grafica_formateada: list[dict[str, Any]] = []
        etiquetas_vistas: dict[str, int] = {}
        suma = 0.0

        for timestamp_raw, valor_raw in datos_raw:
            fecha_str = str(timestamp_raw) if timestamp_raw else ""
            if len(fecha_str) >= 19:
                etiqueta_base = (
                    fecha_str[11:19]
                    if mismo_dia
                    else f"{fecha_str[8:10]}/{fecha_str[5:7]} {fecha_str[11:19]}"
                )
            else:
                etiqueta_base = fecha_str

            repeticiones = etiquetas_vistas.get(etiqueta_base, 0) + 1
            etiquetas_vistas[etiqueta_base] = repeticiones
            etiqueta = etiqueta_base if repeticiones == 1 else f"{etiqueta_base} ({repeticiones})"

            valor = float(valor_raw) if valor_raw is not None else 0.0
            suma += valor
            grafica_formateada.append({"hora": etiqueta, "Valor": valor})

        self.datos_grafica = grafica_formateada
        self.valor_medio = str(round(suma / len(datos_raw), 2) if datos_raw else 0.0)

    def actualizar_grafica(self):
        try:
            with _conectar_db() as conexion:
                self._cargar_grafica_con_cursor(conexion.cursor())
        except sqlite3.Error as e:
            print(f"Error al actualizar gráfica: {e}")
            self.datos_grafica = []
            self.valor_medio = "0.0"

    def obtener_datos(self):
        try:
            asegurar_bd_agrotech()
            with _conectar_db() as conexion:
                cursor = conexion.cursor()

                cursor.execute("SELECT id, name, location FROM parcels ORDER BY id ASC")
                filas_parcelas = cursor.fetchall()

                if filas_parcelas:
                    self.parcelas = [
                        [str(col) if col is not None else "" for col in row]
                        for row in filas_parcelas
                    ]
                    nuevo_mapa = {str(row[1]): int(row[0]) for row in filas_parcelas if row[1]}
                    nombres_por_id = {int(row[0]): str(row[1]) for row in filas_parcelas if row[1]}
                    self.mapa_parcelas = nuevo_mapa
                    self.opciones_parcelas = list(nuevo_mapa.keys())
                else:
                    self.parcelas = [list(fila) for fila in PARCELAS_DEFECTO]
                    self.mapa_parcelas = dict(MAPA_PARCELAS_DEFECTO)
                    self.opciones_parcelas = list(MAPA_PARCELAS_DEFECTO.keys())
                    nombres_por_id = {int(f[0]): f[1] for f in PARCELAS_DEFECTO}

                if self.opciones_parcelas:
                    if self.parcela_seleccionada not in self.mapa_parcelas:
                        self.parcela_seleccionada = self.opciones_parcelas[0]
                    if self.grafica_parcela not in self.mapa_parcelas:
                        self.grafica_parcela = self.opciones_parcelas[0]

                self.sensores = _construir_catalogo_sensores(cursor, nombres_por_id)

                cursor.execute("""
                    SELECT sensor_id, timestamp, value
                    FROM sensor_data
                    ORDER BY id DESC
                    LIMIT 15
                """)
                lecturas_formateadas: list[list[str]] = []
                for sensor_raw, fecha_raw, valor_raw in cursor.fetchall():
                    sensor = str(sensor_raw) if sensor_raw else "Desconocido"
                    fecha_str = str(fecha_raw) if fecha_raw else ""
                    fecha_limpia = fecha_str[:19].replace("T", " ") if len(fecha_str) >= 19 else fecha_str
                    valor = float(valor_raw) if valor_raw is not None else 0.0
                    lecturas_formateadas.append([
                        sensor,
                        fecha_limpia,
                        str(valor),
                        _color_temperatura(sensor, valor),
                    ])
                self.lecturas = lecturas_formateadas

                p_id = self.mapa_parcelas.get(self.parcela_seleccionada, 1)
                patron_parcela = f"p{p_id}_%"
                cursor.execute("""
                    SELECT sensor_id, value
                    FROM sensor_data
                    WHERE id IN (
                        SELECT MAX(id)
                        FROM sensor_data
                        WHERE sensor_id LIKE ?
                        GROUP BY sensor_id
                    )
                """, (patron_parcela,))
                ultimos = dict(cursor.fetchall())

                self.temp_amb = f"{ultimos.get(f'p{p_id}_temp_amb', '--')} ºC"
                self.temp_suelo = f"{ultimos.get(f'p{p_id}_temp_suelo', '--')} ºC"
                self.humedad = f"{ultimos.get(f'p{p_id}_humedad', '--')} %"
                self.lux = f"{ultimos.get(f'p{p_id}_lux', '--')} Lux"
                self.ph = f"{ultimos.get(f'p{p_id}_ph', '--')} pH"

                self._cargar_grafica_con_cursor(cursor)

        except sqlite3.Error as e:
            print(f"Error en la base de datos: {e}")

    @rx.event(background=True)
    async def iniciar_streaming(self):
        async with self:
            self._token_streaming += 1
            mi_token = self._token_streaming
            id_parcela = self.mapa_parcelas.get(self.parcela_seleccionada, 1)

        uri = f"ws://localhost:8001/ws/parcels/{id_parcela}"

        while True:
            async with self:
                if self._token_streaming != mi_token or self.usuario_actual == "":
                    return

            try:
                async with websockets.connect(uri) as websocket:
                    while True:
                        async with self:
                            if self._token_streaming != mi_token or self.usuario_actual == "":
                                return

                        await websocket.recv()

                        async with self:
                            if self._token_streaming != mi_token or self.usuario_actual == "":
                                return
                            self.obtener_datos()
            except asyncio.CancelledError:
                return
            except Exception:
                await asyncio.sleep(2.0)


def tarjeta_metrica_circular(titulo: str, valor: str, icono: str, color_borde: str) -> rx.Component:
    return rx.vstack(
        rx.text(titulo, weight="bold", size="2", color="var(--gray-11)"),
        rx.center(
            rx.vstack(
                rx.icon(tag=icono, size=28, color=color_borde),
                rx.text(valor, weight="bold", size="4", color="var(--gray-12)"),
                align="center",
                justify="center",
                spacing="1",
            ),
            width="135px",
            height="135px",
            border_radius="50%",
            border=f"3px solid {color_borde}",
            box_shadow="0 6px 16px rgba(0,0,0,0.04)",
            background_color="var(--gray-2)",
        ),
        align="center",
        spacing="2",
    )


def vista_boceto_parcelas() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.hstack(
                rx.heading("PARCELA:", size="3", color="var(--gray-12)", weight="bold"),
                rx.select(
                    EstadoAgrotech.opciones_parcelas,
                    value=EstadoAgrotech.parcela_seleccionada,
                    on_change=EstadoAgrotech.set_parcela_seleccionada,
                    variant="soft",
                    size="2",
                ),
                align="center",
                spacing="3",
            ),
            rx.text("Métricas de Suelo y Microclima", size="2", color="var(--gray-11)"),
            width="100%",
            justify="between",
            align="center",
            wrap="wrap",
            spacing="3",
            padding_bottom="1.2em",
            border_bottom="1px solid var(--gray-5)",
            margin_bottom="1.5em",
        ),
        rx.flex(
            tarjeta_metrica_circular("Tª Ambiente", EstadoAgrotech.temp_amb, "thermometer", "#ff8da1"),
            tarjeta_metrica_circular("Tª Suelo", EstadoAgrotech.temp_suelo, "sprout", "#82b1ff"),
            tarjeta_metrica_circular("Luminosidad", EstadoAgrotech.lux, "sun", "#ffd54f"),
            tarjeta_metrica_circular("pH Suelo", EstadoAgrotech.ph, "flask-conical", "#b39ddb"),
            tarjeta_metrica_circular("Humedad (Hº)", EstadoAgrotech.humedad, "droplets", "#4dd0e1"),
            wrap="wrap",
            justify="center",
            spacing="5",
            width="100%",
        ),
        width="100%",
        min_width="0",
        padding="1.8em",
        border="1px solid var(--gray-5)",
        border_radius="20px",
        background_color="var(--gray-2)",
        box_shadow="0 4px 20px rgba(0, 0, 0, 0.03)",
        margin_top="1.5em",
        margin_bottom="1em",
    )


def vista_grafica() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Evolución de Métricas", size="4", color="var(--gray-12)"),
                    rx.text(
                        "Filtra los datos históricos por parcela, métrica y rango de fechas",
                        size="2",
                        color="var(--gray-11)",
                    ),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.text("Zoom:", size="2", weight="medium", color="var(--gray-11)"),
                    rx.icon_button(
                        rx.icon("minus", size=16),
                        on_click=EstadoAgrotech.reducir_zoom_grafica,
                        disabled=EstadoAgrotech.zoom_grafica <= 100,
                        variant="soft",
                        color_scheme="grass",
                        size="2",
                        cursor=rx.cond(EstadoAgrotech.zoom_grafica <= 100, "not-allowed", "pointer"),
                        title="Desampliar gráfica",
                    ),
                    rx.text(
                        EstadoAgrotech.ancho_grafica,
                        size="2",
                        weight="bold",
                        color="var(--gray-12)",
                        min_width="3.5em",
                        text_align="center",
                    ),
                    rx.icon_button(
                        rx.icon("plus", size=16),
                        on_click=EstadoAgrotech.aumentar_zoom_grafica,
                        disabled=EstadoAgrotech.zoom_grafica >= 400,
                        variant="soft",
                        color_scheme="grass",
                        size="2",
                        cursor=rx.cond(EstadoAgrotech.zoom_grafica >= 400, "not-allowed", "pointer"),
                        title="Ampliar gráfica",
                    ),
                    padding="0.35em 0.6em",
                    border_radius="12px",
                    background_color="var(--gray-3)",
                    border="1px solid var(--gray-5)",
                    align="center",
                    spacing="2",
                ),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="3",
                margin_bottom="1em",
            ),

            rx.hstack(
                rx.vstack(
                    rx.text("Parcela", size="1", weight="bold", color="var(--gray-12)"),
                    rx.select(
                        EstadoAgrotech.opciones_parcelas,
                        value=EstadoAgrotech.grafica_parcela,
                        on_change=EstadoAgrotech.set_grafica_parcela,
                        variant="soft",
                    ),
                    align="start",
                ),
                rx.vstack(
                    rx.text("Métrica", size="1", weight="bold", color="var(--gray-12)"),
                    rx.select(
                        EstadoAgrotech.opciones_tipos,
                        value=EstadoAgrotech.grafica_tipo,
                        on_change=EstadoAgrotech.set_grafica_tipo,
                        variant="soft",
                    ),
                    align="start",
                ),
                rx.vstack(
                    rx.text("Desde", size="1", weight="bold", color="var(--gray-12)"),
                    rx.input(
                        type="date",
                        value=EstadoAgrotech.grafica_fecha_inicio,
                        max=EstadoAgrotech.grafica_fecha_fin,
                        on_change=EstadoAgrotech.set_grafica_fecha_inicio,
                        variant="soft",
                        color_scheme="grass",
                    ),
                    align="start",
                ),
                rx.vstack(
                    rx.text("Hasta", size="1", weight="bold", color="var(--gray-12)"),
                    rx.input(
                        type="date",
                        value=EstadoAgrotech.grafica_fecha_fin,
                        min=EstadoAgrotech.grafica_fecha_inicio,
                        on_change=EstadoAgrotech.set_grafica_fecha_fin,
                        variant="soft",
                        color_scheme="grass",
                    ),
                    align="start",
                ),
                wrap="wrap",
                spacing="5",
                margin_bottom="1.5em",
                width="100%",
            ),

            rx.hstack(
                rx.text("Media del periodo:", size="2", color="var(--gray-11)"),
                rx.text(EstadoAgrotech.valor_medio, size="3", weight="bold", color="var(--grass-11)"),
                align="center",
                spacing="2",
                margin_bottom="1.2em",
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
                            dot={"fill": "#64B5F6", "stroke": "var(--gray-12)", "strokeWidth": 1, "r": 4},
                            active_dot={"r": 6, "fill": "var(--grass-9)", "stroke": "var(--gray-12)"},
                        ),
                        rx.recharts.reference_line(
                            y=EstadoAgrotech.valor_medio,
                            stroke="var(--grass-9)",
                            stroke_dasharray="4 4",
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
                            item_style={"color": "#64B5F6", "fontWeight": "bold"},
                        ),
                        data=EstadoAgrotech.datos_grafica,
                        height=320,
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
                padding_bottom="0.75em",
            ),
            width="100%",
            min_width="0",
            padding="0.35em",
        ),
        width="100%",
        min_width="0",
        padding="2em",
        border="1px solid var(--gray-5)",
        background_color="var(--gray-2)",
        box_shadow="0 4px 12px rgba(0, 0, 0, 0.03)",
        border_radius="16px",
        margin_top="1.5em",
    )


def crear_tabla(cabeceras: list[str], datos: list[list[str]], render_fila) -> rx.Component:
    return rx.card(
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(*[rx.table.column_header_cell(c) for c in cabeceras])
                ),
                rx.table.body(rx.foreach(datos, render_fila)),
                variant="surface",
                size="3",
                width="100%",
            ),
            width="100%",
            min_width="0",
            overflow_x="auto",
        ),
        width="100%",
        min_width="0",
        border="1px solid var(--gray-5)",
        background_color="var(--gray-2)",
        box_shadow="0 4px 12px rgba(0, 0, 0, 0.03)",
        border_radius="16px",
    )


def fila_parcela(fila: list[str]) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="green", variant="soft")),
        rx.table.cell(rx.text(fila[1], weight="bold", color="var(--gray-12)")),
        rx.table.cell(rx.text(fila[2], color="var(--gray-11)")),
    )


def fila_sensor(fila: list[str]) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="blue", variant="soft")),
        rx.table.cell(rx.text(fila[1], weight="bold", color="var(--gray-12)")),
        rx.table.cell(rx.text(fila[2], color="var(--gray-11)")),
        rx.table.cell(rx.text(fila[3], color="var(--gray-11)")),
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
        rx.table.cell(rx.badge("Recibido", color_scheme="grass", variant="soft")),
    )


def index() -> rx.Component:
    return rx.box(
        rx.html(ESTILOS_TEMA),

        rx.hstack(
            rx.hstack(
                rx.icon(tag="leaf", color="var(--grass-9)", size=30),
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

        rx.vstack(
            rx.vstack(
                rx.heading("Monitorización y Catálogo", size="7", weight="bold", color="var(--gray-12)"),
                rx.text(
                    "Visualiza las parcelas, sensores y los datos en tiempo real.",
                    color="var(--gray-11)",
                    size="2",
                ),
                align_items="start",
                spacing="1",
                width="100%",
                margin_bottom="1.5em",
            ),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Lecturas en Vivo", value="lecturas"),
                    rx.tabs.trigger("Evolución (Gráfica)", value="grafica"),
                    rx.tabs.trigger("Listado de Parcelas", value="parcelas"),
                    rx.tabs.trigger("Listado de Sensores", value="sensores"),
                    size="2",
                    max_width="100%",
                    overflow_x="auto",
                    overflow_y="hidden",
                ),
                rx.tabs.content(
                    rx.vstack(
                        vista_boceto_parcelas(),
                        crear_tabla(
                            ["ID Sensor", "Fecha / Hora", "Valor", "Estado"],
                            EstadoAgrotech.lecturas,
                            fila_lectura,
                        ),
                        spacing="4",
                        width="100%",
                        min_width="0",
                    ),
                    value="lecturas",
                    width="100%",
                    min_width="0",
                ),
                rx.tabs.content(
                    vista_grafica(),
                    value="grafica",
                    width="100%",
                    min_width="0",
                ),
                rx.tabs.content(
                    crear_tabla(["ID Parcela", "Nombre", "Ubicación"], EstadoAgrotech.parcelas, fila_parcela),
                    value="parcelas",
                    width="100%",
                    min_width="0",
                ),
                rx.tabs.content(
                    crear_tabla(
                        ["ID Sensor", "Tipo", "Unidad", "Descripción"],
                        EstadoAgrotech.sensores,
                        fila_sensor,
                    ),
                    value="sensores",
                    width="100%",
                    min_width="0",
                ),
                default_value="lecturas",
                width="100%",
                max_width="100%",
                min_width="0",
            ),
            width="100%",
            max_width="1200px",
            min_width="0",
            margin="0 auto",
            padding=["1.5em 1em", "2em 1.5em"],
        ),
        width="100%",
        min_height="100vh",
        overflow_x="clip",
        background_color="var(--gray-1)",
    )


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