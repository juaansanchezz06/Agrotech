import sqlite3

from .config import DEFINICION_SENSORES, PARCELAS_INICIALES, RUTA_DB
from .security import generar_hash_password


def conectar_db(timeout: float = 15.0) -> sqlite3.Connection:
    return sqlite3.connect(RUTA_DB, timeout=timeout)


def columna_id_sensors(cursor: sqlite3.Cursor) -> str:
    cursor.execute("PRAGMA table_info(sensors)")
    columnas = {fila[1] for fila in cursor.fetchall()}
    return "sensor_id" if "sensor_id" in columnas and "id" not in columnas else "id"


def _migrar_columnas(cursor: sqlite3.Cursor) -> None:
    # Migración users
    cursor.execute("PRAGMA table_info(users)")
    cols_users = {fila[1] for fila in cursor.fetchall()}
    if "password_hash" not in cols_users:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
        if "password" in cols_users:
            cursor.execute("UPDATE users SET password_hash = password WHERE password_hash = ''")

    # Migración parcels (evita errores si la BD es antigua)
    columnas_parcels = {
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
    cursor.execute("PRAGMA table_info(parcels)")
    existentes_parcels = {fila[1] for fila in cursor.fetchall()}
    for col, definicion in columnas_parcels.items():
        if col not in existentes_parcels:
            cursor.execute(f"ALTER TABLE parcels ADD COLUMN {col} {definicion}")

    # Migración alerts
    columnas_alerts = {
        "parcel_id": "INTEGER",
        "sensor_id": "TEXT DEFAULT ''",
        "message": "TEXT DEFAULT ''",
        "value": "REAL DEFAULT 0.0",
        "timestamp": "TEXT DEFAULT ''",
        "acknowledged": "INTEGER DEFAULT 0",
    }
    cursor.execute("PRAGMA table_info(alerts)")
    existentes_alerts = {fila[1] for fila in cursor.fetchall()}
    for col, definicion in columnas_alerts.items():
        if col not in existentes_alerts:
            cursor.execute(f"ALTER TABLE alerts ADD COLUMN {col} {definicion}")


def _sembrar_datos_basicos(cursor: sqlite3.Cursor) -> None:
    cursor.execute("PRAGMA table_info(users)")
    cols_users = {fila[1] for fila in cursor.fetchall()}

    cursor.execute("SELECT 1 FROM users WHERE username = 'admin'")
    if cursor.fetchone() is None:
        hash_admin = generar_hash_password("admin123")
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

        col_id = columna_id_sensors(cursor)
        cursor.execute("SELECT id FROM parcels ORDER BY id ASC")
        for (pid,) in cursor.fetchall():
            for sufijo, tipo, unidad, _, _ in DEFINICION_SENSORES:
                cursor.execute(
                    f"INSERT OR IGNORE INTO sensors ({col_id}, parcel_id, type, unit) VALUES (?, ?, ?, ?)",
                    (f"p{pid}_{sufijo}", int(pid), tipo, unidad),
                )


def init_db() -> None:
    conexion = sqlite3.connect(RUTA_DB, timeout=15.0, isolation_level=None)
    try:
        cursor = conexion.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
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

        _migrar_columnas(cursor)
        _sembrar_datos_basicos(cursor)
        cursor.execute("COMMIT")
    except Exception:
        if conexion.in_transaction:
            conexion.execute("ROLLBACK")
        raise
    finally:
        conexion.close()