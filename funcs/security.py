import hashlib
import secrets

ITERACIONES_PBKDF2 = 600000


def generar_hash_password(password_plana: str = "admin123") -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password_plana.encode("utf-8"), salt.encode("utf-8"), ITERACIONES_PBKDF2)
    return f"pbkdf2_sha256${ITERACIONES_PBKDF2}${salt}${dk.hex()}"


def verificar_password(password: str, almacenada: str) -> tuple[bool, bool]:
    if not almacenada:
        return False, False

    if almacenada.startswith("pbkdf2_sha256$"):
        partes = almacenada.split("$")
        if len(partes) != 4:
            return False, False
        _, iter_str, salt, hash_hex = partes
        try:
            iteraciones = int(iter_str)
        except ValueError:
            return False, False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iteraciones)
        return secrets.compare_digest(dk.hex(), hash_hex), iteraciones < ITERACIONES_PBKDF2

    if len(almacenada) == 64:
        sha_hex = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if secrets.compare_digest(sha_hex, almacenada):
            return True, True

    if secrets.compare_digest(password, almacenada):
        return True, True

    return False, False