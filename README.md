# AGROTECH DASHBOARD - RETO AGROTECH 2026

## Introducción

En este proyecto se ha desarrollado un sistema integral de monitorización agrícola en tiempo real para el **II Reto Agrotech 2026**. 

El sistema recolecta datos periódicos transmitidos por sensores multivariable (temperatura, humedad, luminosidad, etc.), los procesa mediante una API REST desarrollada en FastAPI, los almacena de forma persistente en una base de datos SQLite y los visualiza en tiempo real a través de un panel web interactivo construido con Reflex.

## Objetivo del proyecto

Implementar una arquitectura modular end-to-end orientada a IoT e ingeniería agrícola:

- **Simulación IoT**: Generación y envío automatizado de telemetría de sensores con variabilidad en el rango de datos y métricas de batería.
- **Backend API REST & WebSockets**: Ingesta, validación y persistencia de datos, junto con soporte para streaming de eventos.
- **Persistencia**: Almacenamiento relacional ligero y eficiente con SQLite.
- **Frontend Dashboard**: Panel web reactivo y dinámico con auto-refresco visual para supervisión de parcelas, sensores y datos en tiempo real.

## Conceptos Básicos y Componentes

### API REST (`api.py`)
Desarrollada en FastAPI. Es la encargada de recibir las mediciones enviadas por los sensores, consultar información referente a parcelas y sensores asociados, y ofrecer endpoints de filtrado histórico de lecturas. Además, expone un WebSocket para transmisión continua de datos.

### Simulador IoT (`simulador.py`)
Script autónomo que emula el envío de métricas de tres tipos de sensores simultáneos (`t001` de temperatura, `h001` de humedad y `l001` de luminosidad). Incorpora manejo de marcas temporales con zonas horarias (`timezone.utc`) e inyecta estados de batería aleatorios.

### Base de Datos (`agrotech.db`)
Base de datos SQLite embebida que contiene el modelo de datos relacional del proyecto:
- `users`: Gestión de usuarios y roles.
- `parcels`: Información geográfica de las parcelas.
- `sensors`: Catálogo de sensores, tipo de métrica, unidades y umbrales de alerta.
- `sensor_data`: Histórico detallado de lecturas registradas.
- `alerts`: Registro de incidencias y estado de confirmación.

### Panel Web Reactivo (`panel_web.py`)
Dashboard interactivo construido íntegramente en Python mediante Reflex. Incluye un mecanismo de actualización en tiempo real mediante *polling* dinámico en JavaScript (cada 5 segundos), semántica de colores pastel según el nivel de lectura y soporte para modo claro/oscuro.

## Tecnologías Utilizadas

- **Lenguaje**: Python 3.10+
- **Backend**: FastAPI, Uvicorn, Pydantic, WebSockets
- **Frontend**: Reflex
- **Base de Datos**: SQLite3
- **Librerías auxiliares**: Requests
- **Control de versiones**: Git, GitHub

## Estructura del Proyecto

```text
RetoAgrotech/
├── api.py               # API REST, configuración WebSockets y esquema SQLite
├── simulador.py         # Simulador de sensores IoT (temperatura, humedad, luz)
├── panel_web.py         # Dashboard frontend con Reflex y visualización reactiva
├── agrotech.db          # Base de datos relacional SQLite (se autogenera)
├── entorno_agrotech/    # Entorno virtual de Python (.venv)
├── README.md            # Documentación del proyecto
└── LICENSE              # Licencia GPLv3
```

## Instalación

### 1. Dependencias del sistema (Linux/Ubuntu)

Asegúrate de disponer de `python3-pip` y `python3-venv` en tu sistema:

```bash
sudo apt update
sudo apt install python3-pip python3-venv -y
```

### 2. Preparar el proyecto y el entorno virtual

Clona o abre el directorio del proyecto y crea el entorno virtual de trabajo:

```bash
python3 -m venv entorno_agrotech
source entorno_agrotech/bin/activate
```

Al activarse, verás el prefijo `(entorno_agrotech)` en la consola.

### 3. Instalar librerías de Python

Instala los módulos requeridos para la API, el simulador y el panel web:

```bash
pip install fastapi uvicorn requests reflex
```

Si es la primera vez que inicializas Reflex en un directorio limpio:

```bash
reflex init
```

## Cómo Ejecutar el Sistema

Para ejecutar la solución completa se requieren **tres terminales abiertas**, todas con el entorno virtual activado.

### Terminal 1: Servidor API REST (Puerto 8001)

Ejecuta FastAPI especificando el puerto 8001 (el cual espera el simulador):

```bash
source entorno_agrotech/bin/activate
uvicorn api:app --port 8001 --reload
```

*Nota: La documentación Swagger interactiva estará accesible en `http://localhost:8001/docs`.*

### Terminal 2: Simulador de Sensores

Inicia el generador de datos para comenzar a enviar métricas a la API cada 5 segundos:

```bash
source entorno_agrotech/bin/activate
python3 simulador.py
```

### Terminal 3: Panel Web Dashboard (Reflex)

Despliega la aplicación web de Reflex:

```bash
source entorno_agrotech/bin/activate
reflex run
```

El panel estará disponible en tu navegador en `http://localhost:3000`.

## Referencia de Endpoints API

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Simulación de autenticación JWT |
| `GET` | `/api/parcels` | Lista de parcelas registradas |
| `GET` | `/api/parcels/{id}/sensors` | Lista de sensores asociados a una parcela |
| `POST` | `/api/sensors/{sensor_id}/data` | Recepción e ingesta de lecturas enviadas por los sensores |
| `GET` | `/api/sensors/{sensor_id}/data` | Consulta histórica de lecturas con filtros opcionales (`from`, `to`, `limit`) |
| `GET` | `/api/dashboard` | Estado general del servicio |
| `WS` | `/ws/parcels/{id}` | Endpoint WebSocket para transmisión continua |

### Ejemplo de Payload enviado por un sensor (`POST`)

```json
{
  "sensor_id": "t001",
  "timestamp": "2026-10-31T11:39:00+01:00",
  "value": 24.8,
  "raw": "{\"estado_bateria\": 85}"
}
```

## Próximas Mejoras

- [ ] Implementar autenticación real mediante tokens JWT persistidos en el cliente.
- [ ] Integrar gráficas de líneas reactivas (`rx.recharts`) en la pestaña de lecturas en vivo del dashboard.
- [ ] Añadir panel de control para la confirmación de alertas en tiempo real (`acknowledged`).
- [ ] Dockerizar la aplicación mediante un archivo `docker-compose.yml` para simplificar la ejecución con un solo comando.

## Licencia

Proyecto publicado bajo la licencia **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. Revisa el archivo `LICENSE` para más detalles.
