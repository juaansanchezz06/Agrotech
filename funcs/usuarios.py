import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "agrotech.db"


def hashear_contrasena(password: str) -> str:
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
    return f"{salt.hex()}${pwd_hash.hex()}"


def verificar_contrasena(password: str, hash_almacenado: str) -> bool:
    try:
        salt_hex, pwd_hash_hex = hash_almacenado.split("$")
        salt = bytes.fromhex(salt_hex)
        pwd_hash = bytes.fromhex(pwd_hash_hex)
        new_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
        return secrets.compare_digest(new_hash, pwd_hash)
    except (ValueError, AttributeError):
        return False


def autenticar_usuario(username: str, password: str) -> str | None:
    """Verifica credenciales y devuelve el rol del usuario si son válidas, o None si fallan."""
    with sqlite3.connect(DB_PATH) as conexion:
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT role, password_hash FROM users WHERE username = ?",
            (username,),
        )
        usuario = cursor.fetchone()

    if usuario and verificar_contrasena(password, usuario[1]):
        return usuario[0]
    return None

def obtener_rol_usuario(username: str) -> str:
    """Devuelve el rol de un usuario por su nombre, o 'usuario' por defecto."""
    if not username:
        return "usuario"
    with sqlite3.connect(DB_PATH) as conexion:
        cursor = conexion.cursor()
        cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
        resultado = cursor.fetchone()
    return resultado[0] if resultado else "usuario"

