from fastapi import FastAPI, HTTPException, Query, WebSocket  
from pydantic import BaseModel  
from typing import Optional  
import sqlite3  
import hashlib
from fastapi.responses import HTMLResponse
import asyncio
from fastapi import WebSocketDisconnect  

# Inicialización de la aplicación  
app = FastAPI()  
  
# --- FUNCIÓN DE SEGURIDAD (HASH) ---
def hashear_contrasena(password: str) -> str:
    """Convierte la contraseña en un hash SHA-256 irreversible."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# --- CREACIÓN DE LA BASE DE DATOS ---  
def init_db():  
    conexion = sqlite3.connect('agrotech.db')  
    cursor = conexion.cursor()  
    cursor.executescript("""  
        CREATE TABLE IF NOT EXISTS users (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            username TEXT UNIQUE,  
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

    # Creación automática del administrador con contraseña hasheada
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        admin_hash = hashear_contrasena("admin123")
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
            ("admin", admin_hash, "administrador")
        )

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
    conexion = sqlite3.connect('agrotech.db')  
    cursor = conexion.cursor()  
    
    # Hasheamos la contraseña recibida para compararla con la guardada
    pass_hash = hashear_contrasena(credenciales.password)
    
    cursor.execute(
        "SELECT id, role FROM users WHERE username = ? AND password_hash = ?", 
        (credenciales.username, pass_hash)
    )
    usuario = cursor.fetchone()
    conexion.close()
    
    if usuario:
        # usuario[1] contiene el 'role' (ej. "administrador")
        return {"token": "simulated_jwt_token_12345", "role": usuario[1], "mensaje": "Login exitoso"}
    else:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
  
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
    cursor.execute("SELECT id, type, unit, description FROM sensors WHERE parcel_id = ?")  
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
  
@app.get("/favicon.ico", include_in_schema=False)  
def favicon():  
    return HTMLResponse(content="")  
  
@app.websocket("/ws/parcels/{id}")  
async def websocket_endpoint(websocket: WebSocket, id: int):  
    await websocket.accept()  
    try:
        while True:
            conexion = sqlite3.connect('agrotech.db')  
            cursor = conexion.cursor()  
            
            # Buscamos los datos más recientes de los sensores que pertenecen a esta parcela
            cursor.execute("""
                SELECT s.id, s.type, sd.value, sd.timestamp 
                FROM sensors s
                LEFT JOIN sensor_data sd ON s.id = sd.sensor_id
                WHERE s.parcel_id = ?
                ORDER BY sd.timestamp DESC LIMIT 5
            """, (id,))
            
            datos = [{"sensor": row[0], "tipo": row[1], "valor": row[2], "hora": row[3]} for row in cursor.fetchall()]
            conexion.close()

            # Enviamos los datos en formato JSON al cliente conectado
            await websocket.send_json({
                "parcela_id": id,
                "mensaje": "Streaming en tiempo real activo",
                "datos_recientes": datos
            })
            
            # Pausa de 5 segundos antes de enviar la siguiente actualización
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print(f"Cliente desconectado del streaming de la parcela {id}")