import sys
from funcs.sistema import iniciar_proceso, detener_procesos


def main():
    procesos = []
    try:
        api = iniciar_proceso(
            "API",
            [sys.executable, "-m", "uvicorn", "api:app", "--port", "8001"],
            espera=2,
        )
        procesos.append(api)

        simulador = iniciar_proceso(
            "Simulador",
            [sys.executable, "simulador.py"],
        )
        procesos.append(simulador)

        reflex = iniciar_proceso(
            "Reflex",
            [sys.executable, "-m", "reflex", "run"],
            cwd="panel_web",
        )
        procesos.append(reflex)

        print("\n🚀 ¡Todo en marcha! Ve a http://localhost:3000")
        print("Pulsa Ctrl+C en esta terminal para apagar todo de golpe.\n")

        api.wait()

    except KeyboardInterrupt:
        pass
    finally:
        detener_procesos(procesos)


if __name__ == "__main__":
    main()