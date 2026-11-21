import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from funcs.database import init_db
from funcs.parcelas import obtener_sensores_parcela, obtener_todas_parcelas
from funcs.sensores import (
    guardar_lectura_db,
    obtener_historico_sensor,
    obtener_ultimas_lecturas_parcela,
)
from funcs.usuarios import autenticar_usuario

app = FastAPI()
init_db()


# --- MODELOS PYDANTIC ---
class LoginRequest(BaseModel):
    username: str
    password: str


class DatoSensor(BaseModel):
    sensor_id: str
    timestamp: str
    value: float
    raw: Optional[str] = None


# --- ENDPOINTS ---
@app.post("/api/auth/login")
def login(credenciales: LoginRequest):
    rol = autenticar_usuario(credenciales.username, credenciales.password)
    if rol:
        return {"token": "simulated_jwt_token_12345", "role": rol, "mensaje": "Login exitoso"}
    raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")


@app.get("/api/parcels")
def listar_parcelas():
    return obtener_todas_parcelas()


@app.get("/api/parcels/{id}/sensors")
def sensores_de_parcela(id: int):
    return obtener_sensores_parcela(id)


@app.post("/api/sensors/{sensor_id_url}/data")
def recibir_dato(sensor_id_url: str, paquete: DatoSensor):
    if sensor_id_url != paquete.sensor_id:
        raise HTTPException(status_code=400, detail="El ID de la URL no coincide con el del payload")

    guardar_lectura_db(paquete.sensor_id, paquete.timestamp, paquete.value, paquete.raw)
    return {"mensaje": "Dato guardado correctamente", "valor": paquete.value}


@app.get("/api/sensors/{sensor_id}/data")
def historico_datos(
    sensor_id: str,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    limit: int = 100,
):
    return obtener_historico_sensor(sensor_id, from_date, to_date, limit)


@app.get("/api/dashboard")
def resumen_dashboard():
    return {"status": "ok", "message": "Dashboard listo."}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return HTMLResponse(content="")


@app.websocket("/ws/parcels/{id}")
async def websocket_endpoint(websocket: WebSocket, id: int):
    await websocket.accept()
    try:
        while True:
            datos = obtener_ultimas_lecturas_parcela(id)
            await websocket.send_json({
                "parcela_id": id,
                "mensaje": "Streaming en tiempo real activo",
                "datos_recientes": datos,
            })
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print(f"Cliente desconectado del streaming de la parcela {id}")