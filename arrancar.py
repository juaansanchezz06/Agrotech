import subprocess
import sys
import time

try:
    print("Iniciando API...")
    # Usamos sys.executable -m en lugar de shell=True para compatibilidad multiplataforma
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--port", "8001"])
    time.sleep(2) 

    print("Iniciando Simulador...")
    simulador = subprocess.Popen([sys.executable, "simulador.py"])

    print("Iniciando Reflex...")
    # Ejecutamos Reflex como módulo de Python dentro de la carpeta panel_web
    reflex = subprocess.Popen([sys.executable, "-m", "reflex", "run"], cwd="panel_web")

    print("\n🚀 ¡Todo en marcha! Ve a http://localhost:3000")
    print("Pulsa Ctrl+C en esta terminal para apagar todo de golpe.\n")
    
    api.wait()

except KeyboardInterrupt:
    print("\nApagando servicios...")
    api.terminate()
    simulador.terminate()
    reflex.terminate()
    print("Sistema cerrado correctamente.")