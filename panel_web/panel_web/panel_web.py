import reflex as rx
import sqlite3
import os

# --- CONFIGURACIÓN DE RUTAS SEGURAS ---
DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")

# 1. INICIALIZACIÓN DE DATOS DE EJEMPLO
def poblar_base_datos():
    try:
        with sqlite3.connect(RUTA_DB) as conexion:
            cursor = conexion.cursor()
            
            cursor.execute("CREATE TABLE IF NOT EXISTS parcels (id INTEGER PRIMARY KEY, name TEXT, location TEXT)")
            cursor.execute("SELECT COUNT(*) FROM parcels")
            if cursor.fetchone()[0] == 0:
                cursor.executescript("""
                    INSERT INTO parcels (name, location) VALUES ('Parcela Norte', 'Sector A');
                    INSERT INTO parcels (name, location) VALUES ('Parcela Sur', 'Sector B');
                    INSERT INTO parcels (name, location) VALUES ('Invernadero Principal', 'Sector C');
                    INSERT INTO parcels (name, location) VALUES ('Viñedo Este', 'Sector D');
                    INSERT INTO parcels (name, location) VALUES ('Huerto Central', 'Sector E');
                """)
                
            cursor.execute("CREATE TABLE IF NOT EXISTS sensors (id TEXT PRIMARY KEY, parcel_id INTEGER, type TEXT, unit TEXT, description TEXT)")
            cursor.execute("SELECT COUNT(*) FROM sensors")
            if cursor.fetchone()[0] == 0:
                cursor.executescript("""
                    INSERT INTO sensors (id, parcel_id, type, unit, description) VALUES ('t001', 1, 'temperaturaAmb', 'ºC', 'Sensor de temperatura ambiente');
                    INSERT INTO sensors (id, parcel_id, type, unit, description) VALUES ('h001', 1, 'humedad_suelo', '%', 'Sensor de humedad del suelo');
                    INSERT INTO sensors (id, parcel_id, type, unit, description) VALUES ('l001', 2, 'luminosidad', 'lux', 'Sensor de luz solar');
                    INSERT INTO sensors (id, parcel_id, type, unit, description) VALUES ('t002', 3, 'temperaturaInt', 'ºC', 'Temperatura interior invernadero');
                    INSERT INTO sensors (id, parcel_id, type, unit, description) VALUES ('ph01', 4, 'ph', 'pH', 'Sensor de acidez del suelo');
                """)

            cursor.execute("CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, sensor_id TEXT, timestamp TEXT, type TEXT, message TEXT, acknowledged INTEGER)")
            cursor.execute("SELECT COUNT(*) FROM alerts")
            if cursor.fetchone()[0] == 0:
                cursor.executescript("""
                    INSERT INTO alerts (sensor_id, timestamp, type, message, acknowledged) 
                    VALUES ('t001', '2026-10-24T10:15:00Z', 'HIGH', 'Temperatura crítica superada', 0);
                    INSERT INTO alerts (sensor_id, timestamp, type, message, acknowledged) 
                    VALUES ('h001', '2026-10-24T11:20:00Z', 'LOW', 'Humedad por debajo del umbral', 1);
                """)
    except sqlite3.Error as e:
        print(f"Error al poblar BD: {e}")

poblar_base_datos()

# 2. GESTIÓN DEL ESTADO
class EstadoAgrotech(rx.State):
    parcelas: list[list[str]] = []
    sensores: list[list[str]] = []
    lecturas: list[list[str]] = []

    def obtener_datos(self):
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                
                cursor.execute("SELECT id, name, location FROM parcels ORDER BY id ASC LIMIT 5")
                self.parcelas = [[str(col) if col is not None else "" for col in row] for row in cursor.fetchall()]
                
                cursor.execute("SELECT id, type, unit, description FROM sensors ORDER BY id ASC LIMIT 5")
                self.sensores = [[str(col) if col is not None else "" for col in row] for row in cursor.fetchall()]
                
                cursor.execute("SELECT sensor_id, timestamp, value FROM sensor_data ORDER BY id DESC LIMIT 15")
                datos_brutos = cursor.fetchall()
                datos_formateados = []
                
                for fila in datos_brutos:
                    sensor = str(fila[0]) if fila[0] else "Desconocido"
                    
                    fecha_cruda = str(fila[1]) if fila[1] else ""
                    fecha_limpia = fecha_cruda[:19].replace('T', ' ') if len(fecha_cruda) >= 19 else fecha_cruda
                    
                    valor_real = float(fila[2]) if fila[2] is not None else 0.0
                    valor_str = str(valor_real)
                    
                    # Colores en tonos pastel
                    color_texto = "var(--gray-12)"
                    if sensor in ["t001", "t002"]:
                        if valor_real > 30:
                            color_texto = "#ff8da1" # Rojo pastel
                        elif valor_real < 20:
                            color_texto = "#82b1ff" # Azul pastel
                        else:
                            color_texto = "#66cdaa" # Verde pastel
                            
                    datos_formateados.append([sensor, fecha_limpia, valor_str, color_texto])
                    
                self.lecturas = datos_formateados
                
        except sqlite3.Error as e:
            print(f"Error en la base de datos: {e}")

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
        box_shadow="0 4px 6px -1px rgb(0 0 0 / 0.1)",
        margin_top="1em"
    )

def fila_parcela(fila: list[str]) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="green")),
        rx.table.cell(rx.text(fila[1], weight="bold")),
        rx.table.cell(rx.text(fila[2]))
    )

def fila_sensor(fila: list[str]) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="blue")),
        rx.table.cell(rx.text(fila[1], weight="bold")),
        rx.table.cell(rx.text(fila[2])),
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
        rx.table.cell(rx.badge("Recibido", color_scheme="grass"))
    )

# 4. INTERFAZ PRINCIPAL
def index() -> rx.Component:
    return rx.box(
        rx.script("setInterval(() => { const btn = document.getElementById('btn-actualizar'); if(btn) btn.click(); }, 5000);"),
        
        rx.hstack(
            rx.hstack(
                rx.icon(tag="leaf", color="var(--grass-9)", size=32),
                rx.heading("Catálogo Agrotech", size="6", color="var(--grass-11)"),
                align_items="center",
                spacing="3"
            ),
            rx.color_mode.button(), 
            justify_content="space-between",
            align_items="center",
            width="100%",
            padding="1em 2em",
            border_bottom="1px solid var(--gray-5)",
            background_color="var(--gray-2)",
        ),
        
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Monitorización y Catálogo", size="7"),
                    rx.text("Visualiza las parcelas, sensores y los datos en tiempo real.", color="var(--gray-11)"),
                    align_items="start"
                ),
                rx.spacer(),
                
                # --- BOTÓN OCULTO ---
                rx.button(
                    rx.icon(tag="refresh-cw", size=18),
                    "Actualizar Datos", 
                    id="btn-actualizar", 
                    on_click=EstadoAgrotech.obtener_datos, 
                    display="none", # Aquí hacemos que desaparezca visualmente
                ),
                
                width="100%",
                align_items="center",
                flex_direction=["column", "row"], 
                spacing="4",
                margin_bottom="2em"
            ),
            
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Lecturas en Vivo", value="lecturas"),
                    rx.tabs.trigger("Listado de Parcelas", value="parcelas"),
                    rx.tabs.trigger("Listado de Sensores", value="sensores"),
                    size="2",
                ),
                rx.tabs.content(
                    crear_tabla(["ID Sensor", "Fecha / Hora", "Valor", "Estado"], EstadoAgrotech.lecturas, fila_lectura),
                    value="lecturas",
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

# 5. CONFIGURACIÓN
app = rx.App(
    theme=rx.theme(
        appearance="light",
        has_background=True,
        radius="medium",
        accent_color="grass",
    )
)
app.add_page(index, on_load=EstadoAgrotech.obtener_datos, title="Panel Agrotech")