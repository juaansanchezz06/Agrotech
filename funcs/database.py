import sqlite3
from pathlib import Path
from funcs.usuarios import hashear_contrasena

# Ruta absoluta garantizada a Agrotech/agrotech.db
DB_PATH = Path(__file__).resolve().parent.parent / "agrotech.db"


def obtener_conexion() -> sqlite3.Connection:
    """Devuelve una conexión lista a la base de datos SQLite."""
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Crea las tablas iniciales y el usuario administrador si no existen."""
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                role TEXT
            );
            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                location TEXT
            );
            CREATE TABLE IF NOT EXISTS sensors (
                id TEXT PRIMARY KEY,
                parcel_id INTEGER,
                type TEXT,
                unit TEXT,
                description TEXT,
                threshold_low REAL,
                threshold_high REAL,
                FOREIGN KEY(parcel_id) REFERENCES parcels(id)
            );
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT,
                timestamp TEXT,
                value REAL,
                raw TEXT,
                FOREIGN KEY(sensor_id) REFERENCES sensors(id)
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT,
                timestamp TEXT,
                type TEXT,
                message TEXT,
                acknowledged BOOLEAN,
                FOREIGN KEY(sensor_id) REFERENCES sensors(id)
            );
        """)

        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            admin_hash = hashear_contrasena("admin123")
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", admin_hash, "administrador"),
            )
        conexion.commit()