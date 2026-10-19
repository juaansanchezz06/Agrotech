import reflex as rx
import sqlite3

# 1. LA GESTIÓN DEL ESTADO (C.E.3.b)
# Esta es la "memoria" de nuestra web. 
class EstadoAgrotech(rx.State):
    # Empezamos con una lista vacía de temperaturas
    temperaturas: list[list[str]] = []

    def obtener_datos(self):
        # Tu especialidad: Conectamos a la BBDD. 
        # Ponemos '../' porque la base de datos está en la carpeta anterior
        conexion = sqlite3.connect('../agrotech.db')
        cursor = conexion.cursor()
        
        # Sacamos los últimos 10 datos registrados
        cursor.execute("SELECT sensor_id, timestamp, value FROM sensor_data ORDER BY id DESC LIMIT 10")
        
        # Guardamos los datos en la "memoria" de la web
        self.temperaturas = cursor.fetchall()
        conexion.close()

# 2. LA INTERFAZ DECLARATIVA (C.E.3.a y C.E.3.c)
# Le decimos a Reflex QUÉ queremos ver, no CÓMO dibujarlo.
def index() -> rx.Component:
    return rx.vstack(
        rx.heading("🌱 Panel de Control Agrotech", size="8", color="green"),
        rx.text("Monitorización de sensores en tiempo real."),
        
        # Un botón que, al pulsarlo, ejecuta la función de buscar en la BBDD
        rx.button("Actualizar Datos", on_click=EstadoAgrotech.obtener_datos, size="3"),
        
        # Una tabla para mostrar los datos de tu BBDD
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Sensor"),
                    rx.table.column_header_cell("Fecha / Hora"),
                    rx.table.column_header_cell("Temperatura (ºC)"),
                )
            ),
            rx.table.body(
                # Bucle (foreach) que recorre nuestra memoria y pinta una fila por cada dato
                rx.foreach(
                    EstadoAgrotech.temperaturas,
                    lambda fila: rx.table.row(
                        rx.table.cell(fila[0]),
                        rx.table.cell(fila[1]),
                        rx.table.cell(fila[2]),
                    )
                )
            ),
            width="100%",
            variant="surface"
        ),
        
        # Estilos del contenedor principal
        padding="2em",
        align_items="center",
        width="100%"
    )

# Arrancamos la aplicación y le decimos que al cargar la página (on_load) busque los datos
app = rx.App()
app.add_page(index, on_load=EstadoAgrotech.obtener_datos)

