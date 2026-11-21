import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

RUTA_RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(RUTA_RAIZ, "agrotech.db")

PARCELAS_INICIALES = [
    ("Parcela Norte", "Sector A", "Maíz", "2.4 ha", 0, "", 15.0, 32.0, 12.0, 28.0, 5.5, 7.5, 200.0, 50000.0, 40.0, 85.0),
    ("Parcela Sur", "Sector B", "Trigo", "3.1 ha", 0, "", 12.0, 30.0, 10.0, 26.0, 6.0, 7.5, 200.0, 50000.0, 35.0, 80.0),
    ("Invernadero Principal", "Sector C", "Tomate", "0.8 ha", 0, "", 18.0, 30.0, 15.0, 26.0, 5.8, 6.8, 300.0, 45000.0, 55.0, 85.0),
    ("Viñedo Este", "Sector D", "Vid", "4.0 ha", 0, "", 14.0, 34.0, 12.0, 28.0, 5.5, 7.5, 300.0, 60000.0, 35.0, 75.0),
    ("Huerto Central", "Sector E", "Hortalizas", "1.2 ha", 0, "", 15.0, 29.0, 13.0, 25.0, 6.0, 7.2, 200.0, 45000.0, 50.0, 85.0),
]

MAPA_SUFIJO_METADATOS: dict[str, tuple[str, str, str, str]] = {
    "temp_amb": ("temperaturaAmb", "ºC", "temp_amb_min", "temp_amb_max"),
    "temp_suelo": ("temperaturaSuelo", "ºC", "temp_suelo_min", "temp_suelo_max"),
    "ph": ("ph", "pH", "ph_min", "ph_max"),
    "lux": ("luminosidad", "lux", "lux_min", "lux_max"),
    "humedad": ("humedadSuelo", "%", "humedad_min", "humedad_max"),
}


def _generar_hash_admin(password_plana: str = "admin123") -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password_plana.encode("utf-8"), salt.encode("utf-8"), 600000)
    return f"pbkdf2_sha256$600000${salt}${dk.hex()}"


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


gestor_ws = GestorConexionesWS()
app = FastAPI(title="Agrotech Telemetry API")


def _conectar_db() -> sqlite3.Connection:
    return sqlite3.connect(RUTA_DB, timeout=15.0)


def _extraer_parcela_y_sufijo(sensor_id: str) -> tuple[Optional[int], str]:
    if not sensor_id.startswith("p") or "_" not in sensor_id:
        return None, ""
    parte_parcela, sufijo = sensor_id.split("_", 1)
    try:
        return int(parte_parcela[1:]), sufijo
    except ValueError:
        return None, sufijo


def _columna_id_sensors(cursor: sqlite3.Cursor) -> str:
    cursor.execute("PRAGMA table_info(sensors)")
    columnas = {fila[1] for fila in cursor.fetchall()}
    return "sensor_id" if "sensor_id" in columnas and "id" not in columnas else "id"


def _sembrar_datos_basicos(cursor: sqlite3.Cursor) -> None:
    cursor.execute("PRAGMA table_info(users)")
    cols_users = {fila[1] for fila in cursor.fetchall()}
    if "password_hash" not in cols_users:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
        if "password" in cols_users:
            cursor.execute("UPDATE users SET password_hash = password WHERE password_hash = ''")

    cursor.execute("SELECT 1 FROM users WHERE username = 'admin'")
    if cursor.fetchone() is None:
        hash_admin = _generar_hash_admin("admin123")
        if "password" in cols_users:
            cursor.execute(
                "INSERT OR IGNORE INTO users (username, password, password_hash, role) VALUES (?, ?, ?, ?)",
                ("admin", hash_admin, hash_admin, "administrador"),
            )
        else:
            cursor.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", hash_admin, "administrador"),
            )

    cursor.execute("SELECT COUNT(*) FROM parcels")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO parcels (
                name, location, crop, area, en_mantenimiento, notes,
                temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            PARCELAS_INICIALES,
        )

        col_id = _columna_id_sensors(cursor)
        cursor.execute("SELECT id FROM parcels ORDER BY id ASC")
        for (pid,) in cursor.fetchall():
            for sufijo, (tipo_sensor, unidad, _, _) in MAPA_SUFIJO_METADATOS.items():
                cursor.execute(
                    f"INSERT OR IGNORE INTO sensors ({col_id}, parcel_id, type, unit) VALUES (?, ?, ?, ?)",
                    (f"p{pid}_{sufijo}", int(pid), tipo_sensor, unidad),
                )


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


def init_db() -> None:
    conexion = sqlite3.connect(RUTA_DB, timeout=15.0, isolation_level=None)
    try:
        cursor = conexion.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'usuario'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                crop TEXT DEFAULT 'Sin especificar',
                area TEXT DEFAULT '1.5 ha',
                en_mantenimiento INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                temp_amb_min REAL DEFAULT 15.0,
                temp_amb_max REAL DEFAULT 32.0,
                temp_suelo_min REAL DEFAULT 12.0,
                temp_suelo_max REAL DEFAULT 28.0,
                ph_min REAL DEFAULT 5.5,
                ph_max REAL DEFAULT 7.5,
                lux_min REAL DEFAULT 200.0,
                lux_max REAL DEFAULT 50000.0,
                humedad_min REAL DEFAULT 40.0,
                humedad_max REAL DEFAULT 85.0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                id TEXT PRIMARY KEY,
                parcel_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                unit TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                value REAL NOT NULL,
                raw TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parcel_id INTEGER,
                sensor_id TEXT NOT NULL,
                message TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0
            )
        """)

        columnas_alerts = {
            "parcel_id": "INTEGER",
            "sensor_id": "TEXT DEFAULT ''",
            "message": "TEXT DEFAULT ''",
            "value": "REAL DEFAULT 0.0",
            "timestamp": "TEXT DEFAULT ''",
            "acknowledged": "INTEGER DEFAULT 0",
        }
        cursor.execute("PRAGMA table_info(alerts)")
        existentes_alerts = {fila[1] for fila in cursor.fetchall()}
        for col, definicion in columnas_alerts.items():
            if col not in existentes_alerts:
                cursor.execute(f"ALTER TABLE alerts ADD COLUMN {col} {definicion}")

        _sembrar_datos_basicos(cursor)
        cursor.execute("COMMIT")
    except Exception:
        if conexion.in_transaction:
            conexion.execute("ROLLBACK")
        raise
    finally:
        conexion.close()


init_db()


@app.on_event("startup")
def on_startup() -> None:
    print(f"[DB] API conectada a: {RUTA_DB}")
    init_db()


@app.get("/api/parcels")
def listar_parcelas():
    with _conectar_db() as conexion:
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM parcels ORDER BY id ASC")
        return [dict(fila) for fila in cursor.fetchall()]


@app.get("/api/sensors")
def listar_sensores():
    with _conectar_db() as conexion:
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
        with _conectar_db() as conexion:
            cursor = conexion.cursor()

            if parcel_id is not None and sufijo in MAPA_SUFIJO_METADATOS:
                tipo_sensor, unidad, col_min, col_max = MAPA_SUFIJO_METADATOS[sufijo]
                col_id = _columna_id_sensors(cursor)
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