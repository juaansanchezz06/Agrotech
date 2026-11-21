from funcs.database import obtener_conexion

MAPA_PARCELAS = {
    "Parcela Norte": 1,
    "Parcela Sur": 2,
    "Invernadero Principal": 3,
    "Viñedo Este": 4,
    "Huerto Central": 5,
}

def obtener_todas_parcelas() -> list[dict]:
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute("SELECT id, name, location FROM parcels")
        return [{"id": row[0], "name": row[1], "location": row[2]} for row in cursor.fetchall()]


def obtener_sensores_parcela(parcela_id: int) -> list[dict]:
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        # Corregido: ahora sí se pasa (parcela_id,) como parámetro
        cursor.execute(
            "SELECT id, type, unit, description FROM sensors WHERE parcel_id = ?",
            (parcela_id,),
        )
        return [
            {"id": row[0], "type": row[1], "unit": row[2], "description": row[3]}
            for row in cursor.fetchall()
        ]

def obtener_parcelas_tabla() -> list[list[str]]:
    """Devuelve las parcelas formateadas como lista de filas para las tablas de Reflex."""
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute("SELECT id, name, location FROM parcels ORDER BY id ASC")
        filas = cursor.fetchall()

    if filas:
        return [[str(col) if col is not None else "" for col in row] for row in filas]

    return [
        ["1", "Parcela Norte", "Sector A"],
        ["2", "Parcela Sur", "Sector B"],
        ["3", "Invernadero Principal", "Sector C"],
        ["4", "Viñedo Este", "Sector D"],
        ["5", "Huerto Central", "Sector E"],
    ]