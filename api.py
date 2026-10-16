from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3

app = FastAPI()

# --- CREACIÓN DE LA BASE DE DATOS (Se ejecuta al arrancar) ---
conexion = sqlite3.connect('agrotech.db')
cursor = conexion.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT,
        timestamp TEXT,
        value REAL
    )
""")
conexion.commit()
conexion.close()
# -------------------------------------------------------------

class DatoSensor(BaseModel):
    sensor_id: str
    timestamp: str
    type: str
    value: float
    unit: str

@app.post("/api/sensors/{sensor_id_url}/data")
def recibir_dato(sensor_id_url: str, paquete: DatoSensor):
    conexion = sqlite3.connect('agrotech.db')
    cursor = conexion.cursor()
    
    cursor.execute("""
        INSERT INTO sensor_data (sensor_id, timestamp, value)
        VALUES (?, ?, ?)
    """, (paquete.sensor_id, paquete.timestamp, paquete.value))
    
    conexion.commit()
    conexion.close()
    
    return {"mensaje": "Dato guardado", "valor": paquete.value}