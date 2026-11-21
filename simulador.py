import time
from funcs.sensores import (
    inicializar_estado_sensores,
    generar_lectura_sensor,
    enviar_lectura_api,
)

URL_BASE = "http://localhost:8001/api/sensors"

PARCELAS = {
    1: "Parcela Norte",
    2: "Parcela Sur",
    3: "Invernadero Principal",
    4: "Viñedo Este",
    5: "Huerto Central",
}

TIPOS_SENSORES = ["temp_amb", "temp_suelo", "humedad", "lux", "ph"]


def ejecutar_simulacion():
    estado_sensores = inicializar_estado_sensores(PARCELAS)
    print("Enviando datos automáticamente... Pulsa Ctrl+C para parar.")

    try:
        while True:
            for p_id in PARCELAS:
                for tipo in TIPOS_SENSORES:
                    s_id = f"p{p_id}_{tipo}"
                    paquete = generar_lectura_sensor(s_id, estado_sensores[s_id])
                    exito, resultado = enviar_lectura_api(URL_BASE, paquete)

                    if exito:
                        print(f"Sensor {s_id} enviado: {paquete['value']} | Estado: {resultado}")
                    else:
                        print("No hay conexión. Esperando a que la API se encienda en el puerto 8001...")

                    time.sleep(1)
    except KeyboardInterrupt:
        print("\nSimulador detenido por el usuario.")


if __name__ == "__main__":
    ejecutar_simulacion()