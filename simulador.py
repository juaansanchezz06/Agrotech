import requests
import time
import random
import json
from datetime import datetime

import requests
import time
import random
import json
from datetime import datetime, timezone

url_base = "http://localhost:8001/api/sensors"

sensores = [
    {"id": "t001", "min": 15.0, "max": 35.0},
    {"id": "h001", "min": 30.0, "max": 80.0},
    {"id": "l001", "min": 200.0, "max": 900.0}
]

print("Enviando datos automáticamente... Pulsa Ctrl+C para parar.")

while True:
    for sensor in sensores:
        valor = round(random.uniform(sensor["min"], sensor["max"]), 1)
        
        paquete = {
            "sensor_id": sensor["id"],
            # Solución al DeprecationWarning: usamos timezone.utc
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "value": valor,
            "raw": json.dumps({"estado_bateria": random.randint(20, 100)})
        }

        url_api = f"{url_base}/{sensor['id']}/data"
        
        try:
            respuesta = requests.post(url_api, json=paquete)
            
            print(f"Sensor {sensor['id']} enviado: {valor} - Estado: {respuesta.status_code}")
        except Exception:
            print("No hay conexión. Esperando a que la API se encienda en el puerto 8001...")
    
    time.sleep(5)