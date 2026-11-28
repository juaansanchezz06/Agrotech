import os

# Subimos un nivel desde funcs/ hasta la raíz de Agrotech
RUTA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_DB = os.path.join(RUTA_RAIZ, "agrotech.db")

TIPOS_SENSORES = ("temp_amb", "temp_suelo", "ph", "lux", "humedad")

# (sufijo, tipo_bd, unidad, col_min, col_max)
DEFINICION_SENSORES: tuple[tuple[str, str, str, str, str], ...] = (
    ("temp_amb", "temperaturaAmb", "ºC", "temp_amb_min", "temp_amb_max"),
    ("temp_suelo", "temperaturaSuelo", "ºC", "temp_suelo_min", "temp_suelo_max"),
    ("ph", "ph", "pH", "ph_min", "ph_max"),
    ("lux", "luminosidad", "lux", "lux_min", "lux_max"),
    ("humedad", "humedadSuelo", "%", "humedad_min", "humedad_max"),
)

MAPA_SUFIJO_METADATOS: dict[str, tuple[str, str, str, str]] = {
    sufijo: (tipo, unidad, c_min, c_max)
    for sufijo, tipo, unidad, c_min, c_max in DEFINICION_SENSORES
}

PARCELAS_INICIALES = [
    ("Parcela Norte", "Sector A", "Maíz", "2.4 ha", 0, "", 15.0, 32.0, 12.0, 28.0, 5.5, 7.5, 200.0, 50000.0, 40.0, 85.0),
    ("Parcela Sur", "Sector B", "Trigo", "3.1 ha", 0, "", 12.0, 30.0, 10.0, 26.0, 6.0, 7.5, 200.0, 50000.0, 35.0, 80.0),
    ("Invernadero Principal", "Sector C", "Tomate", "0.8 ha", 0, "", 18.0, 30.0, 15.0, 26.0, 5.8, 6.8, 300.0, 45000.0, 55.0, 85.0),
    ("Viñedo Este", "Sector D", "Vid", "4.0 ha", 0, "", 14.0, 34.0, 12.0, 28.0, 5.5, 7.5, 300.0, 60000.0, 35.0, 75.0),
    ("Huerto Central", "Sector E", "Hortalizas", "1.2 ha", 0, "", 15.0, 29.0, 13.0, 25.0, 6.0, 7.2, 200.0, 45000.0, 50.0, 85.0),
]