# AGROTECH DASHBOARD - RETO AGROTECH 2026

## Introducción

En este proyecto se ha desarrollado un sistema integral de monitorización agrícola en tiempo real para el **II Reto Agrotech 2026**. 

El sistema recolecta datos periódicos transmitidos por sensores multivariable (temperatura, humedad, luminosidad, pH, etc.), los procesa mediante una API REST desarrollada en FastAPI, los almacena de forma persistente en una base de datos SQLite con contraseñas hasheadas (SHA-256) y los visualiza en tiempo real a través de un panel web interactivo construido con Reflex, protegido mediante control de acceso y gestión de sesiones.

## Objetivo del proyecto

Implementar una arquitectura modular *end-to-end* orientada a IoT e ingeniería agrícola:

- **Simulación IoT**: Generación y envío automatizado de telemetría de sensores con variabilidad en el rango de datos y métricas de batería.
- **Backend API REST & WebSockets**: Ingesta, validación, persistencia de datos y sistema de autenticación de usuarios.
- **Seguridad e Identidad**: Autenticación con almacenamiento local de credenciales, cifrado de contraseñas con SHA-256 y protección de rutas.
- **Frontend Dashboard**: Panel web reactivo y dinámico con auto-refresco visual para supervisión de parcelas, sensores y datos en tiempo real.
- **Orquestación**: Ejecución simplificada de todo el ecosistema con un único comando.

## Conceptos Básicos y Componentes

### 1. API REST y Backend (`api.py`)
Desarrollada en FastAPI. Es la encargada de recibir las mediciones enviadas por los sensores, autenticar usuarios contra hashes SHA-256, consultar información de parcelas y sensores asociados, y ofrecer endpoints de filtrado histórico de lecturas. Además, expone un WebSocket para transmisión continua de datos.

### 2. Módulo de Autenticación (`login.py`)
Componente de Reflex que implementa una interfaz fluida para:
- **Iniciar sesión** verificando hashes SHA-256 en la base de datos.
- **Registro de nuevos usuarios** asignando roles por defecto.
- **Gestión de estado persistente** mediante `rx.LocalStorage` para mantener la sesión del usuario.
- Visibilidad alternable para el campo de contraseña.

### 3. Panel Web Dashboard (`panel_web.py`)
Dashboard interactivo construido íntegramente en Python mediante Reflex. Incluye:
- **Control de barrera de acceso**: Redirige al login si no se detecta sesión activa.
- **Visualización en tiempo real**: Tarjetas circulares con métricas en vivo (Temperatura, Humedad, Luz, pH).
- **Mecanismo de auto-refresco**: *Polling* dinámico en JavaScript (cada 5 segundos).
- **Diseño limpio**: Semántica de colores pastel adaptados según los umbrales de lectura y soporte para modo claro/oscuro.

### 4. Simulador IoT (`simulador.py`)
Script autónomo que emula el envío de métricas de sensores (`t001` de temperatura, `h001` de humedad y `l001` de luminosidad). Incorpora manejo de marcas temporales con zonas horarias (`timezone.utc`) e inyecta estados de batería aleatorios.

### 5. Script de Orquestación (`arrancar.py`)
Permite lanzar simultáneamente la API, el simulador de datos y el panel web de Reflex en subprocesos independientes, gestionando la parada limpia de todos los servicios mediante `Ctrl+C`.

### 6. Base de Datos (`agrotech.db`)
Base de datos SQLite embebida que contiene el modelo relacional del proyecto:
- `users`: Gestión de usuarios, roles y contraseñas hasheadas (`password_hash`).
- `parcels`: Información geográfica de las parcelas.
- `sensors`: Catálogo de sensores, tipo de métrica, unidades y umbrales de alerta.
- `sensor_data`: Histórico detallado de lecturas registradas.
- `alerts`: Registro de incidencias y estado de confirmación.

## Tecnologías Utilizadas

- **Lenguaje**: Python 3.10+
- **Backend**: FastAPI, Uvicorn, Pydantic, WebSockets
- **Frontend**: Reflex (Componentes UI y gestión de estado con React/Next.js subyacente)
- **Base de Datos**: SQLite3
- **Seguridad**: Hashlib (SHA-256)
- **Librerías auxiliares**: Requests
- **Control de versiones**: Git, GitHub

## Estructura del Proyecto

```text
RetoAgrotech/
├── arrancar.py          # Script principal para iniciar todos los servicios a la vez
├── api.py               # API REST, autenticación backend y esquema SQLite
├── simulador.py         # Simulador de sensores IoT (temperatura, humedad, luz)
├── login.py             # Pantalla de Login/Registro y gestión de estado de autenticación
├── panel_web.py         # Dashboard principal con tablas, métricas y control de acceso
├── agrotech.db          # Base de datos relacional SQLite (se autogenera al iniciar)
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

### 2. Preparar el entorno virtual

Clona o abre el directorio del proyecto y activa el entorno virtual:

```bash
python3 -m venv entorno_agrotech
source entorno_agrotech/bin/activate
```

Al activarse, verás el prefijo `(entorno_agrotech)` en la consola.

### 3. Instalar librerías de Python

Instala los módulos requeridos:

```bash
pip install fastapi uvicorn requests reflex
```

Si es la primera vez que inicializas Reflex en un directorio limpio:

```bash
reflex init
```

## Cómo Ejecutar el Sistema

### Opción A: Modo Simplificado (Recomendado)

Puedes arrancar todo el sistema (API + Simulador + Panel Web) con un solo comando gracias al script `arrancar.py`:

```bash
source entorno_agrotech/bin/activate
python3 arrancar.py
```

- La API estará en: `http://localhost:8001`
- El Panel Web estará accesible en: `http://localhost:3000`
- Credenciales por defecto del administrador: **Usuario:** `admin` | **Contraseña:** `admin123`
- Para detener todos los servicios pulsa `Ctrl+C` en la terminal.

---

### Opción B: Ejecución Manual en Terminales Separadas

Si prefieres monitorear los logs de cada servicio por separado, abre tres terminales con el entorno virtual activado:

#### Terminal 1: Servidor API REST (Puerto 8001)
```bash
source entorno_agrotech/bin/activate
uvicorn api:app --port 8001 --reload
```
*Documentación Swagger interactiva accesible en `http://localhost:8001/docs`.*

#### Terminal 2: Simulador de Sensores
```bash
source entorno_agrotech/bin/activate
python3 simulador.py
```

#### Terminal 3: Panel Web Dashboard (Reflex)
```bash
source entorno_agrotech/bin/activate
reflex run
```

## Referencia de Endpoints API

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Validación de credenciales con hash SHA-256 |
| `GET` | `/api/parcels` | Lista de parcelas registradas |
| `GET` | `/api/parcels/{id}/sensors` | Lista de sensores asociados a una parcela |
| `POST` | `/api/sensors/{sensor_id}/data` | Ingesta de lecturas enviadas por los sensores |
| `GET` | `/api/sensors/{sensor_id}/data` | Consulta histórica de lecturas (`from`, `to`, `limit`) |
| `GET` | `/api/dashboard` | Estado general del servicio |
| `WS` | `/ws/parcels/{id}` | WebSocket para transmisión continua |

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

- [ ] Implementar autenticación real mediante tokens JWT firmados.
- [ ] Integrar gráficas temporales de líneas (`rx.recharts`) en la vista del dashboard.
- [ ] Añadir panel de control para la confirmación de alertas en tiempo real (`acknowledged`).
- [ ] Contenedorización mediante un archivo `docker-compose.yml` para despliegue en producción.

## Licencia

Proyecto publicado bajo la licencia **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. Revisa el archivo `LICENSE` para más detalles.
