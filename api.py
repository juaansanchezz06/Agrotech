from fastapi import FastAPI, HTTPException, Query, WebSocket
from pydantic import BaseModel
from typing import Optional
import sqlite3

# Inicialización de la aplicación
app = FastAPI()

# --- CREACIÓN DE LA BASE DE DATOS ---
def init_db():
    conexion = sqlite3.connect('agrotech.db')
    cursor = conexion.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password_hash TEXT,
            role TEXT
        );
        CREATE TABLE IF NOT EXISTS parcels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            location TEXT
        );
        CREATE TABLE IF NOT EXISTS sensors (
            id TEXT PRIMARY KEY,
            parcel_id INTEGER,
            type TEXT,
            unit TEXT,
            description TEXT,
            threshold_low REAL,
            threshold_high REAL,
            FOREIGN KEY(parcel_id) REFERENCES parcels(id)
        );
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT,
            timestamp TEXT,
            value REAL,
            raw TEXT,
            FOREIGN KEY(sensor_id) REFERENCES sensors(id)
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT,
            timestamp TEXT,
            type TEXT,
            message TEXT,
            acknowledged BOOLEAN,
            FOREIGN KEY(sensor_id) REFERENCES sensors(id)
        );
    """)
    conexion.commit()
    conexion.close()

init_db()

# --- MODELOS PYDANTIC ---
class LoginRequest(BaseModel):
    username: str
    password: str

class DatoSensor(BaseModel):
    sensor_id: str
    timestamp: str
    value: float
    raw: Optional[str] = None

# --- ENDPOINTS ---
@app.post("/api/auth/login")
def login(credenciales: LoginRequest):
    return {"token": "simulated_jwt_token_12345"}

@app.get("/api/parcels")
def listar_parcelas():
    conexion = sqlite3.connect('agrotech.db')
    cursor = conexion.cursor()
    cursor.execute("SELECT id, name, location FROM parcels")
    parcelas = [{"id": row[0], "name": row[1], "location": row[2]} for row in cursor.fetchall()]
    conexion.close()
    return parcelas

@app.get("/api/parcels/{id}/sensors")
def sensores_de_parcela(id: int):
    conexion = sqlite3.connect('agrotech.db')
    cursor = conexion.cursor()
    cursor.execute("SELECT id, type, unit, description FROM sensors WHERE parcel_id = ?", (id,))
    sensores = [{"id": row[0], "type": row[1], "unit": row[2], "description": row[3]} for row in cursor.fetchall()]
    conexion.close()
    return sensores

@app.post("/api/sensors/{sensor_id_url}/data")
def recibir_dato(sensor_id_url: str, paquete: DatoSensor):
    if sensor_id_url != paquete.sensor_id:
        raise HTTPException(status_code=400, detail="El ID de la URL no coincide con el del payload")
        
    conexion = sqlite3.connect('agrotech.db')
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO sensor_data (sensor_id, timestamp, value, raw)
        VALUES (?, ?, ?, ?)
    """, (paquete.sensor_id, paquete.timestamp, paquete.value, paquete.raw))
    conexion.commit()
    conexion.close()
    return {"mensaje": "Dato guardado correctamente", "valor": paquete.value}

@app.get("/api/sensors/{sensor_id}/data")
def historico_datos(
    sensor_id: str, 
    from_date: Optional[str] = Query(None, alias="from"), 
    to_date: Optional[str] = Query(None, alias="to"), 
    limit: int = 100
):
    conexion = sqlite3.connect('agrotech.db')
    cursor = conexion.cursor()
    
    query = "SELECT timestamp, value FROM sensor_data WHERE sensor_id = ?"
    params = [sensor_id]
    
    if from_date:
        query += " AND timestamp >= ?"
        params.append(from_date)
    if to_date:
        query += " AND timestamp <= ?"
        params.append(to_date)
        
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, tuple(params))
    datos = [{"timestamp": row[0], "value": row[1]} for row in cursor.fetchall()]
    conexion.close()
    return datos

@app.get("/api/dashboard")
def resumen_dashboard():
    return {"status": "ok", "message": "Dashboard listo."}

@app.websocket("/ws/parcels/{id}")
async def websocket_endpoint(websocket: WebSocket, id: int):
    await websocket.accept()
    await websocket.send_text(f"Conectado al streaming en tiempo real de la parcela {id}")