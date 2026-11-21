import asyncio
import os
import random
import sqlite3
from datetime import datetime, timedelta

import reflex as rx
import websockets

try:
    from login import BaseState
except ImportError:
    from .login import BaseState

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")

DEFINICION_SENSORES_PARCELA: list[tuple[str, str, str]] = [
    ("temp_amb", "temperaturaAmb", "ºC"),
    ("temp_suelo", "temperaturaSuelo", "ºC"),
    ("ph", "ph", "pH"),
    ("lux", "luminosidad", "lux"),
    ("humedad", "humedadSuelo", "%"),
]


SVG_CAMPO = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <polygon points="90,26 146,52 90,78 34,52" fill="#6BBF6B" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="62" y1="39" x2="118" y2="65" stroke="#EBF0F2" stroke-width="2.5"/>
  <line x1="118" y1="39" x2="62" y2="65" stroke="#EBF0F2" stroke-width="2.5"/>
  <path d="M68,14 C61,14 56,19 56,26 C56,35 68,46 68,46 C68,46 80,35 80,26 C80,19 75,14 68,14 Z" fill="#81C784" stroke="#2F6F3E" stroke-width="2"/>
  <circle cx="68" cy="25" r="4" fill="#FFFFFF"/>
</svg>
"""

SVG_SURCOS = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <polygon points="92,28 148,54 88,82 32,56" fill="#6BBF6B" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="46" y1="50" x2="104" y2="76" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="58" y1="44" x2="116" y2="70" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="70" y1="38" x2="128" y2="64" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="82" y1="33" x2="140" y2="59" stroke="#2F6F3E" stroke-width="1.6"/>
  <path d="M62,14 C55,14 50,19 50,26 C50,35 62,46 62,46 C62,46 74,35 74,26 C74,19 69,14 62,14 Z" fill="#81C784" stroke="#2F6F3E" stroke-width="2"/>
  <circle cx="62" cy="25" r="4" fill="#FFFFFF"/>
</svg>
"""

SVG_INVERNADERO = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <path d="M44,58 L44,40 C44,24 76,24 76,40 L76,58 Z" fill="rgba(107,191,107,0.18)" stroke="#2F6F3E" stroke-width="2"/>
  <path d="M44,40 C44,24 76,24 76,40 L134,26 C134,12 104,12 104,26 Z" fill="rgba(107,191,107,0.12)" stroke="#2F6F3E" stroke-width="1.8"/>
  <polyline points="76,58 134,44 134,26" fill="none" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="44" y1="58" x2="76" y2="58" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="60" y1="28" x2="60" y2="58" stroke="#2F6F3E" stroke-width="1.4"/>
  <line x1="95" y1="35" x2="95" y2="53" stroke="#2F6F3E" stroke-width="1.4"/>
  <line x1="115" y1="30" x2="115" y2="48" stroke="#2F6F3E" stroke-width="1.4"/>
  <line x1="44" y1="45" x2="134" y2="31" stroke="#2F6F3E" stroke-width="1.3"/>
</svg>
"""

SVG_VINEDO = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <line x1="40" y1="68" x2="95" y2="26" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="65" y1="74" x2="120" y2="32" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="90" y1="80" x2="145" y2="38" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="40" y1="54" x2="95" y2="14" stroke="#2F6F3E" stroke-width="1.3" stroke-dasharray="3,2"/>
  <line x1="65" y1="60" x2="120" y2="20" stroke="#2F6F3E" stroke-width="1.3" stroke-dasharray="3,2"/>
  <line x1="90" y1="66" x2="145" y2="26" stroke="#2F6F3E" stroke-width="1.3" stroke-dasharray="3,2"/>
  <line x1="45" y1="48" x2="45" y2="72" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="70" y1="54" x2="70" y2="78" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="95" y1="60" x2="95" y2="84" stroke="#2F6F3E" stroke-width="2"/>
  <circle cx="56" cy="52" r="4" fill="#6BBF6B"/>
  <circle cx="81" cy="58" r="4" fill="#6BBF6B"/>
  <circle cx="106" cy="64" r="4" fill="#6BBF6B"/>
</svg>
"""

SVG_HUERTO = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <rect x="34" y="18" width="112" height="64" rx="8" fill="rgba(107,191,107,0.14)" stroke="#2F6F3E" stroke-width="2"/>
  <rect x="42" y="25" width="38" height="22" rx="3" fill="#6BBF6B" opacity="0.75"/>
  <rect x="42" y="53" width="38" height="22" rx="3" fill="#6BBF6B" opacity="0.55"/>
  <line x1="46" y1="59" x2="76" y2="59" stroke="#2F6F3E" stroke-width="1.5"/>
  <line x1="46" y1="65" x2="76" y2="65" stroke="#2F6F3E" stroke-width="1.5"/>
  <line x1="46" y1="71" x2="76" y2="71" stroke="#2F6F3E" stroke-width="1.5"/>
  <rect x="88" y="25" width="18" height="50" rx="3" fill="rgba(77,208,225,0.22)" stroke="#2F6F3E" stroke-width="1.4"/>
  <circle cx="97" cy="36" r="3" fill="#2F6F3E"/>
  <circle cx="97" cy="50" r="3" fill="#2F6F3E"/>
  <circle cx="97" cy="64" r="3" fill="#2F6F3E"/>
  <rect x="114" y="25" width="24" height="50" rx="3" fill="rgba(107,191,107,0.28)" stroke="#2F6F3E" stroke-width="1.4"/>
  <circle cx="126" cy="60" r="5" fill="#6BBF6B" stroke="#2F6F3E" stroke-width="1.4"/>
</svg>
"""


def detectar_icono_parcela(nombre: str, cultivo: str) -> str:
    texto = f"{nombre} {cultivo}".lower()
    if any(k in texto for k in ("invernadero", "tomate", "pimiento", "pepino", "calabacin", "calabacín")):
        return "invernadero"
    if any(k in texto for k in ("viñedo", "vinedo", "vid", "uva", "parra")):
        return "vinedo"
    if any(k in texto for k in ("huerto", "hortaliza", "lechuga", "frutal")):
        return "huerto"
    if any(k in texto for k in ("sur", "trigo", "cebada", "cereal", "olivar")):
        return "surcos"
    return "campo"


def _parsear_rango(min_txt: str, max_txt: str, etiqueta: str) -> tuple[float, float]:
    try:
        v_min = float(min_txt.replace(",", ".").strip())
        v_max = float(max_txt.replace(",", ".").strip())
    except ValueError:
        raise ValueError(f"Los límites de {etiqueta} deben ser valores numéricos.")
    if v_min > v_max:
        raise ValueError(f"En {etiqueta}, el mínimo ({v_min}) no puede ser mayor que el máximo ({v_max}).")
    return v_min, v_max


def _columna_id_sensors(cursor: sqlite3.Cursor) -> str:
    """Detecta si la clave primaria de la tabla sensors se llama 'id' o 'sensor_id'."""
    cursor.execute("PRAGMA table_info(sensors)")
    columnas = {fila[1] for fila in cursor.fetchall()}
    return "sensor_id" if "sensor_id" in columnas and "id" not in columnas else "id"


def _registrar_sensores_parcela(cursor: sqlite3.Cursor, parcela_id: int) -> None:
    """Crea en la tabla sensors los 5 sensores estándar de la parcela si no existen."""
    col_id = _columna_id_sensors(cursor)
    for sufijo, tipo, unidad in DEFINICION_SENSORES_PARCELA:
        sensor_id = f"p{parcela_id}_{sufijo}"
        cursor.execute(
            f"INSERT OR IGNORE INTO sensors ({col_id}, parcel_id, type, unit) VALUES (?, ?, ?, ?)",
            (sensor_id, parcela_id, tipo, unidad),
        )


def _generar_muestras_rango_y_criticos(
    sufijo: str, v_min: float, v_max: float
) -> list[float]:
    """
    Genera 6 valores iniciales: 4 dentro de [v_min, v_max] y 2 fuera de rango
    (uno por debajo del mínimo y otro por encima del máximo) para verificar alertas.
    """
    amplitud = max(0.1, v_max - v_min)
    if sufijo in ("temp_amb", "temp_suelo"):
        margen = max(2.0, amplitud * 0.10)
        decimales = 1
        limite_inf, limite_sup = -30.0, 70.0
    elif sufijo == "ph":
        margen = max(0.5, amplitud * 0.15)
        decimales = 2
        limite_inf, limite_sup = 0.0, 14.0
    elif sufijo == "humedad":
        margen = max(5.0, amplitud * 0.10)
        decimales = 1
        limite_inf, limite_sup = 0.0, 100.0
    else:  # lux
        margen = max(500.0, amplitud * 0.10)
        decimales = 0
        limite_inf, limite_sup = 0.0, 150000.0

    paso = 0.1 if decimales > 0 else 1.0
    bajo_min = max(limite_inf, round(random.uniform(v_min - margen, v_min - paso), decimales))
    sobre_max = min(limite_sup, round(random.uniform(v_max + paso, v_max + margen), decimales))

    normales = [round(random.uniform(v_min, v_max), decimales) for _ in range(4)]
    muestras = [normales[0], bajo_min, normales[1], normales[2], sobre_max, normales[3]]
    return [int(v) if decimales == 0 else v for v in muestras]


def _poblar_datos_iniciales_parcela(
    cursor: sqlite3.Cursor,
    parcela_id: int,
    rangos: dict[str, tuple[float, float]],
) -> None:
    """Inserta lecturas iniciales (normales + fuera de rango) para los 5 sensores de la parcela."""
    ahora = datetime.now()
    for sufijo, (v_min, v_max) in rangos.items():
        sensor_id = f"p{parcela_id}_{sufijo}"
        muestras = _generar_muestras_rango_y_criticos(sufijo, v_min, v_max)
        for indice, valor in enumerate(muestras):
            ts = (ahora - timedelta(minutes=(len(muestras) - indice) * 5)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO sensor_data (sensor_id, timestamp, value) VALUES (?, ?, ?)",
                (sensor_id, ts, valor),
            )


class GestorParcelasState(BaseState):
    _token_streaming: int = 0
    _ultimo_id_sensor: int = -1

    rol_usuario: str = ""
    parcelas_lista: list[list[str]] = []

    # Formulario de alta de nueva parcela
    nueva_nombre: str = ""
    nueva_ubicacion: str = ""
    nuevo_cultivo: str = ""

    nueva_temp_amb_min: str = "15.0"
    nueva_temp_amb_max: str = "32.0"
    nueva_temp_suelo_min: str = "12.0"
    nueva_temp_suelo_max: str = "28.0"
    nueva_ph_min: str = "5.5"
    nueva_ph_max: str = "7.5"
    nueva_lux_min: str = "200"
    nueva_lux_max: str = "50000"
    nueva_humedad_min: str = "40"
    nueva_humedad_max: str = "85"

    # Filtros de búsqueda
    filtro_busqueda: str = ""
    filtro_estado: str = "Todas"

    # Mensajes
    error_mensaje: str = ""
    exito_mensaje: str = ""

    # Modal de edición de rangos, mantenimiento y cuaderno
    modal_abierto: bool = False
    edit_id: str = ""
    edit_nombre: str = ""
    edit_ubicacion: str = ""
    edit_cultivo: str = ""
    edit_superficie: str = ""
    edit_en_mantenimiento: bool = False
    edit_notas: str = ""

    edit_temp_amb_min: str = ""
    edit_temp_amb_max: str = ""
    edit_temp_suelo_min: str = ""
    edit_temp_suelo_max: str = ""
    edit_ph_min: str = ""
    edit_ph_max: str = ""
    edit_lux_min: str = ""
    edit_lux_max: str = ""
    edit_humedad_min: str = ""
    edit_humedad_max: str = ""

    @rx.var
    def total_parcelas(self) -> int:
        return len(self.parcelas_lista)

    @rx.var
    def total_criticas(self) -> int:
        return sum(1 for p in self.parcelas_lista if len(p) > 11 and p[11] == "1")

    @rx.var
    def parcelas_filtradas(self) -> list[list[str]]:
        termino = self.filtro_busqueda.strip().lower()
        resultado: list[list[str]] = []
        for p in self.parcelas_lista:
            en_mant = p[5] == "1"
            es_crit = p[11] == "1"

            if self.filtro_estado == "Críticas" and not es_crit:
                continue
            elif self.filtro_estado == "En mantenimiento" and not en_mant:
                continue
            elif self.filtro_estado == "Operativas" and (en_mant or es_crit):
                continue

            if termino:
                bloque = f"{p[1]} {p[2]} {p[3]} {p[0]}".lower()
                if termino not in bloque:
                    continue
            resultado.append(p)
        return resultado

    # Setters formulario alta
    def set_nueva_nombre(self, val: str):
        self.nueva_nombre = val

    def set_nueva_ubicacion(self, val: str):
        self.nueva_ubicacion = val

    def set_nuevo_cultivo(self, val: str):
        self.nuevo_cultivo = val

    def set_nueva_temp_amb_min(self, val: str):
        self.nueva_temp_amb_min = val

    def set_nueva_temp_amb_max(self, val: str):
        self.nueva_temp_amb_max = val

    def set_nueva_temp_suelo_min(self, val: str):
        self.nueva_temp_suelo_min = val

    def set_nueva_temp_suelo_max(self, val: str):
        self.nueva_temp_suelo_max = val

    def set_nueva_ph_min(self, val: str):
        self.nueva_ph_min = val

    def set_nueva_ph_max(self, val: str):
        self.nueva_ph_max = val

    def set_nueva_lux_min(self, val: str):
        self.nueva_lux_min = val

    def set_nueva_lux_max(self, val: str):
        self.nueva_lux_max = val

    def set_nueva_humedad_min(self, val: str):
        self.nueva_humedad_min = val

    def set_nueva_humedad_max(self, val: str):
        self.nueva_humedad_max = val

    # Setters filtros y modal
    def set_filtro_busqueda(self, val: str):
        self.filtro_busqueda = val

    def set_filtro_estado(self, val: str):
        self.filtro_estado = val

    def set_modal_abierto(self, val: bool):
        self.modal_abierto = val

    def set_edit_nombre(self, val: str):
        self.edit_nombre = val

    def set_edit_ubicacion(self, val: str):
        self.edit_ubicacion = val

    def set_edit_cultivo(self, val: str):
        self.edit_cultivo = val

    def set_edit_superficie(self, val: str):
        self.edit_superficie = val

    def set_edit_en_mantenimiento(self, val: bool):
        self.edit_en_mantenimiento = val

    def set_edit_notas(self, val: str):
        self.edit_notas = val

    def set_edit_temp_amb_min(self, val: str):
        self.edit_temp_amb_min = val

    def set_edit_temp_amb_max(self, val: str):
        self.edit_temp_amb_max = val

    def set_edit_temp_suelo_min(self, val: str):
        self.edit_temp_suelo_min = val

    def set_edit_temp_suelo_max(self, val: str):
        self.edit_temp_suelo_max = val

    def set_edit_ph_min(self, val: str):
        self.edit_ph_min = val

    def set_edit_ph_max(self, val: str):
        self.edit_ph_max = val

    def set_edit_lux_min(self, val: str):
        self.edit_lux_min = val

    def set_edit_lux_max(self, val: str):
        self.edit_lux_max = val

    def set_edit_humedad_min(self, val: str):
        self.edit_humedad_min = val

    def set_edit_humedad_max(self, val: str):
        self.edit_humedad_max = val

    def comprobar_acceso_parcelas(self):
        if self.usuario_actual == "":
            return rx.redirect("/")

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT role FROM users WHERE username = ?", (self.usuario_actual,))
                resultado = cursor.fetchone()
                if not resultado or resultado[0] not in ("administrador", "tecnico_agricola"):
                    return rx.redirect("/panel")
                self.rol_usuario = resultado[0]
        except sqlite3.Error:
            return rx.redirect("/panel")

        self.error_mensaje = ""
        self.exito_mensaje = ""
        self._asegurar_esquema_parcelas()
        self.cargar_parcelas()
        return GestorParcelasState.iniciar_streaming_parcelas

    async def _escuchar_websocket_parcela(self, pid: int, token: int):
        """Escucha el canal WebSocket de una parcela concreta y actualiza en tiempo real."""
        uri = f"ws://localhost:8001/ws/parcels/{pid}"
        while True:
            async with self:
                if self._token_streaming != token or self.usuario_actual == "":
                    return
                if not any(p[0] == str(pid) for p in self.parcelas_lista):
                    return

            try:
                async with websockets.connect(uri) as websocket:
                    while True:
                        async with self:
                            if self._token_streaming != token or self.usuario_actual == "":
                                return
                        await websocket.recv()
                        async with self:
                            if self._token_streaming != token:
                                return
                            self.cargar_parcelas()
            except asyncio.CancelledError:
                return
            except Exception:
                await asyncio.sleep(2.0)

    @rx.event(background=True)
    async def iniciar_streaming_parcelas(self):
        """Mantiene actualizadas las tarjetas en tiempo real mediante WebSockets y respaldo SQLite."""
        async with self:
            self._token_streaming += 1
            mi_token = self._token_streaming

        tareas_ws: dict[int, asyncio.Task] = {}

        try:
            while True:
                async with self:
                    if self._token_streaming != mi_token or self.usuario_actual == "":
                        break
                    ids_actuales = [int(p[0]) for p in self.parcelas_lista]

                for pid in ids_actuales:
                    if pid not in tareas_ws or tareas_ws[pid].done():
                        tareas_ws[pid] = asyncio.create_task(
                            self._escuchar_websocket_parcela(pid, mi_token)
                        )

                try:
                    with sqlite3.connect(RUTA_DB) as conexion:
                        cursor = conexion.cursor()
                        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM sensor_data")
                        fila_max = cursor.fetchone()
                        max_id_actual = int(fila_max[0]) if fila_max else 0

                    async with self:
                        if self._token_streaming != mi_token:
                            break
                        if max_id_actual != self._ultimo_id_sensor:
                            self._ultimo_id_sensor = max_id_actual
                            self.cargar_parcelas()
                except sqlite3.Error:
                    pass

                await asyncio.sleep(1.5)
        finally:
            for tarea in tareas_ws.values():
                if not tarea.done():
                    tarea.cancel()

    def _asegurar_esquema_parcelas(self):
        columnas_necesarias = {
            "crop": "TEXT DEFAULT 'Sin especificar'",
            "area": "TEXT DEFAULT '1.5 ha'",
            "en_mantenimiento": "INTEGER DEFAULT 0",
            "notes": "TEXT DEFAULT ''",
            "temp_amb_min": "REAL DEFAULT 15.0",
            "temp_amb_max": "REAL DEFAULT 32.0",
            "temp_suelo_min": "REAL DEFAULT 12.0",
            "temp_suelo_max": "REAL DEFAULT 28.0",
            "ph_min": "REAL DEFAULT 5.5",
            "ph_max": "REAL DEFAULT 7.5",
            "lux_min": "REAL DEFAULT 200.0",
            "lux_max": "REAL DEFAULT 50000.0",
            "humedad_min": "REAL DEFAULT 40.0",
            "humedad_max": "REAL DEFAULT 85.0",
        }
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS parcels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        location TEXT
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
                cursor.execute("PRAGMA table_info(parcels)")
                existentes = {fila[1] for fila in cursor.fetchall()}

                for col, definicion in columnas_necesarias.items():
                    if col not in existentes:
                        cursor.execute(f"ALTER TABLE parcels ADD COLUMN {col} {definicion}")

                conexion.commit()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al preparar base de datos: {e}"

    def cargar_parcelas(self):
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    SELECT id, name, location,
                           COALESCE(crop, 'Sin especificar'),
                           COALESCE(area, '1.5 ha'),
                           COALESCE(en_mantenimiento, 0),
                           COALESCE(notes, ''),
                           COALESCE(temp_amb_min, 15.0),
                           COALESCE(temp_amb_max, 32.0),
                           COALESCE(temp_suelo_min, 12.0),
                           COALESCE(temp_suelo_max, 28.0),
                           COALESCE(ph_min, 5.5),
                           COALESCE(ph_max, 7.5),
                           COALESCE(lux_min, 200.0),
                           COALESCE(lux_max, 50000.0),
                           COALESCE(humedad_min, 40.0),
                           COALESCE(humedad_max, 85.0)
                    FROM parcels
                    ORDER BY id ASC
                """)
                filas = cursor.fetchall()

                if not filas:
                    semilla = [
                        ("Parcela Norte", "Sector A", "Maíz", "2.4 ha", 0, "", 15.0, 32.0, 12.0, 28.0, 5.5, 7.5, 200.0, 50000.0, 40.0, 85.0),
                        ("Parcela Sur", "Sector B", "Trigo", "3.1 ha", 0, "", 12.0, 30.0, 10.0, 26.0, 6.0, 7.5, 200.0, 50000.0, 35.0, 80.0),
                        ("Invernadero Principal", "Sector C", "Tomate", "0.8 ha", 0, "", 18.0, 30.0, 15.0, 26.0, 5.8, 6.8, 300.0, 45000.0, 55.0, 85.0),
                        ("Viñedo Este", "Sector D", "Vid", "4.0 ha", 0, "", 14.0, 34.0, 12.0, 28.0, 5.5, 7.5, 300.0, 60000.0, 35.0, 75.0),
                        ("Huerto Central", "Sector E", "Hortalizas", "1.2 ha", 0, "", 15.0, 29.0, 13.0, 25.0, 6.0, 7.2, 200.0, 45000.0, 50.0, 85.0),
                    ]
                    cursor.executemany("""
                        INSERT INTO parcels (
                            name, location, crop, area, en_mantenimiento, notes,
                            temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                            ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, semilla)
                    conexion.commit()
                    cursor.execute("""
                        SELECT id, name, location, crop, area, en_mantenimiento, notes,
                               temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                               ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
                        FROM parcels
                        ORDER BY id ASC
                    """)
                    filas = cursor.fetchall()

                # Asegura que toda parcela tenga sus 5 sensores dados de alta en 'sensors'
                for row in filas:
                    _registrar_sensores_parcela(cursor, int(row[0]))
                conexion.commit()

                conteo_sensores: dict[int, int] = {}
                cursor.execute("SELECT parcel_id, COUNT(*) FROM sensors GROUP BY parcel_id")
                for p_id_reg, total_s in cursor.fetchall():
                    if p_id_reg is not None:
                        conteo_sensores[int(p_id_reg)] = int(total_s)

                ultimos_valores: dict[str, float] = {}
                cursor.execute("SELECT COALESCE(MAX(id), 0) FROM sensor_data")
                fila_max = cursor.fetchone()
                if fila_max:
                    self._ultimo_id_sensor = int(fila_max[0])

                cursor.execute("""
                    SELECT sensor_id, value FROM sensor_data
                    WHERE id IN (SELECT MAX(id) FROM sensor_data GROUP BY sensor_id)
                """)
                for sid, val in cursor.fetchall():
                    if sid and val is not None:
                        ultimos_valores[str(sid)] = float(val)

                lista_construida: list[list[str]] = []
                for row in filas:
                    pid = int(row[0])
                    nombre = str(row[1])
                    ubicacion = str(row[2]) if row[2] else "Sin sector"
                    cultivo = str(row[3]) if row[3] else "Sin especificar"
                    superficie = str(row[4]) if row[4] else "1.5 ha"
                    en_mant = int(row[5]) if row[5] is not None else 0
                    notas = str(row[6]) if row[6] else ""

                    t_amb_min, t_amb_max = float(row[7]), float(row[8])
                    t_sue_min, t_sue_max = float(row[9]), float(row[10])
                    ph_min, ph_max = float(row[11]), float(row[12])
                    lux_min, lux_max = float(row[13]), float(row[14])
                    hum_min, hum_max = float(row[15]), float(row[16])

                    v_t_amb = ultimos_valores.get(f"p{pid}_temp_amb")
                    v_t_sue = ultimos_valores.get(f"p{pid}_temp_suelo")
                    v_ph = ultimos_valores.get(f"p{pid}_ph")
                    v_lux = ultimos_valores.get(f"p{pid}_lux")
                    v_hum = ultimos_valores.get(f"p{pid}_humedad")

                    alertas: list[str] = []
                    crit_t_amb = "0"
                    crit_t_sue = "0"
                    crit_ph = "0"
                    crit_lux = "0"
                    crit_hum = "0"

                    if v_t_amb is not None:
                        if v_t_amb > t_amb_max:
                            crit_t_amb = "1"
                            alertas.append(f"Tª Ambiente por encima del máximo ({round(v_t_amb, 1)} ºC / máx. {t_amb_max} ºC)")
                        elif v_t_amb < t_amb_min:
                            crit_t_amb = "1"
                            alertas.append(f"Tª Ambiente por debajo del mínimo ({round(v_t_amb, 1)} ºC / mín. {t_amb_min} ºC)")

                    if v_t_sue is not None:
                        if v_t_sue > t_sue_max:
                            crit_t_sue = "1"
                            alertas.append(f"Tª Suelo por encima del máximo ({round(v_t_sue, 1)} ºC / máx. {t_sue_max} ºC)")
                        elif v_t_sue < t_sue_min:
                            crit_t_sue = "1"
                            alertas.append(f"Tª Suelo por debajo del mínimo ({round(v_t_sue, 1)} ºC / mín. {t_sue_min} ºC)")

                    if v_ph is not None:
                        if v_ph > ph_max:
                            crit_ph = "1"
                            alertas.append(f"pH por encima del máximo ({round(v_ph, 2)} / máx. {ph_max})")
                        elif v_ph < ph_min:
                            crit_ph = "1"
                            alertas.append(f"pH por debajo del mínimo ({round(v_ph, 2)} / mín. {ph_min})")

                    if v_lux is not None:
                        if v_lux > lux_max:
                            crit_lux = "1"
                            alertas.append(f"Luminosidad por encima del máximo ({int(round(v_lux))} lux / máx. {int(lux_max)} lux)")
                        elif v_lux < lux_min:
                            crit_lux = "1"
                            alertas.append(f"Luminosidad por debajo del mínimo ({int(round(v_lux))} lux / mín. {int(lux_min)} lux)")

                    if v_hum is not None:
                        if v_hum > hum_max:
                            crit_hum = "1"
                            alertas.append(f"Humedad por encima del máximo ({round(v_hum, 1)}% / máx. {hum_max}%)")
                        elif v_hum < hum_min:
                            crit_hum = "1"
                            alertas.append(f"Humedad por debajo del mínimo ({round(v_hum, 1)}% / mín. {hum_min}%)")

                    n_sens = conteo_sensores.get(pid, 5)
                    sens_str = f"{n_sens} sensores" if n_sens != 1 else "1 sensor"

                    lista_construida.append([
                        str(pid),
                        nombre,
                        ubicacion,
                        cultivo,
                        superficie,
                        "1" if en_mant == 1 else "0",
                        notas,
                        f"{round(v_t_amb, 1)} ºC" if v_t_amb is not None else "-- ºC",
                        f"{int(round(v_hum))} %" if v_hum is not None else "-- %",
                        sens_str,
                        detectar_icono_parcela(nombre, cultivo),
                        "1" if len(alertas) > 0 else "0",
                        "\n".join(alertas),
                        str(t_amb_min),
                        str(t_amb_max),
                        str(t_sue_min),
                        str(t_sue_max),
                        str(ph_min),
                        str(ph_max),
                        str(lux_min),
                        str(lux_max),
                        str(hum_min),
                        str(hum_max),
                        f"{round(v_t_sue, 1)} ºC" if v_t_sue is not None else "-- ºC",
                        f"{round(v_ph, 2)} pH" if v_ph is not None else "-- pH",
                        f"{int(round(v_lux))} lux" if v_lux is not None else "-- lux",
                        crit_t_amb,
                        crit_t_sue,
                        crit_ph,
                        crit_lux,
                        crit_hum,
                    ])

                self.parcelas_lista = lista_construida
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al cargar parcelas: {e}"

    def anadir_parcela(self):
        self.error_mensaje = ""
        self.exito_mensaje = ""

        nombre = self.nueva_nombre.strip()
        ubicacion = self.nueva_ubicacion.strip()
        cultivo = self.nuevo_cultivo.strip() or "Sin especificar"

        if not nombre or not ubicacion:
            self.error_mensaje = "Indica el nombre de la parcela y su ubicación o sector."
            return

        try:
            t_amb_min, t_amb_max = _parsear_rango(self.nueva_temp_amb_min, self.nueva_temp_amb_max, "Temperatura ambiental")
            t_sue_min, t_sue_max = _parsear_rango(self.nueva_temp_suelo_min, self.nueva_temp_suelo_max, "Temperatura del suelo")
            ph_min, ph_max = _parsear_rango(self.nueva_ph_min, self.nueva_ph_max, "pH")
            lux_min, lux_max = _parsear_rango(self.nueva_lux_min, self.nueva_lux_max, "Luminosidad")
            hum_min, hum_max = _parsear_rango(self.nueva_humedad_min, self.nueva_humedad_max, "Humedad")
        except ValueError as err:
            self.error_mensaje = str(err)
            return

        try:
            self._asegurar_esquema_parcelas()
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    INSERT INTO parcels (
                        name, location, crop, area, en_mantenimiento, notes,
                        temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                        ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
                    ) VALUES (?, ?, ?, ?, 0, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nombre, ubicacion, cultivo, "1.5 ha",
                    t_amb_min, t_amb_max, t_sue_min, t_sue_max,
                    ph_min, ph_max, lux_min, lux_max, hum_min, hum_max
                ))
                nueva_id = int(cursor.lastrowid)

                # Alta automática de los 5 sensores (p{id}_temp_amb, p{id}_temp_suelo, p{id}_ph, p{id}_lux, p{id}_humedad)
                _registrar_sensores_parcela(cursor, nueva_id)

                # Inserta una tanda inicial con valores dentro del rango y un par fuera de límite
                rangos_parcela = {
                    "temp_amb": (t_amb_min, t_amb_max),
                    "temp_suelo": (t_sue_min, t_sue_max),
                    "ph": (ph_min, ph_max),
                    "lux": (lux_min, lux_max),
                    "humedad": (hum_min, hum_max),
                }
                _poblar_datos_iniciales_parcela(cursor, nueva_id, rangos_parcela)
                conexion.commit()

            self.nueva_nombre = ""
            self.nueva_ubicacion = ""
            self.nuevo_cultivo = ""
            self.exito_mensaje = f"Parcela '{nombre}' (#{nueva_id}) creada con sus 5 sensores y lecturas iniciales."
            self.cargar_parcelas()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al añadir parcela: {e}"

    def cambiar_mantenimiento(self, parcela_id: str, activo: bool):
        self.error_mensaje = ""
        self.exito_mensaje = ""
        valor_db = 1 if activo else 0
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute(
                    "UPDATE parcels SET en_mantenimiento = ? WHERE id = ?",
                    (valor_db, int(parcela_id))
                )
                conexion.commit()
            self.cargar_parcelas()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al cambiar estado de mantenimiento: {e}"

    def abrir_ficha_parcela(self, parcela: list[str]):
        self.error_mensaje = ""
        self.exito_mensaje = ""
        self.edit_id = parcela[0]
        self.edit_nombre = parcela[1]
        self.edit_ubicacion = parcela[2]
        self.edit_cultivo = parcela[3]
        self.edit_superficie = parcela[4]
        self.edit_en_mantenimiento = parcela[5] == "1"
        self.edit_notas = parcela[6]

        self.edit_temp_amb_min = parcela[13]
        self.edit_temp_amb_max = parcela[14]
        self.edit_temp_suelo_min = parcela[15]
        self.edit_temp_suelo_max = parcela[16]
        self.edit_ph_min = parcela[17]
        self.edit_ph_max = parcela[18]
        self.edit_lux_min = parcela[19]
        self.edit_lux_max = parcela[20]
        self.edit_humedad_min = parcela[21]
        self.edit_humedad_max = parcela[22]

        self.modal_abierto = True

    def guardar_ficha_parcela(self):
        if not self.edit_nombre.strip() or not self.edit_ubicacion.strip():
            self.error_mensaje = "El nombre y la ubicación no pueden quedar vacíos."
            return

        try:
            t_amb_min, t_amb_max = _parsear_rango(self.edit_temp_amb_min, self.edit_temp_amb_max, "Temperatura ambiental")
            t_sue_min, t_sue_max = _parsear_rango(self.edit_temp_suelo_min, self.edit_temp_suelo_max, "Temperatura del suelo")
            ph_min, ph_max = _parsear_rango(self.edit_ph_min, self.edit_ph_max, "pH")
            lux_min, lux_max = _parsear_rango(self.edit_lux_min, self.edit_lux_max, "Luminosidad")
            hum_min, hum_max = _parsear_rango(self.edit_humedad_min, self.edit_humedad_max, "Humedad")
        except ValueError as err:
            self.error_mensaje = str(err)
            return

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    UPDATE parcels
                    SET name = ?, location = ?, crop = ?, area = ?,
                        en_mantenimiento = ?, notes = ?,
                        temp_amb_min = ?, temp_amb_max = ?,
                        temp_suelo_min = ?, temp_suelo_max = ?,
                        ph_min = ?, ph_max = ?,
                        lux_min = ?, lux_max = ?,
                        humedad_min = ?, humedad_max = ?
                    WHERE id = ?
                """, (
                    self.edit_nombre.strip(),
                    self.edit_ubicacion.strip(),
                    self.edit_cultivo.strip() or "Sin especificar",
                    self.edit_superficie.strip() or "1.5 ha",
                    1 if self.edit_en_mantenimiento else 0,
                    self.edit_notas.strip(),
                    t_amb_min, t_amb_max,
                    t_sue_min, t_sue_max,
                    ph_min, ph_max,
                    lux_min, lux_max,
                    hum_min, hum_max,
                    int(self.edit_id)
                ))
                conexion.commit()

            self.modal_abierto = False
            self.exito_mensaje = f"Rangos y ficha de '{self.edit_nombre}' actualizados."
            self.cargar_parcelas()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al actualizar parcela: {e}"

    def eliminar_parcela_actual(self):
        try:
            pid = int(self.edit_id)
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("DELETE FROM parcels WHERE id = ?", (pid,))
                cursor.execute("DELETE FROM sensors WHERE parcel_id = ?", (pid,))
                cursor.execute("DELETE FROM sensor_data WHERE sensor_id LIKE ?", (f"p{pid}_%",))
                conexion.commit()

            self.modal_abierto = False
            self.exito_mensaje = f"Parcela '{self.edit_nombre}' y sus sensores eliminados."
            self.cargar_parcelas()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al eliminar parcela: {e}"


def bloque_rango_sensor(
    titulo: str,
    val_min: str,
    on_change_min,
    val_max: str,
    on_change_max,
) -> rx.Component:
    return rx.vstack(
        rx.text(titulo, size="2", weight="medium", color="var(--gray-12)"),
        rx.hstack(
            rx.input(
                placeholder="Mín",
                value=val_min,
                on_change=on_change_min,
                size="2",
                variant="surface",
                width="100%",
            ),
            rx.input(
                placeholder="Máx",
                value=val_max,
                on_change=on_change_max,
                size="2",
                variant="surface",
                width="100%",
            ),
            spacing="2",
            width="100%",
        ),
        padding="0.75em",
        border_radius="10px",
        background_color="var(--gray-3)",
        border="1px solid var(--gray-4)",
        spacing="2",
        align="start",
        width="100%",
    )


def ilustracion_parcela(tipo: str) -> rx.Component:
    return rx.center(
        rx.match(
            tipo,
            ("invernadero", rx.html(SVG_INVERNADERO)),
            ("vinedo", rx.html(SVG_VINEDO)),
            ("huerto", rx.html(SVG_HUERTO)),
            ("surcos", rx.html(SVG_SURCOS)),
            rx.html(SVG_CAMPO),
        ),
        width="100%",
        height="104px",
        border_radius="12px",
        background_color="var(--gray-3)",
        border="1px solid var(--gray-4)",
        margin_y="0.35em",
    )


def tarjeta_parcela(parcela: list[str]) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading(
                    parcela[1],
                    size="4",
                    weight="bold",
                    color="var(--gray-12)",
                    line_height="1.2",
                ),
                rx.badge(
                    "ID #" + parcela[0],
                    color_scheme="grass",
                    variant="soft",
                    radius="full",
                    size="2",
                ),
                justify="between",
                align="start",
                width="100%",
                spacing="2",
            ),

            rx.vstack(
                rx.text(parcela[2], size="2", color="var(--gray-11)"),
                rx.text(
                    "Cultivo: ",
                    rx.text.span(parcela[3], weight="medium", color="var(--gray-12)"),
                    size="2",
                    color="var(--gray-11)",
                ),
                rx.hstack(
                    rx.cond(
                        parcela[5] == "1",
                        rx.badge(
                            rx.icon("wrench", size=12),
                            "En mantenimiento",
                            color_scheme="amber",
                            variant="soft",
                            size="1",
                        ),
                        rx.cond(
                            parcela[11] == "1",
                            rx.badge(
                                rx.icon("triangle-alert", size=12),
                                "Crítico",
                                color_scheme="red",
                                variant="solid",
                                size="1",
                            ),
                            rx.badge(
                                rx.icon("circle-check", size=12),
                                "Operativa",
                                color_scheme="grass",
                                variant="outline",
                                size="1",
                            ),
                        ),
                    ),
                    rx.badge(parcela[9], color_scheme="gray", variant="soft", size="1"),
                    spacing="2",
                    align="center",
                    wrap="wrap",
                    padding_top="0.2em",
                ),
                spacing="1",
                align="start",
                width="100%",
            ),

            ilustracion_parcela(parcela[10]),

            rx.flex(
                rx.badge(
                    rx.icon("thermometer", size=12),
                    "Amb: ",
                    parcela[7],
                    color_scheme=rx.cond(parcela[26] == "1", "red", "gray"),
                    variant=rx.cond(parcela[26] == "1", "solid", "soft"),
                    radius="full",
                    size="1",
                ),
                rx.badge(
                    rx.icon("sprout", size=12),
                    "Suelo: ",
                    parcela[23],
                    color_scheme=rx.cond(parcela[27] == "1", "red", "gray"),
                    variant=rx.cond(parcela[27] == "1", "solid", "soft"),
                    radius="full",
                    size="1",
                ),
                rx.badge(
                    rx.icon("flask-conical", size=12),
                    parcela[24],
                    color_scheme=rx.cond(parcela[28] == "1", "red", "gray"),
                    variant=rx.cond(parcela[28] == "1", "solid", "soft"),
                    radius="full",
                    size="1",
                ),
                rx.badge(
                    rx.icon("sun", size=12),
                    parcela[25],
                    color_scheme=rx.cond(parcela[29] == "1", "red", "gray"),
                    variant=rx.cond(parcela[29] == "1", "solid", "soft"),
                    radius="full",
                    size="1",
                ),
                rx.badge(
                    rx.icon("droplets", size=12),
                    parcela[8],
                    color_scheme=rx.cond(parcela[30] == "1", "red", "blue"),
                    variant=rx.cond(parcela[30] == "1", "solid", "soft"),
                    radius="full",
                    size="1",
                ),
                wrap="wrap",
                spacing="2",
                width="100%",
            ),

            rx.cond(
                parcela[11] == "1",
                rx.box(
                    rx.text(
                        "Valores fuera de rango:",
                        size="1",
                        weight="bold",
                        color="var(--red-11)",
                        margin_bottom="0.25em",
                    ),
                    rx.text(
                        parcela[12],
                        size="1",
                        color="var(--red-11)",
                        white_space="pre-line",
                        line_height="1.35",
                    ),
                    width="100%",
                    padding="0.65em 0.75em",
                    border_radius="10px",
                    background_color="var(--red-3)",
                    border="1px solid var(--red-7)",
                ),
            ),

            rx.hstack(
                rx.text("En mantenimiento", size="2", color="var(--gray-11)"),
                rx.switch(
                    checked=parcela[5] == "1",
                    on_change=lambda val: GestorParcelasState.cambiar_mantenimiento(parcela[0], val),
                    color_scheme="amber",
                    size="1",
                    cursor="pointer",
                ),
                justify="between",
                align="center",
                width="100%",
                padding_top="0.35em",
                border_top="1px solid var(--gray-4)",
            ),

            rx.button(
                rx.icon("sliders-horizontal", size=14),
                "Configurar Rangos y Ficha",
                on_click=lambda: GestorParcelasState.abrir_ficha_parcela(parcela),
                variant="soft",
                color_scheme="gray",
                size="2",
                width="100%",
                cursor="pointer",
            ),

            spacing="3",
            justify="between",
            height="100%",
            width="100%",
        ),
        width="100%",
        padding="1.2em",
        border=rx.cond(
            parcela[11] == "1",
            "2px solid var(--red-9)",
            rx.cond(
                parcela[5] == "1",
                "1px solid var(--amber-8)",
                "1px solid var(--gray-5)",
            ),
        ),
        background_color="var(--gray-2)",
        box_shadow="0 4px 14px rgba(0, 0, 0, 0.04)",
        border_radius="16px",
    )


def panel_gestor_parcelas() -> rx.Component:
    return rx.box(
        rx.html("""
            <style>
                :root, .light, .light-theme {
                    color-scheme: light;
                    --gray-1: #F4F7F8 !important;
                    --gray-2: #FFFFFF !important;
                    --gray-3: #F1F5F7 !important;
                    --gray-4: #E2E9EC !important;
                    --gray-5: #D0DCE2 !important;
                    --gray-11: #4A636E !important;
                    --gray-12: #1A2E35 !important;
                }
                .dark, .dark-theme, [data-theme="dark"] {
                    color-scheme: dark;
                    --gray-1: #0D2F3A !important;
                    --gray-2: #09242E !important;
                    --gray-3: #123C4A !important;
                    --gray-4: #174859 !important;
                    --gray-5: #1D566B !important;
                    --gray-11: #B8D4DF !important;
                    --gray-12: #F0F8FA !important;
                }
            </style>
        """),

        rx.hstack(
            rx.hstack(
                rx.icon(tag="leaf", color="var(--grass-9)", size=28),
                rx.heading("Catálogo Agrotech", size="5", color="var(--grass-11)", weight="bold"),
                align_items="center",
                spacing="3",
            ),
            rx.hstack(
                rx.color_mode.button(),
                rx.button(
                    rx.icon(tag="log-out", size=16),
                    "Volver al Panel",
                    on_click=rx.redirect("/panel"),
                    color_scheme="gray",
                    variant="ghost",
                    size="2",
                    cursor="pointer",
                ),
                rx.hstack(
                    rx.box(
                        width="8px",
                        height="8px",
                        border_radius="50%",
                        background_color="var(--grass-9)",
                    ),
                    rx.text(BaseState.usuario_actual, weight="bold", size="2", color="var(--gray-12)"),
                    rx.avatar(
                        fallback=BaseState.usuario_actual[:1].upper(),
                        size="1",
                        color_scheme="grass",
                        variant="soft",
                    ),
                    padding="0.35em 0.75em",
                    border_radius="12px",
                    background_color="var(--gray-3)",
                    border="1px solid var(--gray-5)",
                    align_items="center",
                    spacing="2",
                ),
                spacing="3",
                align_items="center",
            ),
            justify_content="space-between",
            align_items="center",
            wrap="wrap",
            spacing="3",
            width="100%",
            min_width="0",
            padding=["0.8em 1em", "0.8em 2em"],
            border_bottom="1px solid var(--gray-5)",
            background_color="var(--gray-2)",
        ),

        rx.vstack(
            rx.vstack(
                rx.heading("Gestión de Parcelas", size="7", weight="bold", color="var(--gray-12)"),
                rx.text(
                    "Administra parcelas, define los rangos válidos por sensor y supervisa alertas críticas",
                    color="var(--gray-11)",
                    size="3",
                ),
                align_items="start",
                spacing="1",
                width="100%",
            ),

            rx.cond(
                GestorParcelasState.error_mensaje != "",
                rx.callout.root(
                    rx.callout.icon("triangle-alert"),
                    rx.callout.text(GestorParcelasState.error_mensaje),
                    color_scheme="red",
                    width="100%",
                ),
            ),
            rx.cond(
                GestorParcelasState.exito_mensaje != "",
                rx.callout.root(
                    rx.callout.icon("circle-check"),
                    rx.callout.text(GestorParcelasState.exito_mensaje),
                    color_scheme="grass",
                    width="100%",
                ),
            ),

            rx.card(
                rx.vstack(
                    rx.heading("Añadir Nueva Parcela", size="4", weight="bold", color="var(--gray-12)"),

                    rx.grid(
                        rx.vstack(
                            rx.text("Nombre de la parcela", size="2", weight="medium", color="var(--gray-11)"),
                            rx.input(
                                placeholder="Ej. Parcela Norte",
                                value=GestorParcelasState.nueva_nombre,
                                on_change=GestorParcelasState.set_nueva_nombre,
                                size="3",
                                variant="surface",
                                width="100%",
                            ),
                            align="start",
                            spacing="2",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text("Ubicación / Sector", size="2", weight="medium", color="var(--gray-11)"),
                            rx.input(
                                placeholder="Ej. Sector N",
                                value=GestorParcelasState.nueva_ubicacion,
                                on_change=GestorParcelasState.set_nueva_ubicacion,
                                size="3",
                                variant="surface",
                                width="100%",
                            ),
                            align="start",
                            spacing="2",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text("Cultivo", size="2", weight="medium", color="var(--gray-11)"),
                            rx.input(
                                placeholder="Ej. Pepino",
                                value=GestorParcelasState.nuevo_cultivo,
                                on_change=GestorParcelasState.set_nuevo_cultivo,
                                size="3",
                                variant="surface",
                                width="100%",
                            ),
                            align="start",
                            spacing="2",
                            width="100%",
                        ),
                        columns=rx.breakpoints(initial="1", sm="3"),
                        spacing="4",
                        width="100%",
                    ),

                    rx.text(
                        "Rangos permitidos por sensor (Mínimo y Máximo)",
                        size="2",
                        weight="bold",
                        color="var(--gray-11)",
                        padding_top="0.25em",
                    ),

                    rx.grid(
                        bloque_rango_sensor(
                            "Tª Ambiente (ºC)",
                            GestorParcelasState.nueva_temp_amb_min,
                            GestorParcelasState.set_nueva_temp_amb_min,
                            GestorParcelasState.nueva_temp_amb_max,
                            GestorParcelasState.set_nueva_temp_amb_max,
                        ),
                        bloque_rango_sensor(
                            "Tª Suelo (ºC)",
                            GestorParcelasState.nueva_temp_suelo_min,
                            GestorParcelasState.set_nueva_temp_suelo_min,
                            GestorParcelasState.nueva_temp_suelo_max,
                            GestorParcelasState.set_nueva_temp_suelo_max,
                        ),
                        bloque_rango_sensor(
                            "pH Suelo (pH)",
                            GestorParcelasState.nueva_ph_min,
                            GestorParcelasState.set_nueva_ph_min,
                            GestorParcelasState.nueva_ph_max,
                            GestorParcelasState.set_nueva_ph_max,
                        ),
                        bloque_rango_sensor(
                            "Luminosidad (lux)",
                            GestorParcelasState.nueva_lux_min,
                            GestorParcelasState.set_nueva_lux_min,
                            GestorParcelasState.nueva_lux_max,
                            GestorParcelasState.set_nueva_lux_max,
                        ),
                        bloque_rango_sensor(
                            "Humedad (%)",
                            GestorParcelasState.nueva_humedad_min,
                            GestorParcelasState.set_nueva_humedad_min,
                            GestorParcelasState.nueva_humedad_max,
                            GestorParcelasState.set_nueva_humedad_max,
                        ),
                        columns=rx.breakpoints(initial="1", sm="2", md="3", lg="5"),
                        spacing="4",
                        width="100%",
                    ),

                    rx.hstack(
                        rx.spacer(),
                        rx.button(
                            rx.icon("plus", size=18),
                            "Añadir Parcela",
                            on_click=GestorParcelasState.anadir_parcela,
                            color_scheme="grass",
                            size="3",
                            cursor="pointer",
                        ),
                        width="100%",
                        padding_top="0.25em",
                    ),

                    spacing="4",
                    width="100%",
                ),
                width="100%",
                padding="1.6em",
                border="1px solid var(--gray-5)",
                background_color="var(--gray-2)",
                box_shadow="0 4px 12px rgba(0, 0, 0, 0.03)",
                border_radius="16px",
            ),

            rx.hstack(
                rx.hstack(
                    rx.heading("Mis Parcelas", size="5", weight="bold", color="var(--gray-12)"),
                    rx.badge(
                        GestorParcelasState.total_parcelas,
                        " registradas",
                        color_scheme="grass",
                        variant="soft",
                        size="2",
                    ),
                    rx.badge(
                        rx.icon("radio", size=12),
                        "Tiempo real",
                        color_scheme="grass",
                        variant="outline",
                        size="2",
                    ),
                    rx.cond(
                        GestorParcelasState.total_criticas > 0,
                        rx.badge(
                            GestorParcelasState.total_criticas,
                            " en estado crítico",
                            color_scheme="red",
                            variant="solid",
                            size="2",
                        ),
                    ),
                    align="center",
                    spacing="3",
                    wrap="wrap",
                ),
                rx.hstack(
                    rx.input(
                        placeholder="Buscar parcela, sector o cultivo...",
                        value=GestorParcelasState.filtro_busqueda,
                        on_change=GestorParcelasState.set_filtro_busqueda,
                        size="2",
                        variant="surface",
                        width=["100%", "240px"],
                    ),
                    rx.select(
                        ["Todas", "Críticas", "Operativas", "En mantenimiento"],
                        value=GestorParcelasState.filtro_estado,
                        on_change=GestorParcelasState.set_filtro_estado,
                        size="2",
                        variant="soft",
                    ),
                    spacing="3",
                    wrap="wrap",
                    align="center",
                ),
                justify="between",
                align="center",
                wrap="wrap",
                spacing="3",
                width="100%",
                padding_top="0.5em",
            ),

            rx.grid(
                rx.foreach(GestorParcelasState.parcelas_filtradas, tarjeta_parcela),
                columns=rx.breakpoints(initial="1", sm="2", md="3", lg="4"),
                spacing="4",
                width="100%",
                min_width="0",
            ),

            rx.dialog.root(
                rx.dialog.content(
                    rx.dialog.title(
                        "Configurar Rangos y Ficha: Parcela #",
                        GestorParcelasState.edit_id,
                    ),
                    rx.dialog.description(
                        "Modifica los límites permitidos de cada sensor, el estado de mantenimiento o las notas.",
                        size="2",
                        margin_bottom="1em",
                    ),
                    rx.vstack(
                        rx.grid(
                            rx.vstack(
                                rx.text("Nombre", size="2", weight="bold"),
                                rx.input(
                                    value=GestorParcelasState.edit_nombre,
                                    on_change=GestorParcelasState.set_edit_nombre,
                                    width="100%",
                                ),
                                spacing="2",
                                align="start",
                            ),
                            rx.vstack(
                                rx.text("Ubicación / Sector", size="2", weight="bold"),
                                rx.input(
                                    value=GestorParcelasState.edit_ubicacion,
                                    on_change=GestorParcelasState.set_edit_ubicacion,
                                    width="100%",
                                ),
                                spacing="2",
                                align="start",
                            ),
                            rx.vstack(
                                rx.text("Cultivo", size="2", weight="bold"),
                                rx.input(
                                    value=GestorParcelasState.edit_cultivo,
                                    on_change=GestorParcelasState.set_edit_cultivo,
                                    width="100%",
                                ),
                                spacing="2",
                                align="start",
                            ),
                            rx.vstack(
                                rx.text("Superficie", size="2", weight="bold"),
                                rx.input(
                                    placeholder="Ej. 2.4 ha",
                                    value=GestorParcelasState.edit_superficie,
                                    on_change=GestorParcelasState.set_edit_superficie,
                                    width="100%",
                                ),
                                spacing="2",
                                align="start",
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),

                        rx.hstack(
                            rx.vstack(
                                rx.text("Modo mantenimiento", size="2", weight="bold"),
                                rx.text(
                                    "Actívalo si se están realizando tareas técnicas en la parcela",
                                    size="1",
                                    color="var(--gray-11)",
                                ),
                                spacing="1",
                                align="start",
                            ),
                            rx.spacer(),
                            rx.switch(
                                checked=GestorParcelasState.edit_en_mantenimiento,
                                on_change=GestorParcelasState.set_edit_en_mantenimiento,
                                color_scheme="amber",
                                cursor="pointer",
                            ),
                            width="100%",
                            padding="0.75em",
                            border_radius="10px",
                            background_color="var(--gray-3)",
                            align="center",
                        ),

                        rx.text("Límites permitidos por sensor (Mínimo y Máximo)", size="2", weight="bold"),

                        rx.grid(
                            bloque_rango_sensor(
                                "Tª Ambiente (ºC)",
                                GestorParcelasState.edit_temp_amb_min,
                                GestorParcelasState.set_edit_temp_amb_min,
                                GestorParcelasState.edit_temp_amb_max,
                                GestorParcelasState.set_edit_temp_amb_max,
                            ),
                            bloque_rango_sensor(
                                "Tª Suelo (ºC)",
                                GestorParcelasState.edit_temp_suelo_min,
                                GestorParcelasState.set_edit_temp_suelo_min,
                                GestorParcelasState.edit_temp_suelo_max,
                                GestorParcelasState.set_edit_temp_suelo_max,
                            ),
                            bloque_rango_sensor(
                                "pH Suelo (pH)",
                                GestorParcelasState.edit_ph_min,
                                GestorParcelasState.set_edit_ph_min,
                                GestorParcelasState.edit_ph_max,
                                GestorParcelasState.set_edit_ph_max,
                            ),
                            bloque_rango_sensor(
                                "Luminosidad (lux)",
                                GestorParcelasState.edit_lux_min,
                                GestorParcelasState.set_edit_lux_min,
                                GestorParcelasState.edit_lux_max,
                                GestorParcelasState.set_edit_lux_max,
                            ),
                            bloque_rango_sensor(
                                "Humedad (%)",
                                GestorParcelasState.edit_humedad_min,
                                GestorParcelasState.set_edit_humedad_min,
                                GestorParcelasState.edit_humedad_max,
                                GestorParcelasState.set_edit_humedad_max,
                            ),
                            columns="2",
                            spacing="3",
                            width="100%",
                        ),

                        rx.vstack(
                            rx.text("Cuaderno de campo / Observaciones", size="2", weight="bold"),
                            rx.text_area(
                                placeholder="Anota tratamientos, riegos o incidencias...",
                                value=GestorParcelasState.edit_notas,
                                on_change=GestorParcelasState.set_edit_notas,
                                width="100%",
                                min_height="75px",
                            ),
                            width="100%",
                            spacing="2",
                            align="start",
                        ),

                        rx.hstack(
                            rx.button(
                                rx.icon("trash-2", size=15),
                                "Eliminar",
                                on_click=GestorParcelasState.eliminar_parcela_actual,
                                color_scheme="red",
                                variant="soft",
                                cursor="pointer",
                            ),
                            rx.spacer(),
                            rx.dialog.close(
                                rx.button("Cancelar", variant="soft", color_scheme="gray", cursor="pointer")
                            ),
                            rx.button(
                                "Guardar Cambios",
                                on_click=GestorParcelasState.guardar_ficha_parcela,
                                color_scheme="grass",
                                cursor="pointer",
                            ),
                            width="100%",
                            padding_top="0.5em",
                            align="center",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    max_width="620px",
                ),
                open=GestorParcelasState.modal_abierto,
                on_open_change=GestorParcelasState.set_modal_abierto,
            ),

            width="100%",
            max_width="1350px",
            min_width="0",
            margin="0 auto",
            padding=["1.5em 1em", "2em 1.5em"],
            spacing="5",
        ),
        width="100%",
        min_height="100vh",
        overflow_x="clip",
        background_color="var(--gray-1)",
    )