import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from funcs import (
    MAPA_SUFIJO_METADATOS,
    RUTA_DB,
    columna_id_sensors,
    conectar_db,
    init_db,
)


class DatoSensor(BaseModel):
    sensor_id: str
    timestamp: str
    value: float
    raw: Optional[str] = None


class GestorConexionesWS:
    def __init__(self) -> None:
        self.conexiones_por_parcela: dict[int, set[WebSocket]] = {}

    async def conectar(self, parcel_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.conexiones_por_parcela.setdefault(parcel_id, set()).add(websocket)

    def desconectar(self, parcel_id: int, websocket: WebSocket) -> None:
        grupo = self.conexiones_por_parcela.get(parcel_id)
        if grupo:
            grupo.discard(websocket)
            if not grupo:
                self.conexiones_por_parcela.pop(parcel_id, None)

    async def notificar_parcela(self, parcel_id: int, payload: dict) -> None:
        grupo = list(self.conexiones_por_parcela.get(parcel_id, set()))
        if not grupo:
            return
        mensaje = json.dumps(payload, ensure_ascii=False)
        for ws in grupo:
            try:
                await ws.send_text(mensaje)
            except Exception:
                self.desconectar(parcel_id, ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(f"[DB] API conectada a: {RUTA_DB}")
    yield


gestor_ws = GestorConexionesWS()
app = FastAPI(title="Agrotech Telemetry API", lifespan=lifespan)


def _extraer_parcela_y_sufijo(sensor_id: str) -> tuple[Optional[int], str]:
    if not sensor_id.startswith("p") or "_" not in sensor_id:
        return None, ""
    parte_parcela, sufijo = sensor_id.split("_", 1)
    try:
        return int(parte_parcela[1:]), sufijo
    except ValueError:
        return None, sufijo


def _insertar_alerta(
    cursor: sqlite3.Cursor,
    parcel_id: int,
    sensor_id: str,
    message: str,
    value: float,
    timestamp: str,
) -> None:
    cursor.execute("PRAGMA table_info(alerts)")
    info_cols = cursor.fetchall()

    valores_base: dict[str, object] = {
        "parcel_id": parcel_id,
        "sensor_id": sensor_id,
        "message": message,
        "value": value,
        "timestamp": timestamp,
        "acknowledged": 0,
    }

    columnas_insert: list[str] = []
    valores_insert: list[object] = []

    for _, nombre, tipo, notnull, dflt_value, pk in info_cols:
        if pk == 1:
            continue
        if nombre in valores_base:
            columnas_insert.append(nombre)
            valores_insert.append(valores_base[nombre])
        elif notnull == 1 and dflt_value is None:
            tipo_upper = (tipo or "").upper()
            columnas_insert.append(nombre)
            if "INT" in tipo_upper or "REAL" in tipo_upper:
                valores_insert.append(0)
            elif "TIME" in nombre.lower() or "DATE" in nombre.lower():
                valores_insert.append(timestamp)
            else:
                valores_insert.append("critico")

    if columnas_insert:
        placeholders = ", ".join("?" for _ in columnas_insert)
        cols_sql = ", ".join(columnas_insert)
        cursor.execute(f"INSERT INTO alerts ({cols_sql}) VALUES ({placeholders})", tuple(valores_insert))


@app.get("/api/parcels")
def listar_parcelas():
    with conectar_db() as conexion:
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM parcels ORDER BY id ASC")
        return [dict(fila) for fila in cursor.fetchall()]


@app.get("/api/sensors")
def listar_sensores():
    with conectar_db() as conexion:
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM sensors ORDER BY parcel_id ASC")
        return [dict(fila) for fila in cursor.fetchall()]


@app.post("/api/sensors/{sensor_id_url}/data")
async def recibir_dato_sensor(sensor_id_url: str, dato: DatoSensor):
    if sensor_id_url != dato.sensor_id:
        raise HTTPException(
            status_code=400,
            detail="El sensor_id de la URL no coincide con el del cuerpo JSON.",
        )

    parcel_id, sufijo = _extraer_parcela_y_sufijo(dato.sensor_id)

    try:
        with conectar_db() as conexion:
            cursor = conexion.cursor()

            if parcel_id is not None and sufijo in MAPA_SUFIJO_METADATOS:
                tipo_sensor, unidad, col_min, col_max = MAPA_SUFIJO_METADATOS[sufijo]
                col_id = columna_id_sensors(cursor)
                cursor.execute(
                    f"INSERT OR IGNORE INTO sensors ({col_id}, parcel_id, type, unit) VALUES (?, ?, ?, ?)",
                    (dato.sensor_id, parcel_id, tipo_sensor, unidad),
                )

                cursor.execute(
                    f"SELECT {col_min}, {col_max} FROM parcels WHERE id = ?",
                    (parcel_id,),
                )
                rango = cursor.fetchone()
                if rango and rango[0] is not None and rango[1] is not None:
                    v_min, v_max = float(rango[0]), float(rango[1])
                    if dato.value < v_min or dato.value > v_max:
                        detalle = (
                            f"{dato.sensor_id} fuera de rango ({dato.value} {unidad}; "
                            f"permitido [{v_min}, {v_max}])"
                        )
                        _insertar_alerta(
                            cursor,
                            parcel_id,
                            dato.sensor_id,
                            detalle,
                            dato.value,
                            dato.timestamp,
                        )

            cursor.execute("PRAGMA table_info(sensor_data)")
            cols_data = {fila[1] for fila in cursor.fetchall()}
            if "raw" in cols_data:
                cursor.execute(
                    "INSERT INTO sensor_data (sensor_id, timestamp, value, raw) VALUES (?, ?, ?, ?)",
                    (dato.sensor_id, dato.timestamp, dato.value, dato.raw),
                )
            else:
                cursor.execute(
                    "INSERT INTO sensor_data (sensor_id, timestamp, value) VALUES (?, ?, ?)",
                    (dato.sensor_id, dato.timestamp, dato.value),
                )
            conexion.commit()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {e}")

    if parcel_id is not None:
        await gestor_ws.notificar_parcela(
            parcel_id,
            {
                "parcel_id": parcel_id,
                "sensor_id": dato.sensor_id,
                "timestamp": dato.timestamp,
                "value": dato.value,
            },
        )

    return {"status": "ok", "sensor_id": dato.sensor_id, "value": dato.value}


@app.websocket("/ws/parcels/{parcel_id}")
async def websocket_parcela(websocket: WebSocket, parcel_id: int):
    await gestor_ws.conectar(parcel_id, websocket)
    try:
        while True:
            await asyncio.sleep(15)
            await websocket.send_text(
                json.dumps({"type": "ping", "parcel_id": parcel_id, "ts": datetime.now().isoformat()})
            )
    except WebSocketDisconnect:
        gestor_ws.desconectar(parcel_id, websocket)
    except Exception:
        gestor_ws.desconectar(parcel_id, websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)