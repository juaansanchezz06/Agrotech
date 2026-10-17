# AGROTECH DASHBOARD - RETO AGROTECH 2026

## Introducción

En este proyecto se ha creado un sistema sencillo para monitorizar sensores agrícolas en tiempo real, para el **II Reto Agrotech 2026**.

La idea principal es que unos sensores (en este caso simulados) mandan datos de temperatura a una API, la API los guarda en una base de datos y después esos datos se podrán ver en un panel web (dashboard).

De momento está hecha la parte de la API, el simulador y la base de datos. El panel web se hará con Reflex y está en proceso.

## Objetivo del proyecto

El objetivo es aprender a montar un flujo completo de datos de principio a fin:

- simular un sensor que genera datos
- recibir esos datos con una API REST
- guardarlos en una base de datos
- (más adelante) mostrarlos en un panel web


## Conceptos básicos

### API REST
Es el "buzón" al que los sensores mandan sus datos mediante peticiones HTTP. En este proyecto se ha hecho con FastAPI.

### Sensor simulado
Un script en Python (`simulador.py`) que se inventa una temperatura y la envía a la API cada 5 segundos, como si fuera un sensor real. El sensor se llama `t001`.

### Base de datos SQLite
Una base de datos que vive en un solo archivo (`agrotech.db`). No hay que instalar nada, se crea sola al arrancar la API.

### Entorno virtual
Una "burbuja" de Python para el proyecto. En Linux no se pueden instalar librerías directamente en todo el sistema, así que todo lo que instalamos se queda dentro de esta burbuja (`entorno_agrotech`).

### Reflex
Librería de Python para hacer páginas web sin escribir JavaScript. Se usará para el dashboard.

## Tecnologías utilizadas

- Python
- FastAPI
- Uvicorn
- Requests
- SQLite
- Reflex
- Git
- GitHub

## Estructura del proyecto

```text
RetoAgrotech/
├── api.py               # API con FastAPI y base de datos
├── simulador.py         # Simulador del sensor de temperatura
├── agrotech.db          # Base de datos (se crea sola)
├── entorno_agrotech/    # Entorno virtual (no se sube a Git)
├── README.md
└── LICENSE
```

## Instalación

### 1. Herramientas extra de Python 

Python ya viene instalado, pero faltan `pip` y `venv`. Abrir la terminal y ejecutar:

```bash
sudo apt update
sudo apt install python3-pip python3-venv -y
```

### 2. Preparar la carpeta

Crear la carpeta `RetoAgrotech` en el Escritorio, abrirla en VS Code (Archivo > Abrir carpeta) y abrir la terminal integrada con `Ctrl + ñ`.

### 3. Crear y activar el entorno virtual

```bash
python3 -m venv entorno_agrotech
source entorno_agrotech/bin/activate
```

Si ha funcionado, aparece `(entorno_agrotech)` al principio de la línea de la terminal.

### 4. Instalar las librerías

Para la API y el simulador:

```bash
pip install fastapi uvicorn requests
```

Para el dashboard con Reflex:

```bash
# Instalar la librería
pip install reflex

# Inicializar el proyecto
reflex init
```

### 5. Crear los archivos

Dentro de la carpeta crear `api.py` y `simulador.py` y pegar el código.

## Cómo ejecutarlo

Hacen falta **dos terminales**, y las dos tienen que estar dentro del entorno virtual.

**Terminal 1 (API):**

```bash
uvicorn api:app --reload
```

Se creará el archivo `agrotech.db`. La documentación de la API se puede ver en `http://localhost:8000/docs`.

**Terminal 2 (simulador):**

Esta terminal nueva no está dentro de la burbuja todavía, hay que activarla primero:

```bash
source entorno_agrotech/bin/activate
python3 simulador.py
```

Saldrá algo como:

```text
Enviado: 23.5ºC - Respuesta: 200
```

Para ver la base de datos dentro de VS Code se puede usar la extensión **SQLite Viewer**.

## API

### `POST /api/sensors/{sensor_id}/data`

Recibe y guarda una lectura de un sensor.

Ejemplo de datos que se envían:

```json
{
  "sensor_id": "t001",
  "timestamp": "2026-10-17T18:00:00Z",
  "type": "temperatura",
  "value": 23.5,
  "unit": "ºC"
}
```

Respuesta si todo va bien (200 OK):

```json
{
  "mensaje": "Dato guardado",
  "valor": 23.5
}
```

## Qué falta por hacer

- Simular también humedad y luminosidad
- Crear una forma de consultar los datos guardados
- Hacer el dashboard con Reflex
- Mostrar los datos en gráficas

## Licencia

Proyecto de software libre bajo la **GNU General Public License v3.0 o posterior (GPL-3.0-or-later)**. Ver el archivo `LICENSE`.
