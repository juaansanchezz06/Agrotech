import requests
import time
import random
import json
from datetime import datetime

url_base = "http://localhost:8001/api/sensors"

PARCELAS = {
    1: "Parcela Norte",
    2: "Parcela Sur",
    3: "Invernadero Principal",
    4: "Viñedo Este",
    5: "Huerto Central"
}

# Estado inicial realista para los 5 sensores de cada parcela
estado_sensores = {}
for p_id in PARCELAS.keys():
    estado_sensores[f"p{p_id}_temp_amb"] = {"val": 23.5, "delta": 0.4, "min": 14.0, "max": 34.0}
    estado_sensores[f"p{p_id}_temp_suelo"] = {"val": 18.2, "delta": 0.2, "min": 12.0, "max": 24.0}
    estado_sensores[f"p{p_id}_humedad"] = {"val": 65.0, "delta": 1.2, "min": 35.0, "max": 85.0}
    estado_sensores[f"p{p_id}_lux"] = {"val": 8500.0, "delta": 250.0, "min": 500.0, "max": 16000.0}
    estado_sensores[f"p{p_id}_ph"] = {"val": 6.5, "delta": 0.05, "min": 5.8, "max": 7.4}

print("Enviando datos automáticamente... Pulsa Ctrl+C para parar.")

while True:
    for p_id, p_nombre in PARCELAS.items():
        sensores_ids = [
            f"p{p_id}_temp_amb",
            f"p{p_id}_temp_suelo",
            f"p{p_id}_humedad",
            f"p{p_id}_lux",
            f"p{p_id}_ph"
        ]

        for s_id in sensores_ids:
            sensor_info = estado_sensores[s_id]
            
            # Variación progresiva del valor
            variacion = random.uniform(-sensor_info["delta"], sensor_info["delta"])
            nuevo_valor = round(sensor_info["val"] + variacion, 2 if "ph" in s_id else 1)

            # Mantener dentro de los rangos lógicos
            nuevo_valor = max(sensor_info["min"], min(sensor_info["max"], nuevo_valor))
            sensor_info["val"] = nuevo_valor

            timestamp_actual = datetime.now().astimezone().isoformat()
            paquete = {
                "sensor_id": s_id,
                "timestamp": timestamp_actual,
                "value": nuevo_valor,
                "raw": json.dumps({"estado_bateria": random.randint(85, 100)})
            }

            url_api = f"{url_base}/{s_id}/data"

            try:
                respuesta = requests.post(url_api, json=paquete, timeout=2)
                print(f"Sensor {s_id} enviado: {nuevo_valor} | Estado: {respuesta.status_code}")
            except Exception:
                print("No hay conexión. Esperando a que la API se encienda en el puerto 8001...")

            time.sleep(1)