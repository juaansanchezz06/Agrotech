import random
import sqlite3
from datetime import datetime, timedelta

from funcs import DEFINICION_SENSORES, columna_id_sensors

 
def detectar_icono_parcela(nombre: str, cultivo: str) -> str:
    texto = f"{nombre} {cultivo}".lower()
    if any(k in texto for k in ("invernadero", "tomate", "pimiento", "pepino", "calabacin", "calabacín")):
        return "invernadero"
    if any(k in texto for k in ("viñedo", "vinedo", "vid", "uva", "parra")):
        return "vinedo"
    if any(k in texto for k in ("huerto", "hortaliza", "lechuga", "frutal")):
        return "huerto"
    if any(k in texto for k in ("sur", "trigo", "cebada", "cereal", "olivar")):
        return "surcos"
    return "campo"


def parsear_rango(min_txt: str, max_txt: str, etiqueta: str) -> tuple[float, float]:
    try:
        v_min = float(min_txt.replace(",", ".").strip())
        v_max = float(max_txt.replace(",", ".").strip())
    except ValueError:
        raise ValueError(f"Los límites de {etiqueta} deben ser valores numéricos.")
    if v_min > v_max:
        raise ValueError(f"En {etiqueta}, el mínimo ({v_min}) no puede ser mayor que el máximo ({v_max}).")
    return v_min, v_max


def registrar_sensores_parcela(cursor: sqlite3.Cursor, parcela_id: int) -> None:
    """Crea en la tabla sensors los 5 sensores estándar de la parcela si no existen."""
    col_id = columna_id_sensors(cursor)
    for sufijo, tipo, unidad in DEFINICION_SENSORES:
        sensor_id = f"p{parcela_id}_{sufijo}"
        cursor.execute(
            f"INSERT OR IGNORE INTO sensors ({col_id}, parcel_id, type, unit) VALUES (?, ?, ?, ?)",
            (sensor_id, parcela_id, tipo, unidad),
        )


def _generar_muestras_rango_y_criticos(sufijo: str, v_min: float, v_max: float) -> list[float]:
    amplitud = max(0.1, v_max - v_min)
    if sufijo in ("temp_amb", "temp_suelo"):
        margen, decimales, limite_inf, limite_sup = max(2.0, amplitud * 0.10), 1, -30.0, 70.0
    elif sufijo == "ph":
        margen, decimales, limite_inf, limite_sup = max(0.5, amplitud * 0.15), 2, 0.0, 14.0
    elif sufijo == "humedad":
        margen, decimales, limite_inf, limite_sup = max(5.0, amplitud * 0.10), 1, 0.0, 100.0
    else:
        margen, decimales, limite_inf, limite_sup = max(500.0, amplitud * 0.10), 0, 0.0, 150000.0

    paso = 0.1 if decimales > 0 else 1.0
    bajo_min = max(limite_inf, round(random.uniform(v_min - margen, v_min - paso), decimales))
    sobre_max = min(limite_sup, round(random.uniform(v_max + paso, v_max + margen), decimales))

    normales = [round(random.uniform(v_min, v_max), decimales) for _ in range(4)]
    muestras = [normales[0], bajo_min, normales[1], normales[2], sobre_max, normales[3]]
    return [int(v) if decimales == 0 else v for v in muestras]


def poblar_datos_iniciales_parcela(
    cursor: sqlite3.Cursor,
    parcela_id: int,
    rangos: dict[str, tuple[float, float]],
) -> None:
    """Inserta lecturas iniciales (normales + fuera de rango) para los 5 sensores de la parcela."""
    ahora = datetime.now()
    for sufijo, (v_min, v_max) in rangos.items():
        sensor_id = f"p{parcela_id}_{sufijo}"
        muestras = _generar_muestras_rango_y_criticos(sufijo, v_min, v_max)
        for indice, valor in enumerate(muestras):
            ts = (ahora - timedelta(minutes=(len(muestras) - indice) * 5)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO sensor_data (sensor_id, timestamp, value) VALUES (?, ?, ?)",
                (sensor_id, ts, valor),
            )