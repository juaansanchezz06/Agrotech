import json
import random
from datetime import datetime
import requests
from funcs.database import obtener_conexion

MAPA_TIPOS = {
    "temperaturaAmb": "temp_amb",
    "humedadSuelo": "humedad",
    "luminosidad": "lux",
    "temperaturaSuelo": "temp_suelo",
    "ph": "ph",
}

CATALOGO_SENSORES = [
    ["p#_humedad", "humedadSuelo", "%", "Sensor Humedad Suelo"],
    ["p#_lux", "luminosidad", "lux", "Sensor Luz Solar"],
    ["p#_ph", "ph", "pH", "Sensor pH Suelo"],
    ["p#_temp_amb", "temperaturaAmb", "ºC", "Sensor Temp. Ambiente"],
    ["p#_temp_suelo", "temperaturaSuelo", "ºC", "Sensor Temp. Suelo"],
]

def inicializar_estado_sensores(parcelas: dict) -> dict:
    """Genera el diccionario con los valores iniciales y rangos de los 5 sensores por parcela."""
    estado = {}
    for p_id in parcelas.keys():
        estado[f"p{p_id}_temp_amb"] = {"val": 23.5, "delta": 0.4, "min": 14.0, "max": 34.0}
        estado[f"p{p_id}_temp_suelo"] = {"val": 18.2, "delta": 0.2, "min": 12.0, "max": 24.0}
        estado[f"p{p_id}_humedad"] = {"val": 65.0, "delta": 1.2, "min": 35.0, "max": 85.0}
        estado[f"p{p_id}_lux"] = {"val": 8500.0, "delta": 250.0, "min": 500.0, "max": 16000.0}
        estado[f"p{p_id}_ph"] = {"val": 6.5, "delta": 0.05, "min": 5.8, "max": 7.4}
    return estado


def generar_lectura_sensor(sensor_id: str, sensor_info: dict) -> dict:
    """Calcula el siguiente valor progresivo dentro de su rango y arma el paquete JSON."""
    variacion = random.uniform(-sensor_info["delta"], sensor_info["delta"])
    decimales = 2 if "ph" in sensor_id else 1
    nuevo_valor = round(sensor_info["val"] + variacion, decimales)

    # Mantener dentro de los rangos lógicos y actualizar el estado en memoria
    nuevo_valor = max(sensor_info["min"], min(sensor_info["max"], nuevo_valor))
    sensor_info["val"] = nuevo_valor

    return {
        "sensor_id": sensor_id,
        "timestamp": datetime.now().astimezone().isoformat(),
        "value": nuevo_valor,
        "raw": json.dumps({"estado_bateria": random.randint(85, 100)}),
    }


def enviar_lectura_api(url_base: str, paquete: dict, timeout: int = 2) -> tuple[bool, int | str]:
    """Envía el paquete de un sensor a la API. Devuelve (exito, codigo_http_o_error)."""
    url_api = f"{url_base}/{paquete['sensor_id']}/data"
    try:
        respuesta = requests.post(url_api, json=paquete, timeout=timeout)
        return True, respuesta.status_code
    except requests.RequestException as e:
        return False, str(e)

def guardar_lectura_db(sensor_id: str, timestamp: str, value: float, raw: str | None = None) -> None:
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute(
            "INSERT INTO sensor_data (sensor_id, timestamp, value, raw) VALUES (?, ?, ?, ?)",
            (sensor_id, timestamp, value, raw),
        )
        conexion.commit()


def obtener_historico_sensor(
    sensor_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
) -> list[dict]:
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        query = "SELECT timestamp, value FROM sensor_data WHERE sensor_id = ?"
        params: list = [sensor_id]

        if from_date:
            query += " AND timestamp >= ?"
            params.append(from_date)
        if to_date:
            query += " AND timestamp <= ?"
            params.append(to_date)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, tuple(params))
        return [{"timestamp": row[0], "value": row[1]} for row in cursor.fetchall()]


def obtener_ultimas_lecturas_parcela(parcela_id: int, limit: int = 5) -> list[dict]:
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT s.id, s.type, sd.value, sd.timestamp
            FROM sensors s
            LEFT JOIN sensor_data sd ON s.id = sd.sensor_id
            WHERE s.parcel_id = ?
            ORDER BY sd.timestamp DESC LIMIT ?
            """,
            (parcela_id, limit),
        )
        return [
            {"sensor": row[0], "tipo": row[1], "valor": row[2], "hora": row[3]}
            for row in cursor.fetchall()
        ]

def obtener_ultimas_lecturas_tabla(limit: int = 15) -> list[list[str]]:
    """Obtiene las últimas lecturas globales formateadas con su color térmico para la tabla."""
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT sensor_id, timestamp, value FROM sensor_data ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        datos_brutos = cursor.fetchall()

    datos_formateados = []
    for fila in datos_brutos:
        sensor = str(fila[0]) if fila[0] else "Desconocido"
        fecha_cruda = str(fila[1]) if fila[1] else ""
        fecha_limpia = fecha_cruda[:19].replace("T", " ") if len(fecha_cruda) >= 19 else fecha_cruda
        valor_real = float(fila[2]) if fila[2] is not None else 0.0

        color_texto = "var(--gray-12)"
        if "temp" in sensor:
            if valor_real > 30:
                color_texto = "#ff8da1"
            elif valor_real < 20:
                color_texto = "#82b1ff"
            else:
                color_texto = "#66cdaa"

        datos_formateados.append([sensor, fecha_limpia, str(valor_real), color_texto])
    return datos_formateados


def obtener_metricas_actuales_parcela(parcela_id: int) -> dict[str, str]:
    """Devuelve los últimos valores formateados de los 5 sensores de una parcela."""
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT sensor_id, value FROM sensor_data
            WHERE sensor_id LIKE ? AND id IN (
                SELECT MAX(id) FROM sensor_data GROUP BY sensor_id
            )
            """,
            (f"p{parcela_id}_%",),
        )
        ultimos = dict(cursor.fetchall())

    return {
        "temp_amb": f"{ultimos.get(f'p{parcela_id}_temp_amb', '--')} ºC",
        "temp_suelo": f"{ultimos.get(f'p{parcela_id}_temp_suelo', '--')} ºC",
        "humedad": f"{ultimos.get(f'p{parcela_id}_humedad', '--')} %",
        "lux": f"{ultimos.get(f'p{parcela_id}_lux', '--')} Lux",
        "ph": f"{ultimos.get(f'p{parcela_id}_ph', '--')} pH",
    }


def obtener_datos_grafica_sensor(
    parcela_id: int,
    sufijo_sensor: str,
    fecha_inicio: str = "",
    fecha_fin: str = "",
) -> tuple[list[dict], str]:
    """Consulta el histórico filtrado por fecha y devuelve (lista_puntos, media_en_texto)."""
    target_sensor_id = f"p{parcela_id}_{sufijo_sensor}"
    condiciones = ["sensor_id = ?"]
    parametros: list = [target_sensor_id]

    if fecha_inicio:
        condiciones.append("substr(timestamp, 1, 10) >= ?")
        parametros.append(fecha_inicio)
    if fecha_fin:
        condiciones.append("substr(timestamp, 1, 10) <= ?")
        parametros.append(fecha_fin)

    query = f"""
        SELECT timestamp, value
        FROM sensor_data
        WHERE {' AND '.join(condiciones)}
        ORDER BY id ASC
    """

    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute(query, tuple(parametros))
        datos_raw = cursor.fetchall()

    grafica_formateada = []
    suma = 0.0
    mismo_dia = bool(fecha_inicio) and fecha_inicio == fecha_fin

    for fila in datos_raw:
        fecha_cruda = str(fila[0]) if fila[0] else ""
        if len(fecha_cruda) >= 19:
            etiqueta = (
                fecha_cruda[11:19]
                if mismo_dia
                else f"{fecha_cruda[8:10]}/{fecha_cruda[5:7]} {fecha_cruda[11:16]}"
            )
        else:
            etiqueta = fecha_cruda

        valor = float(fila[1]) if fila[1] is not None else 0.0
        suma += valor
        grafica_formateada.append({"hora": etiqueta, "Valor": valor})

    media = round(suma / len(datos_raw), 2) if datos_raw else 0.0
    return grafica_formateada, str(media)