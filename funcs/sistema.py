import subprocess
import sys
import time


def iniciar_proceso(nombre: str, comando: list[str], cwd: str | None = None, espera: float = 0) -> subprocess.Popen:
    """Arranca un subproceso mostrando su estado y espera opcionalmente."""
    print(f"Iniciando {nombre}...")
    proceso = subprocess.Popen(comando, cwd=cwd)
    if espera > 0:
        time.sleep(espera)
    return proceso


def detener_procesos(procesos: list[subprocess.Popen]) -> None:
    """Cierra de forma segura todos los procesos activos en orden inverso."""
    print("\nApagando servicios...")
    for proceso in reversed(procesos):
        if proceso and proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proceso.kill()
    print("Sistema cerrado correctamente.")