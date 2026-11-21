from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import os
import random
import secrets
import sqlite3
import time

import requests

RUTA_RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(RUTA_RAIZ, "agrotech.db")

URL_API = "http://127.0.0.1:8001/api/sensors"
INTERVALO_SEGUNDOS = 5.0
MAX_HILOS_ENVIO = 20
PROBABILIDAD_CRITICO = 0.01

TIPOS_SENSORES = ("temp_amb", "temp_suelo", "ph", "lux", "humedad")

DEFINICION_SENSORES = (
    ("temp_amb", "temperaturaAmb", "ºC"),
    ("temp_suelo", "temperaturaSuelo", "ºC"),
    ("ph", "ph", "pH"),
    ("lux", "luminosidad", "lux"),
    ("humedad", "humedadSuelo", "%"),
)

PARCELAS_INICIALES = [
    ("Parcela Norte", "Sector A", "Maíz", "2.4 ha", 0, "", 15.0, 32.0, 12.0, 28.0, 5.5, 7.5, 200.0, 50000.0, 40.0, 85.0),
    ("Parcela Sur", "Sector B", "Trigo", "3.1 ha", 0, "", 12.0, 30.0, 10.0, 26.0, 6.0, 7.5, 200.0, 50000.0, 35.0, 80.0),
    ("Invernadero Principal", "Sector C", "Tomate", "0.8 ha", 0, "", 18.0, 30.0, 15.0, 26.0, 5.8, 6.8, 300.0, 45000.0, 55.0, 85.0),
    ("Viñedo Este", "Sector D", "Vid", "4.0 ha", 0, "", 14.0, 34.0, 12.0, 28.0, 5.5, 7.5, 300.0, 60000.0, 35.0, 75.0),
    ("Huerto Central", "Sector E", "Hortalizas", "1.2 ha", 0, "", 15.0, 29.0, 13.0, 25.0, 6.0, 7.2, 200.0, 45000.0, 50.0, 85.0),
]


def _generar_hash_admin(password_plana: str = "admin123") -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password_plana.encode("utf-8"), salt.encode("utf-8"), 600000)
    return f"pbkdf2_sha256$600000${salt}${dk.hex()}"


def asegurar_db_inicial() -> None:
    conexion = sqlite3.connect(RUTA_DB, timeout=15.0, isolation_level=None)
    try:
        cursor = conexion.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'usuario'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                crop TEXT DEFAULT 'Sin especificar',
                area TEXT DEFAULT '1.5 ha',
                en_mantenimiento INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                temp_amb_min REAL DEFAULT 15.0,
                temp_amb_max REAL DEFAULT 32.0,
                temp_suelo_min REAL DEFAULT 12.0,
                temp_suelo_max REAL DEFAULT 28.0,
                ph_min REAL DEFAULT 5.5,
                ph_max REAL DEFAULT 7.5,
                lux_min REAL DEFAULT 200.0,
                lux_max REAL DEFAULT 50000.0,
                humedad_min REAL DEFAULT 40.0,
                humedad_max REAL DEFAULT 85.0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                id TEXT PRIMARY KEY,
                parcel_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                unit TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                value REAL NOT NULL,
                raw TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                value REAL NOT NULL,
                raw TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_ts 
            ON sensor_data(sensor_id, timestamp)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parcel_id INTEGER,
                sensor_id TEXT NOT NULL,
                message TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0
            )
        """)

        cursor.execute("PRAGMA table_info(users)")
        cols_users = {fila[1] for fila in cursor.fetchall()}
        if "password_hash" not in cols_users:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
            if "password" in cols_users:
                cursor.execute("UPDATE users SET password_hash = password WHERE password_hash = ''")

        cursor.execute("SELECT 1 FROM users WHERE username = 'admin'")
        if cursor.fetchone() is None:
            hash_admin = _generar_hash_admin("admin123")
            if "password" in cols_users:
                cursor.execute(
                    "INSERT OR IGNORE INTO users (username, password, password_hash, role) VALUES (?, ?, ?, ?)",
                    ("admin", hash_admin, hash_admin, "administrador"),
                )
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    ("admin", hash_admin, "administrador"),
                )

        cursor.execute("SELECT COUNT(*) FROM parcels")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                """
                INSERT INTO parcels (
                    name, location, crop, area, en_mantenimiento, notes,
                    temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                    ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                PARCELAS_INICIALES,
            )
            cursor.execute("PRAGMA table_info(sensors)")
            cols = {fila[1] for fila in cursor.fetchall()}
            col_id = "sensor_id" if "sensor_id" in cols and "id" not in cols else "id"

            cursor.execute("SELECT id FROM parcels ORDER BY id ASC")
            for (pid,) in cursor.fetchall():
                for sufijo, tipo, unidad in DEFINICION_SENSORES:
                    cursor.execute(
                        f"INSERT OR IGNORE INTO sensors ({col_id}, parcel_id, type, unit) VALUES (?, ?, ?, ?)",
                        (f"p{pid}_{sufijo}", int(pid), tipo, unidad),
                    )
        cursor.execute("COMMIT")
    except Exception:
        if conexion.in_transaction:
            conexion.execute("ROLLBACK")
        raise
    finally:
        conexion.close()


def obtener_parcelas() -> list[dict]:
    try:
        asegurar_db_inicial()
        with sqlite3.connect(RUTA_DB, timeout=10.0) as conexion:
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT id, name,
                       COALESCE(temp_amb_min, 15.0), COALESCE(temp_amb_max, 32.0),
                       COALESCE(temp_suelo_min, 12.0), COALESCE(temp_suelo_max, 28.0),
                       COALESCE(ph_min, 5.5), COALESCE(ph_max, 7.5),
                       COALESCE(lux_min, 200.0), COALESCE(lux_max, 50000.0),
                       COALESCE(humedad_min, 40.0), COALESCE(humedad_max, 85.0)
                FROM parcels
                ORDER BY id ASC
            """)
            parcelas = []
            for row in cursor.fetchall():
                parcelas.append({
                    "id": int(row[0]),
                    "nombre": str(row[1]),
                    "rangos": {
                        "temp_amb": (float(row[2]), float(row[3])),
                        "temp_suelo": (float(row[4]), float(row[5])),
                        "ph": (float(row[6]), float(row[7])),
                        "lux": (float(row[8]), float(row[9])),
                        "humedad": (float(row[10]), float(row[11])),
                    },
                })
            return parcelas
    except sqlite3.Error as e:
        print(f"[DB] Error al consultar parcelas: {e}")
        return []


class GeneradorProgresivo:
    def __init__(self) -> None:
        self.valores_actuales: dict[str, float] = {}
        self.derivas_activas: dict[str, tuple[int, int]] = {}

    def limpiar_parcelas_eliminadas(self, ids_activos: set[int]) -> None:
        prefijos_validos = tuple(f"p{pid}_" for pid in ids_activos)
        for sid in list(self.valores_actuales.keys()):
            if not sid.startswith(prefijos_validos):
                self.valores_actuales.pop(sid, None)
                self.derivas_activas.pop(sid, None)

    @staticmethod
    def _parametros_sensor(
        sufijo: str, v_min: float, v_max: float
    ) -> tuple[float, float, int, float, float]:
        amplitud = max(0.1, v_max - v_min)

        if sufijo == "temp_amb":
            return min(0.4, max(0.1, amplitud * 0.025)), max(1.5, amplitud * 0.08), 1, -30.0, 70.0
        if sufijo == "temp_suelo":
            return min(0.2, max(0.05, amplitud * 0.015)), max(1.2, amplitud * 0.08), 1, -30.0, 70.0
        if sufijo == "ph":
            return min(0.04, max(0.01, amplitud * 0.02)), max(0.3, amplitud * 0.10), 2, 0.0, 14.0
        if sufijo == "humedad":
            return min(0.8, max(0.2, amplitud * 0.02)), max(3.0, amplitud * 0.08), 1, 0.0, 100.0
        return max(50.0, amplitud * 0.025), max(1000.0, amplitud * 0.08), 0, 0.0, 150000.0

    def siguiente_valor(self, sensor_id: str, sufijo: str, v_min: float, v_max: float) -> float | int:
        paso_max, margen_critico, decimales, lim_inf, lim_sup = self._parametros_sensor(sufijo, v_min, v_max)
        amplitud = max(0.1, v_max - v_min)
        centro = (v_min + v_max) / 2.0

        if sensor_id not in self.valores_actuales:
            holgura = amplitud * 0.20
            valor = random.uniform(v_min + holgura, v_max - holgura)
        else:
            actual = self.valores_actuales[sensor_id]

            if sensor_id not in self.derivas_activas and random.random() < PROBABILIDAD_CRITICO:
                direccion = 1 if actual >= centro else -1
                objetivo = (v_max + margen_critico * 0.5) if direccion == 1 else (v_min - margen_critico * 0.5)
                distancia = abs(objetivo - actual)
                pasos = max(4, min(35, int(distancia / max(paso_max * 0.75, 1e-6)) + 2))
                self.derivas_activas[sensor_id] = (direccion, pasos)

            if sensor_id in self.derivas_activas:
                direccion, restantes = self.derivas_activas[sensor_id]
                valor = actual + direccion * random.uniform(paso_max * 0.6, paso_max)
                valor = max(max(lim_inf, v_min - margen_critico), min(min(lim_sup, v_max + margen_critico), valor))

                if restantes <= 1:
                    self.derivas_activas.pop(sensor_id, None)
                else:
                    self.derivas_activas[sensor_id] = (direccion, restantes - 1)
            elif actual > v_max:
                valor = actual - random.uniform(paso_max * 0.5, paso_max)
            elif actual < v_min:
                valor = actual + random.uniform(paso_max * 0.5, paso_max)
            else:
                atraccion_centro = (centro - actual) * 0.05
                variacion = random.uniform(-paso_max, paso_max)
                valor = max(v_min, min(v_max, actual + atraccion_centro + variacion))

        valor_redondeado = round(valor, decimales)
        if decimales == 0:
            valor_redondeado = int(valor_redondeado)

        self.valores_actuales[sensor_id] = float(valor_redondeado)
        return valor_redondeado


def enviar_lectura(
    sesion: requests.Session, sensor_id: str, valor: float | int, timestamp: str
) -> tuple[str, bool, str]:
    payload = {
        "sensor_id": sensor_id,
        "timestamp": timestamp,
        "value": float(valor),
    }
    try:
        respuesta = sesion.post(f"{URL_API}/{sensor_id}/data", json=payload, timeout=4.0)
        if respuesta.status_code >= 400:
            return sensor_id, False, f"HTTP {respuesta.status_code}: {respuesta.text}"
        return sensor_id, True, ""
    except requests.RequestException as e:
        return sensor_id, False, str(e)


def ejecutar_simulacion() -> None:
    asegurar_db_inicial()
    print(f"Simulador iniciado | DB: {RUTA_DB} | Intervalo: {INTERVALO_SEGUNDOS}s | Modo progresivo")

    generador = GeneradorProgresivo()
    sesion = requests.Session()
    adaptador = requests.adapters.HTTPAdapter(pool_connections=MAX_HILOS_ENVIO, pool_maxsize=MAX_HILOS_ENVIO)
    sesion.mount("http://", adaptador)

    with ThreadPoolExecutor(max_workers=MAX_HILOS_ENVIO) as pool:
        while True:
            inicio_ciclo = time.monotonic()
            parcelas = obtener_parcelas()

            if not parcelas:
                time.sleep(INTERVALO_SEGUNDOS)
                continue

            ids_parcelas = [p["id"] for p in parcelas]
            generador.limpiar_parcelas_eliminadas(set(ids_parcelas))

            timestamp_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lote_lecturas: list[tuple[str, float | int]] = []

            for parcela in parcelas:
                pid = parcela["id"]
                rangos = parcela["rangos"]
                for sufijo in TIPOS_SENSORES:
                    v_min, v_max = rangos[sufijo]
                    sensor_id = f"p{pid}_{sufijo}"
                    valor = generador.siguiente_valor(sensor_id, sufijo, v_min, v_max)
                    lote_lecturas.append((sensor_id, valor))

            futuros = [
                pool.submit(enviar_lectura, sesion, sensor_id, valor, timestamp_actual)
                for sensor_id, valor in lote_lecturas
            ]

            ok = 0
            errores: list[str] = []
            for futuro in as_completed(futuros):
                sensor_id, exito, detalle = futuro.result()
                if exito:
                    ok += 1
                else:
                    errores.append(f"{sensor_id} ({detalle})")

            duracion = round(time.monotonic() - inicio_ciclo, 2)
            print(f"[{timestamp_actual[11:]}] Parcelas {ids_parcelas} -> {ok}/{len(lote_lecturas)} sensores enviados en {duracion}s")

            if errores:
                print(f"  Errores: {', '.join(errores[:3])}")

            espera = max(0.0, INTERVALO_SEGUNDOS - (time.monotonic() - inicio_ciclo))
            time.sleep(espera)


if __name__ == "__main__":
    ejecutar_simulacion()