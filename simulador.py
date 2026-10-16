import requests
import time
import random
from datetime import datetime

url_api = "http://localhost:8000/api/sensors/t001/data"
print("Enviando datos... Pulsa Ctrl+C para parar.")

while True:
    temperatura = round(random.uniform(15.0, 35.0), 1)
    paquete = {
        "sensor_id": "t001",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "temperatura",
        "value": temperatura,
        "unit": "ºC"
    }

    try:
        respuesta = requests.post(url_api, json=paquete)
        print(f"Enviado: {temperatura}ºC - Respuesta: {respuesta.status_code}")
    except Exception:
        print("Esperando a que la API se encienda...")
    
    time.sleep(5)