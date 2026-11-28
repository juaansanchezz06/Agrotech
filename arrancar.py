import subprocess
import sys
import time


def main() -> None:
    procesos: list[subprocess.Popen] = []
    try:
        print("Iniciando API...")
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--port", "8001"])
        procesos.append(api)
        time.sleep(2)

        print("Iniciando Simulador...")
        simulador = subprocess.Popen([sys.executable, "simulador.py"])
        procesos.append(simulador)

        print("Iniciando Reflex...")
        reflex = subprocess.Popen([sys.executable, "-m", "reflex", "run"], cwd="panel_web")
        procesos.append(reflex)

        print("\n🚀 ¡Todo en marcha! Ve a http://localhost:3000")
        print("Pulsa Ctrl+C en esta terminal para apagar todo de golpe.\n")

        api.wait()

    except KeyboardInterrupt:
        print("\nApagando servicios...")
    finally:
        for proc in reversed(procesos):
            if proc.poll() is None:
                proc.terminate()
        for proc in reversed(procesos):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Sistema cerrado correctamente.")


if __name__ == "__main__":
    main()