import subprocess
import sys
import time

try:
    print("Iniciando API...")
    api = subprocess.Popen(["uvicorn", "api:app", "--port", "8001"], shell=True)
    time.sleep(2) 

    print("Iniciando Simulador...")
    simulador = subprocess.Popen([sys.executable, "simulador.py"])

    print("Iniciando Reflex...")
    # Añadimos cwd="panel_web" para que ejecute el comando dentro de esa carpeta
    reflex = subprocess.Popen(["reflex", "run"], shell=True, cwd="panel_web")

    print("\n🚀 ¡Todo en marcha! Ve a http://localhost:3000")
    print("Pulsa Ctrl+C en esta terminal para apagar todo de golpe.\n")
    
    api.wait()

except KeyboardInterrupt:
    print("\nApagando servicios...")
    api.terminate()
    simulador.terminate()
    reflex.terminate()
    print("Sistema cerrado correctamente.")