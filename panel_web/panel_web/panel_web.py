import reflex as rx
import sqlite3
import os
from .login import login_page, BaseState

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")

# 1. ESTADO DEL PANEL Y OBTENCIÓN DINÁMICA DE DATOS
class EstadoAgrotech(BaseState):
    parcelas: list[list[str]] = []
    sensores: list[list[str]] = []
    lecturas: list[list[str]] = []
    
    parcela_seleccionada: str = "Parcela Norte"
    
    # Métricas dinámicas
    temp_amb: str = "24.5 ºC"
    temp_suelo: str = "19.2 ºC"
    lux: str = "12500 Lux"
    ph: str = "6.5 pH"
    humedad: str = "68 %"

    def comprobar_acceso(self):
        if self.usuario_actual == "":
            return rx.redirect("/")
        self.obtener_datos()

    def set_parcela_seleccionada(self, valor: str):
        self.parcela_seleccionada = valor
        
        multiplicador = 1.0
        if "Sur" in valor:
            multiplicador = 1.15
        elif "Invernadero" in valor:
            multiplicador = 1.25
        elif "Viñedo" in valor:
            multiplicador = 0.90
        elif "Huerto" in valor:
            multiplicador = 1.05

        self.temp_amb = f"{round(24.5 * multiplicador, 1)} ºC"
        self.temp_suelo = f"{round(19.2 * multiplicador, 1)} ºC"
        self.lux = f"{int(12500 * multiplicador)} Lux"
        self.ph = f"{round(6.5 * (0.98 if multiplicador > 1 else 1.02), 1)} pH"
        self.humedad = f"{int(68 * multiplicador)} %"
        
        self.obtener_datos()

    def obtener_datos(self):
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                
                cursor.execute("SELECT id, name, location FROM parcels ORDER BY id ASC LIMIT 5")
                self.parcelas = [[str(col) if col is not None else "" for col in row] for row in cursor.fetchall()]
                
                cursor.execute("SELECT id, type, unit, description FROM sensors ORDER BY id ASC LIMIT 5")
                self.sensores = [[str(col) if col is not None else "" for col in row] for row in cursor.fetchall()]
                
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
                    
                    color_texto = "var(--gray-12)"
                    if sensor in ["t001", "t002"]:
                        if valor_real > 30:
                            color_texto = "#ff8da1"
                        elif valor_real < 20:
                            color_texto = "#82b1ff"
                        else:
                            color_texto = "#66cdaa"
                            
                    datos_formateados.append([sensor, fecha_limpia, str(valor_real), color_texto])
                
                self.lecturas = datos_formateados if datos_formateados else [
                    ["t001", "2026-11-04 12:30:00", "24.5", "#66cdaa"],
                    ["h001", "2026-11-04 12:29:45", "68.0", "var(--gray-12)"],
                    ["l001", "2026-11-04 12:28:10", "12500", "var(--gray-12)"],
                    ["ph01", "2026-11-04 12:25:00", "6.5", "var(--gray-12)"],
                    ["t002", "2026-11-04 12:20:00", "19.2", "#82b1ff"],
                ]

        except sqlite3.Error as e:
            print(f"Error en la base de datos: {e}")

# 2. COMPONENTES CIRCULARES USANDO TOKENS ADAPTATIVOS
def tarjeta_metrica_circular(titulo: str, valor: str, icono: str, color_borde: str) -> rx.Component:
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
    return rx.vstack(
        rx.hstack(
            rx.hstack(
                rx.heading("PARCELA:", size="3", color="var(--gray-12)", weight="bold"),
                rx.select(
                    ["Parcela Norte", "Parcela Sur", "Invernadero Principal", "Viñedo Este", "Huerto Central"],
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

# 3. COMPONENTES DE TABLAS
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
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="green", variant="soft")),
        rx.table.cell(rx.text(fila[1], weight="bold", color="var(--gray-12)")),
        rx.table.cell(rx.text(fila[2], color="var(--gray-11)"))
    )

def fila_sensor(fila: list[str]) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="blue", variant="soft")),
        rx.table.cell(rx.text(fila[1], weight="bold", color="var(--gray-12)")),
        rx.table.cell(rx.text(fila[2], color="var(--gray-11)")),
        rx.table.cell(rx.text(fila[3], color="var(--gray-11)"))
    )

def fila_lectura(fila: list[str]) -> rx.Component:
    valor_con_unidad = rx.match(
        fila[0],
        ("t001", fila[2] + " ºC"),
        ("t002", fila[2] + " ºC"),
        ("h001", fila[2] + " %"),
        ("l001", fila[2] + " lux"),
        ("ph01", fila[2] + " pH"),
        fila[2]
    )

    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="blue", variant="soft")),
        rx.table.cell(rx.text(fila[1], size="2", color="var(--gray-11)")),
        rx.table.cell(rx.text(valor_con_unidad, weight="bold", color=fila[3])),
        rx.table.cell(rx.badge("Recibido", color_scheme="grass", variant="soft"))
    )

# 4. INTERFAZ PRINCIPAL
def index() -> rx.Component:
    return rx.box(
        # Inyección de estilos: Modo Claro en grises mate confortables + Modo Oscuro #0D2F3A
        rx.html("""
            <style>
                :root, .light, .light-theme {
                    --gray-1: #F4F7F8 !important;  /* Fondo general gris suave */
                    --gray-2: #EBF0F2 !important;  /* Tarjetas y Header */
                    --gray-3: #E1E8EC !important;  /* Elementos internos */
                    --gray-4: #D3DEE3 !important;  /* Bordes de interacción */
                    --gray-5: #C5D4DC !important;  /* Separadores */
                    --gray-11: #4A636E !important; /* Texto secundario */
                    --gray-12: #1A2E35 !important; /* Texto principal fácil de leer */
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
        
        # Script de auto-actualización silenciosa en vivo cada 5s
        rx.script("setInterval(() => { const btn = document.getElementById('btn-actualizar'); if(btn) btn.click(); }, 5000);"),
        
        # TOP NAVBAR CON PERFIL DE USUARIO
        rx.hstack(
            rx.hstack(
                rx.icon(tag="leaf", color="var(--grass-9)", size=30),
                rx.heading("Catálogo Agrotech", size="5", color="var(--grass-11)", weight="bold"),
                align_items="center",
                spacing="3"
            ),
            
            rx.hstack(
                rx.color_mode.button(),
                
                # Tarjeta del perfil de usuario
                rx.hstack(
                    rx.avatar(
                        fallback=BaseState.usuario_actual[0].upper(),
                        size="1",
                        color_scheme="grass",
                        variant="solid"
                    ),
                    rx.vstack(
                        rx.text(BaseState.usuario_actual, weight="bold", size="2", color="var(--gray-12)"),
                        rx.text("Conectado", size="1", color="var(--grass-10)"),
                        spacing="0",
                        align_items="start"
                    ),
                    padding="0.35em 0.75em",
                    border_radius="12px",
                    background_color="var(--gray-3)",
                    border="1px solid var(--gray-5)",
                    align_items="center",
                    spacing="2"
                ),
                
                rx.button(
                    rx.icon(tag="log-out", size=16),
                    "Cerrar Sesión",
                    on_click=BaseState.cerrar_sesion,
                    color_scheme="red",
                    variant="ghost",
                    size="2"
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
        
        # MAIN CONTAINER
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Monitorización y Catálogo", size="7", weight="bold", color="var(--gray-12)"),
                    rx.text("Visualiza las parcelas, sensores y los datos en tiempo real.", color="var(--gray-11)", size="2"),
                    align_items="start",
                    spacing="1"
                ),
                rx.spacer(),
                
                # Indicador de Transmisión en Vivo
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
            
            # PESTAÑAS Y CONTENIDO
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Lecturas en Vivo", value="lecturas"),
                    rx.tabs.trigger("Listado de Parcelas", value="parcelas"),
                    rx.tabs.trigger("Listado de Sensores", value="sensores"),
                    size="2",
                ),
                # Pestaña 1: Visores circulares arriba + Tabla de Lecturas
                rx.tabs.content(
                    rx.vstack(
                        vista_boceto_parcelas(),
                        crear_tabla(["ID Sensor", "Fecha / Hora", "Valor", "Estado"], EstadoAgrotech.lecturas, fila_lectura),
                        spacing="4",
                        width="100%"
                    ),
                    value="lecturas",
                ),
                # Pestaña 2: Listado de Parcelas
                rx.tabs.content(
                    crear_tabla(["ID Parcela", "Nombre", "Ubicación"], EstadoAgrotech.parcelas, fila_parcela),
                    value="parcelas",
                ),
                # Pestaña 3: Listado de Sensores
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

# 5. CONFIGURACIÓN DE RUTA
app = rx.App()
app.add_page(login_page, route="/", title="Login | Agrotech")
app.add_page(index, route="/panel", on_load=EstadoAgrotech.comprobar_acceso, title="Panel Agrotech")