"""
MÓDULO PRINCIPAL DE LA APLICACIÓN AGROTECH (panel_web.py)
---------------------------------------------------------
Este fichero centraliza el panel de monitorización en tiempo real, la visualización
histórica mediante gráficas, las tablas de catálogo y el enrutamiento general.

ÍNDICE DE SECCIONES:
  1. Importaciones y configuración global (rutas de BD y diccionarios de mapeo).
  2. Estado principal (EstadoAgrotech): lógica de negocio, SQLite y WebSockets.
  3. Componentes de métricas en tiempo real (tarjetas circulares por parcela).
  4. Componente de gráfica histórica (filtros, cálculo de media y Recharts).
  5. Componentes de tablas reutilizables (parcelas, sensores y lecturas).
  6. Interfaz principal (index): estilos CSS, barra de navegación y pestañas.
  7. Configuración de la aplicación y registro de rutas.
"""

import reflex as rx
import sqlite3
import os
import json
import asyncio
import websockets
from datetime import datetime
from typing import Any, List, Dict

# Importación de vistas y estados secundarios.
# El bloque try/except permite ejecutar tanto desde la raíz del proyecto como en modo paquete.
try:
    from login import login_page, BaseState
    from gestor_usuarios import panel_gestor_usuarios, GestorUsuariosState
    from gestor_parcelas import panel_gestor_parcelas, GestorParcelasState
except ImportError:
    from .login import login_page, BaseState
    from .gestor_usuarios import panel_gestor_usuarios, GestorUsuariosState
    from .gestor_parcelas import panel_gestor_parcelas, GestorParcelasState


# ==============================================================================
# 1. CONFIGURACIÓN GLOBAL Y CONSTANTES DE MAPEO
# ==============================================================================

# Ruta absoluta hacia la base de datos SQLite situada dos niveles por encima
DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")

# Relaciona el nombre legible de cada parcela con su ID numérico en la base de datos
MAPA_PARCELAS = {
    "Parcela Norte": 1,
    "Parcela Sur": 2,
    "Invernadero Principal": 3,
    "Viñedo Este": 4,
    "Huerto Central": 5
}

# Traduce el nombre técnico de la métrica al sufijo usado en sensor_id (ej. "p1_temp_amb")
MAPA_TIPOS = {
    "temperaturaAmb": "temp_amb",
    "humedadSuelo": "humedad",
    "luminosidad": "lux",
    "temperaturaSuelo": "temp_suelo",
    "ph": "ph"
}


# ==============================================================================
# 2. ESTADO DEL PANEL Y OBTENCIÓN DINÁMICA DE DATOS
# ==============================================================================

class EstadoAgrotech(BaseState):
    """
    Gestiona el estado reactivo del panel principal:
      - Control de sesión y rol del usuario conectado.
      - Conexión WebSocket en segundo plano para actualizaciones en vivo.
      - Consultas a SQLite para tarjetas, tablas y gráfica histórica.
    """

    # Control interno para evitar múltiples conexiones WebSocket simultáneas
    _id_streaming_actual: int = 0

    # Listas que alimentan las tablas del catálogo y el historial reciente
    parcelas: list[list[str]] = []
    sensores: list[list[str]] = []
    lecturas: list[list[str]] = []

    # Datos de sesión y selección activa en la pestaña "Lecturas en Vivo"
    rol_usuario: str = ""
    parcela_seleccionada: str = "Parcela Norte"

    # Valores formateados para los indicadores circulares de microclima
    temp_amb: str = "-- ºC"
    temp_suelo: str = "-- ºC"
    lux: str = "-- Lux"
    ph: str = "-- pH"
    humedad: str = "-- %"

    # Variables de estado para la pestaña "Evolución (Gráfica)"
    datos_grafica: List[Dict[str, Any]] = []
    grafica_parcela: str = "Parcela Norte"
    grafica_tipo: str = "temperaturaAmb"
    grafica_limite: str = "50"
    valor_medio: str = "0.0"  # Se guarda como str porque ReferenceLine.y de Recharts exige str | int

    # Opciones disponibles en los desplegables de filtrado de la gráfica
    opciones_parcelas: list[str] = [
        "Parcela Norte",
        "Parcela Sur",
        "Invernadero Principal",
        "Viñedo Este",
        "Huerto Central"
    ]
    opciones_tipos: list[str] = [
        "temperaturaAmb",
        "humedadSuelo",
        "luminosidad",
        "temperaturaSuelo",
        "ph"
    ]
    opciones_limites: list[str] = ["10", "20", "30", "50"]

    def comprobar_acceso(self):
        """
        Se ejecuta al cargar /panel (on_load).
        Verifica que haya un usuario autenticado, consulta su rol en SQLite,
        carga los datos iniciales y arranca el flujo en tiempo real.
        """
        if self.usuario_actual == "":
            return rx.redirect("/")
        else:
            try:
                with sqlite3.connect(RUTA_DB) as conexion:
                    cursor = conexion.cursor()
                    cursor.execute("SELECT role FROM users WHERE username = ?", (self.usuario_actual,))
                    resultado = cursor.fetchone()
                    if resultado:
                        self.rol_usuario = resultado[0]
                    else:
                        self.rol_usuario = "usuario"
            except sqlite3.Error:
                self.rol_usuario = "usuario"

            self.obtener_datos()
            return EstadoAgrotech.iniciar_streaming

    def set_parcela_seleccionada(self, valor: str):
        """Cambia la parcela activa, refresca sus métricas y reconecta el WebSocket."""
        self.parcela_seleccionada = valor
        self.obtener_datos()
        return EstadoAgrotech.iniciar_streaming

    # --- Setters de los filtros de la gráfica ---
    def set_grafica_parcela(self, valor: str):
        self.grafica_parcela = valor
        self.actualizar_grafica()

    def set_grafica_tipo(self, valor: str):
        self.grafica_tipo = valor
        self.actualizar_grafica()

    def set_grafica_limite(self, valor: str):
        self.grafica_limite = valor
        self.actualizar_grafica()

    def actualizar_grafica(self):
        """
        Consulta en SQLite las últimas N lecturas del sensor seleccionado en los filtros,
        las ordena cronológicamente y calcula el valor medio para la línea de referencia.
        """
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()

                # Construye el identificador real del sensor (ej. "p2_humedad")
                p_id = MAPA_PARCELAS.get(self.grafica_parcela, 1)
                s_suffix = MAPA_TIPOS.get(self.grafica_tipo, "temp_amb")
                target_sensor_id = f"p{p_id}_{s_suffix}"

                # Obtiene los últimos registros y los invierte para pintarlos de izquierda a derecha
                query = """
                    SELECT timestamp, value
                    FROM sensor_data
                    WHERE sensor_id = ?
                    ORDER BY id DESC LIMIT ?
                """
                cursor.execute(query, (target_sensor_id, int(self.grafica_limite)))
                datos_raw = list(reversed(cursor.fetchall()))

                grafica_formateada = []
                suma = 0.0

                for fila in datos_raw:
                    # Extrae únicamente la hora (HH:MM:SS) de la marca temporal ISO
                    fecha_cruda_g = str(fila[0]) if fila[0] else ""
                    hora = fecha_cruda_g[11:19] if len(fecha_cruda_g) >= 19 else fecha_cruda_g
                    valor_g = float(fila[1]) if fila[1] is not None else 0.0

                    suma += valor_g
                    grafica_formateada.append({
                        "hora": hora,
                        "Valor": valor_g
                    })

                self.datos_grafica = grafica_formateada

                # Calcula la media redondeada a 2 decimales y la convierte a texto
                media_calculada = round(suma / len(datos_raw), 2) if len(datos_raw) > 0 else 0.0
                self.valor_medio = str(media_calculada)

        except sqlite3.Error as e:
            print(f"Error al actualizar gráfica: {e}")
            self.datos_grafica = []
            self.valor_medio = "0.0"

    @rx.event(background=True)
    async def iniciar_streaming(self):
        """
        Tarea asíncrona en segundo plano que escucha el servidor WebSocket (puerto 8001)
        para la parcela activa. Cada vez que llega un paquete nuevo, refresca la interfaz.
        """
        async with self:
            id_parcela = MAPA_PARCELAS.get(self.parcela_seleccionada, 1)
            # Evita abrir un segundo hilo si ya estamos escuchando esa misma parcela
            if self._id_streaming_actual == id_parcela:
                return
            self._id_streaming_actual = id_parcela

        uri = f"ws://localhost:8001/ws/parcels/{id_parcela}"

        try:
            async with websockets.connect(uri) as websocket:
                while True:
                    # Si el usuario cambió de parcela, detenemos este bucle antiguo
                    async with self:
                        if self._id_streaming_actual != id_parcela:
                            break

                    mensaje = await websocket.recv()

                    # Al recibir notificación del servidor, actualizamos los datos en pantalla
                    async with self:
                        self.obtener_datos()

        except Exception as e:
            print(f"Streaming desconectado de parcela {id_parcela}: {e}")
            async with self:
                self._id_streaming_actual = 0

    def obtener_datos(self):
        """
        Sincroniza el estado con la base de datos:
          1. Carga el listado de parcelas registradas.
          2. Define el catálogo de tipos de sensores.
          3. Obtiene las últimas 15 lecturas globales con código de color térmico.
          4. Carga la última lectura de cada sensor de la parcela seleccionada.
          5. Refresca también los datos de la gráfica.
        """
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()

                # 1. Listado de parcelas (con respaldo estático si la tabla está vacía)
                cursor.execute("SELECT id, name, location FROM parcels ORDER BY id ASC")
                filas_parcelas = cursor.fetchall()
                if filas_parcelas:
                    self.parcelas = [[str(col) if col is not None else "" for col in row] for row in filas_parcelas]
                else:
                    self.parcelas = [
                        ["1", "Parcela Norte", "Sector A"],
                        ["2", "Parcela Sur", "Sector B"],
                        ["3", "Invernadero Principal", "Sector C"],
                        ["4", "Viñedo Este", "Sector D"],
                        ["5", "Huerto Central", "Sector E"]
                    ]

                # 2. Catálogo descriptivo de sensores por parcela
                self.sensores = [
                    ["p#_humedad", "humedadSuelo", "%", "Sensor Humedad Suelo"],
                    ["p#_lux", "luminosidad", "lux", "Sensor Luz Solar"],
                    ["p#_ph", "ph", "pH", "Sensor pH Suelo"],
                    ["p#_temp_amb", "temperaturaAmb", "ºC", "Sensor Temp. Ambiente"],
                    ["p#_temp_suelo", "temperaturaSuelo", "ºC", "Sensor Temp. Suelo"]
                ]

                # 3. Últimas 15 lecturas recibidas para la tabla inferior
                cursor.execute("""
                    SELECT sensor_id, timestamp, value
                    FROM sensor_data
                    ORDER BY id DESC LIMIT 15
                """)
                datos_brutos = cursor.fetchall()
                datos_formateados = []

                for fila in datos_brutos:
                    sensor = str(fila[0]) if fila[0] else "Desconocido"
                    fecha_cruda = str(fila[1]) if fila[1] else ""
                    fecha_limpia = fecha_cruda[:19].replace('T', ' ') if len(fecha_cruda) >= 19 else fecha_cruda
                    valor_real = float(fila[2]) if fila[2] is not None else 0.0

                    # Código de color para alertas visuales de temperatura (>30ºC cálido, <20ºC frío)
                    color_texto = "var(--gray-12)"
                    if "temp" in sensor:
                        if valor_real > 30:
                            color_texto = "#ff8da1"
                        elif valor_real < 20:
                            color_texto = "#82b1ff"
                        else:
                            color_texto = "#66cdaa"

                    datos_formateados.append([sensor, fecha_limpia, str(valor_real), color_texto])

                self.lecturas = datos_formateados

                # 4. Último valor registrado por cada sensor de la parcela seleccionada
                p_id = MAPA_PARCELAS.get(self.parcela_seleccionada, 1)
                cursor.execute("""
                    SELECT sensor_id, value FROM sensor_data
                    WHERE sensor_id LIKE ? AND id IN (
                        SELECT MAX(id) FROM sensor_data GROUP BY sensor_id
                    )
                """, (f"p{p_id}_%",))
                ultimos_datos = dict(cursor.fetchall())

                self.temp_amb = f"{ultimos_datos.get(f'p{p_id}_temp_amb', '--')} ºC"
                self.temp_suelo = f"{ultimos_datos.get(f'p{p_id}_temp_suelo', '--')} ºC"
                self.humedad = f"{ultimos_datos.get(f'p{p_id}_humedad', '--')} %"
                self.lux = f"{ultimos_datos.get(f'p{p_id}_lux', '--')} Lux"
                self.ph = f"{ultimos_datos.get(f'p{p_id}_ph', '--')} pH"

                # 5. Actualización sincronizada de la gráfica
                self.actualizar_grafica()

        except sqlite3.Error as e:
            print(f"Error en la base de datos: {e}")


# ==============================================================================
# 3. COMPONENTES VISUALES DE MÉTRICAS EN VIVO
# ==============================================================================

def tarjeta_metrica_circular(titulo: str, valor: str, icono: str, color_borde: str) -> rx.Component:
    """Renderiza un indicador circular individual con icono, valor y borde coloreado."""
    return rx.vstack(
        rx.text(titulo, weight="bold", size="2", color="var(--gray-11)"),
        rx.center(
            rx.vstack(
                rx.icon(tag=icono, size=28, color=color_borde),
                rx.text(valor, weight="bold", size="4", color="var(--gray-12)"),
                align="center",
                justify="center",
                spacing="1"
            ),
            width="135px",
            height="135px",
            border_radius="50%",
            border=f"3px solid {color_borde}",
            box_shadow="0 6px 16px rgba(0,0,0,0.04)",
            background_color="var(--gray-2)",
        ),
        align="center",
        spacing="2"
    )


def vista_boceto_parcelas() -> rx.Component:
    """Contenedor superior con el selector de parcela y las 5 tarjetas de microclima."""
    return rx.vstack(
        # Cabecera con desplegable de selección de parcela
        rx.hstack(
            rx.hstack(
                rx.heading("PARCELA:", size="3", color="var(--gray-12)", weight="bold"),
                rx.select(
                    list(MAPA_PARCELAS.keys()),
                    value=EstadoAgrotech.parcela_seleccionada,
                    on_change=EstadoAgrotech.set_parcela_seleccionada,
                    variant="soft",
                    size="2"
                ),
                align="center",
                spacing="3"
            ),
            rx.text("Métricas de Suelo y Microclima", size="2", color="var(--gray-11)"),
            width="100%",
            justify="between",
            align="center",
            padding_bottom="1.2em",
            border_bottom="1px solid var(--gray-5)",
            margin_bottom="1.5em"
        ),
        # Fila flexible con los 5 indicadores circulares
        rx.flex(
            tarjeta_metrica_circular("Tª Ambiente", EstadoAgrotech.temp_amb, "thermometer", "#ff8da1"),
            tarjeta_metrica_circular("Tª Suelo", EstadoAgrotech.temp_suelo, "sprout", "#82b1ff"),
            tarjeta_metrica_circular("Luminosidad", EstadoAgrotech.lux, "sun", "#ffd54f"),
            tarjeta_metrica_circular("pH Suelo", EstadoAgrotech.ph, "flask-conical", "#b39ddb"),
            tarjeta_metrica_circular("Humedad (Hº)", EstadoAgrotech.humedad, "droplets", "#4dd0e1"),
            wrap="wrap",
            justify="center",
            spacing="5",
            width="100%"
        ),
        width="100%",
        padding="1.8em",
        border="1px solid var(--gray-5)",
        border_radius="20px",
        background_color="var(--gray-2)",
        box_shadow="0 4px 20px rgba(0, 0, 0, 0.03)",
        margin_top="1.5em",
        margin_bottom="1em"
    )


# ==============================================================================
# 4. COMPONENTE DE GRÁFICA INTERACTIVA (RECHARTS)
# ==============================================================================

def vista_grafica() -> rx.Component:
    """
    Tarjeta de la pestaña 'Evolución (Gráfica)':
      - 3 selectores de filtro (Parcela, Métrica y Límite de lecturas).
      - Indicador numérico de la media del periodo.
      - Gráfica lineal Recharts con línea de media y scroll horizontal para 50 puntos.
    """
    return rx.card(
        rx.vstack(
            rx.heading("Evolución de Métricas", size="4", color="var(--gray-12)"),
            rx.text(
                "Filtra los datos históricos por parcela y tipo de métrica",
                size="2",
                color="var(--gray-11)",
                margin_bottom="1em"
            ),

            # Barra de filtros de la gráfica
            rx.hstack(
                rx.vstack(
                    rx.text("Parcela", size="1", weight="bold", color="var(--gray-12)"),
                    rx.select(
                        EstadoAgrotech.opciones_parcelas,
                        value=EstadoAgrotech.grafica_parcela,
                        on_change=EstadoAgrotech.set_grafica_parcela,
                        variant="soft"
                    ),
                    align="start"
                ),
                rx.vstack(
                    rx.text("Métrica", size="1", weight="bold", color="var(--gray-12)"),
                    rx.select(
                        EstadoAgrotech.opciones_tipos,
                        value=EstadoAgrotech.grafica_tipo,
                        on_change=EstadoAgrotech.set_grafica_tipo,
                        variant="soft"
                    ),
                    align="start"
                ),
                rx.vstack(
                    rx.text("Últimas lecturas", size="1", weight="bold", color="var(--gray-12)"),
                    rx.select(
                        EstadoAgrotech.opciones_limites,
                        value=EstadoAgrotech.grafica_limite,
                        on_change=EstadoAgrotech.set_grafica_limite,
                        variant="soft"
                    ),
                    align="start"
                ),
                wrap="wrap",
                spacing="5",
                margin_bottom="1.5em",
                width="100%"
            ),

            # Resumen del valor medio calculado
            rx.hstack(
                rx.text("Media actual:", size="2", color="var(--gray-11)"),
                rx.text(EstadoAgrotech.valor_medio, size="3", weight="bold", color="var(--grass-11)"),
                align="center",
                spacing="2",
                margin_bottom="1em",
            ),

            # Contenedor con desplazamiento horizontal para evitar solapamiento de etiquetas
            rx.box(
                rx.recharts.line_chart(
                    rx.recharts.line(
                        data_key="Valor",
                        stroke="#82b1ff",
                        stroke_width=3,
                        dot=True,
                    ),
                    # Línea horizontal discontinua que marca la media
                    rx.recharts.reference_line(
                        y=EstadoAgrotech.valor_medio,
                        stroke="var(--grass-9)",
                        stroke_dasharray="3 3",
                    ),
                    rx.recharts.x_axis(data_key="hora"),
                    rx.recharts.y_axis(domain=["auto", "auto"]),
                    rx.recharts.graphing_tooltip(),
                    data=EstadoAgrotech.datos_grafica,
                    height=320,
                    width="100%",
                    min_width="1200px",
                ),
                width="100%",
                overflow_x="auto",
                padding_bottom="1em"
            ),
            width="100%",
        ),
        width="100%",
        border="1px solid var(--gray-5)",
        background_color="var(--gray-2)",
        box_shadow="0 4px 12px rgba(0, 0, 0, 0.03)",
        border_radius="16px",
        margin_top="1em"
    )


# ==============================================================================
# 5. COMPONENTES DE TABLAS REUTILIZABLES
# ==============================================================================

def crear_tabla(cabeceras: list[str], datos: list[list[str]], render_fila) -> rx.Component:
    """Plantilla genérica de tabla con scroll horizontal y diseño de tarjeta."""
    return rx.card(
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(*[rx.table.column_header_cell(c) for c in cabeceras])
                ),
                rx.table.body(rx.foreach(datos, render_fila)),
                variant="surface",
                size="3",
            ),
            width="100%",
            overflow_x="auto",
        ),
        width="100%",
        border="1px solid var(--gray-5)",
        background_color="var(--gray-2)",
        box_shadow="0 4px 12px rgba(0, 0, 0, 0.03)",
        border_radius="16px"
    )


def fila_parcela(fila: list[str]) -> rx.Component:
    """Renderiza una fila de la tabla 'Listado de Parcelas'."""
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="green", variant="soft")),
        rx.table.cell(rx.text(fila[1], weight="bold", color="var(--gray-12)")),
        rx.table.cell(rx.text(fila[2], color="var(--gray-11)"))
    )


def fila_sensor(fila: list[str]) -> rx.Component:
    """Renderiza una fila de la tabla 'Listado de Sensores'."""
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="blue", variant="soft")),
        rx.table.cell(rx.text(fila[1], weight="bold", color="var(--gray-12)")),
        rx.table.cell(rx.text(fila[2], color="var(--gray-11)")),
        rx.table.cell(rx.text(fila[3], color="var(--gray-11)"))
    )


def fila_lectura(fila: list[str]) -> rx.Component:
    """
    Renderiza una fila de la tabla 'Lecturas en Vivo', añadiendo dinámicamente
    la unidad de medida según el nombre del sensor.
    """
    unidad = rx.cond(
        fila[0].contains("temp"),
        " ºC",
        rx.cond(
            fila[0].contains("humedad"),
            " %",
            rx.cond(
                fila[0].contains("lux"),
                " lux",
                rx.cond(fila[0].contains("ph"), " pH", "")
            )
        )
    )

    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="blue", variant="soft")),
        rx.table.cell(rx.text(fila[1], size="2", color="var(--gray-11)")),
        rx.table.cell(rx.text(fila[2] + unidad, weight="bold", color=fila[3])),
        rx.table.cell(rx.badge("Recibido", color_scheme="grass", variant="soft"))
    )


# ==============================================================================
# 6. INTERFAZ PRINCIPAL DEL PANEL (/panel)
# ==============================================================================

def index() -> rx.Component:
    """Construye la página principal completa: estilos, navbar, cabecera y pestañas."""
    return rx.box(
        # Sobrescritura de tokens de color de Radix UI para paleta personalizada en modo claro y oscuro
        rx.html("""
            <style>
                :root, .light, .light-theme {
                    --gray-1: #F4F7F8 !important;
                    --gray-2: #EBF0F2 !important;
                    --gray-3: #E1E8EC !important;
                    --gray-4: #D3DEE3 !important;
                    --gray-5: #C5D4DC !important;
                    --gray-11: #4A636E !important;
                    --gray-12: #1A2E35 !important;
                }
                .dark, .dark-theme, [data-theme="dark"] {
                    --gray-1: #0D2F3A !important;
                    --gray-2: #09242E !important;
                    --gray-3: #123C4A !important;
                    --gray-4: #174859 !important;
                    --gray-5: #1D566B !important;
                    --gray-6: #24657D !important;
                    --gray-11: #8FB4C2 !important;
                    --gray-12: #E2F1F5 !important;
                }
            </style>
        """),

        # --- BARRA DE NAVEGACIÓN SUPERIOR (NAVBAR) ---
        rx.hstack(
            # Logotipo y título
            rx.hstack(
                rx.icon(tag="leaf", color="var(--grass-9)", size=30),
                rx.heading("Catálogo Agrotech", size="5", color="var(--grass-11)", weight="bold"),
                align_items="center",
                spacing="3"
            ),

            # Selector de tema y menú desplegable de usuario
            rx.hstack(
                rx.color_mode.button(),

                rx.menu.root(
                    rx.menu.trigger(
                        rx.hstack(
                            rx.avatar(
                                fallback=BaseState.usuario_actual[:1].upper(),
                                size="1",
                                color_scheme="grass",
                                variant="solid"
                            ),
                            rx.vstack(
                                rx.text(BaseState.usuario_actual, weight="bold", size="2", color="var(--gray-12)"),
                                rx.text(
                                    rx.match(
                                        EstadoAgrotech.rol_usuario,
                                        ("administrador", "Administrador"),
                                        ("tecnico_agricola", "Técnico Agrícola"),
                                        "Usuario"
                                    ),
                                    size="1",
                                    color="var(--grass-10)"
                                ),
                                spacing="0",
                                align_items="start"
                            ),
                            padding="0.35em 0.75em",
                            border_radius="12px",
                            background_color="var(--gray-3)",
                            border="1px solid var(--gray-5)",
                            align_items="center",
                            spacing="2",
                            cursor="pointer",
                            _hover={"background_color": "var(--gray-4)"}
                        )
                    ),
                    # Opciones del menú condicionadas según el rol del usuario
                    rx.menu.content(
                        rx.cond(
                            EstadoAgrotech.rol_usuario == "administrador",
                            rx.menu.item(
                                rx.icon("users", size=16),
                                "Gestión de usuarios",
                                on_click=rx.redirect("/gestor-usuarios")
                            )
                        ),
                        rx.cond(
                            (EstadoAgrotech.rol_usuario == "administrador") | (EstadoAgrotech.rol_usuario == "tecnico_agricola"),
                            rx.menu.item(
                                rx.icon("map-pin", size=16),
                                "Gestión de parcelas",
                                on_click=rx.redirect("/gestor-parcelas")
                            )
                        ),
                        rx.cond(
                            (EstadoAgrotech.rol_usuario == "administrador") | (EstadoAgrotech.rol_usuario == "tecnico_agricola"),
                            rx.menu.separator()
                        ),
                        rx.menu.item(
                            rx.icon("log-out", size=16),
                            "Cerrar Sesión",
                            on_click=BaseState.cerrar_sesion,
                            color="red"
                        )
                    )
                ),
                spacing="4",
                align_items="center",
            ),
            justify_content="space-between",
            align_items="center",
            width="100%",
            padding="0.8em 2em",
            border_bottom="1px solid var(--gray-5)",
            background_color="var(--gray-2)",
        ),

        # --- CONTENEDOR CENTRAL DEL DASHBOARD ---
        rx.vstack(
            # Cabecera de sección e indicador visual de WebSocket activo
            rx.hstack(
                rx.vstack(
                    rx.heading("Monitorización y Catálogo", size="7", weight="bold", color="var(--gray-12)"),
                    rx.text("Visualiza las parcelas, sensores y los datos en tiempo real.", color="var(--gray-11)", size="2"),
                    align_items="start",
                    spacing="1"
                ),
                rx.spacer(),

                rx.hstack(
                    rx.box(width="8px", height="8px", border_radius="50%", background_color="var(--grass-9)"),
                    rx.text("Transmisión en Vivo", size="2", weight="medium", color="var(--grass-11)"),
                    padding="0.4em 0.9em",
                    border_radius="20px",
                    border="1px solid var(--grass-6)",
                    background_color="var(--gray-2)",
                    align_items="center",
                    spacing="2"
                ),

                # Botón oculto auxiliar para forzar recarga manual si fuese necesario
                rx.button(
                    "Actualizar Datos",
                    id="btn-actualizar",
                    on_click=EstadoAgrotech.obtener_datos,
                    display="none",
                ),

                width="100%",
                align_items="center",
                flex_direction=["column", "row"],
                spacing="4",
                margin_bottom="1.5em"
            ),

            # Sistema de pestañas de navegación del panel
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Lecturas en Vivo", value="lecturas"),
                    rx.tabs.trigger("Evolución (Gráfica)", value="grafica"),
                    rx.tabs.trigger("Listado de Parcelas", value="parcelas"),
                    rx.tabs.trigger("Listado de Sensores", value="sensores"),
                    size="2",
                ),
                rx.tabs.content(
                    rx.vstack(
                        vista_boceto_parcelas(),
                        crear_tabla(["ID Sensor", "Fecha / Hora", "Valor", "Estado"], EstadoAgrotech.lecturas, fila_lectura),
                        spacing="4",
                        width="100%"
                    ),
                    value="lecturas",
                ),
                rx.tabs.content(
                    vista_grafica(),
                    value="grafica",
                ),
                rx.tabs.content(
                    crear_tabla(["ID Parcela", "Nombre", "Ubicación"], EstadoAgrotech.parcelas, fila_parcela),
                    value="parcelas",
                ),
                rx.tabs.content(
                    crear_tabla(["ID Sensor", "Tipo", "Unidad", "Descripción"], EstadoAgrotech.sensores, fila_sensor),
                    value="sensores",
                ),
                default_value="lecturas",
                width="100%",
            ),

            width=["100%", "95%", "85%", "1200px"],
            margin="0 auto",
            padding="2em 1em",
        ),
        width="100%",
        min_height="100vh",
        background_color="var(--gray-1)",
    )


# ==============================================================================
# 7. CONFIGURACIÓN DE LA APP Y REGISTRO DE RUTAS
# ==============================================================================

app = rx.App()
app.add_page(login_page, route="/", title="Login | Agrotech")
app.add_page(index, route="/panel", on_load=EstadoAgrotech.comprobar_acceso, title="Panel Agrotech")
app.add_page(panel_gestor_usuarios, route="/gestor-usuarios", on_load=GestorUsuariosState.comprobar_acceso_admin, title="Gestor de Usuarios")
app.add_page(panel_gestor_parcelas, route="/gestor-parcelas", on_load=GestorParcelasState.comprobar_acceso_parcelas, title="Gestión de Parcelas")