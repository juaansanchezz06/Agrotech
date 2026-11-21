import hashlib
import os
import secrets
import sqlite3

import reflex as rx

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_RAIZ = os.path.abspath(os.path.join(DIR_ACTUAL, "..", ".."))
RUTA_DB = os.path.join(RUTA_RAIZ, "agrotech.db")

ITERACIONES_PBKDF2 = 600000

PARCELAS_INICIALES = [
    ("Parcela Norte", "Sector A", "Maíz", "2.4 ha", 0, "", 15.0, 32.0, 12.0, 28.0, 5.5, 7.5, 200.0, 50000.0, 40.0, 85.0),
    ("Parcela Sur", "Sector B", "Trigo", "3.1 ha", 0, "", 12.0, 30.0, 10.0, 26.0, 6.0, 7.5, 200.0, 50000.0, 35.0, 80.0),
    ("Invernadero Principal", "Sector C", "Tomate", "0.8 ha", 0, "", 18.0, 30.0, 15.0, 26.0, 5.8, 6.8, 300.0, 45000.0, 55.0, 85.0),
    ("Viñedo Este", "Sector D", "Vid", "4.0 ha", 0, "", 14.0, 34.0, 12.0, 28.0, 5.5, 7.5, 300.0, 60000.0, 35.0, 75.0),
    ("Huerto Central", "Sector E", "Hortalizas", "1.2 ha", 0, "", 15.0, 29.0, 13.0, 25.0, 6.0, 7.2, 200.0, 45000.0, 50.0, 85.0),
]

DEFINICION_SENSORES = (
    ("temp_amb", "temperaturaAmb", "ºC"),
    ("temp_suelo", "temperaturaSuelo", "ºC"),
    ("ph", "ph", "pH"),
    ("lux", "luminosidad", "lux"),
    ("humedad", "humedadSuelo", "%"),
)

ESTILOS_LOGIN = """
<style>
    :root, .light, .light-theme {
        color-scheme: light;
        --gray-1: #F4F7F8 !important;
        --gray-2: #EBF0F2 !important;
        --gray-3: #E1E8EC !important;
        --gray-4: #D3DEE3 !important;
        --gray-5: #C5D4DC !important;
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
        --gray-6: #2A718B !important;
        --gray-11: #B8D4DF !important;
        --gray-12: #F0F8FA !important;
    }
    .dark .rt-TextFieldInput,
    .dark-theme .rt-TextFieldInput,
    [data-theme="dark"] .rt-TextFieldInput {
        color: #FFFFFF !important;
    }
    .dark .rt-TextFieldInput::placeholder,
    .dark-theme .rt-TextFieldInput::placeholder,
    [data-theme="dark"] .rt-TextFieldInput::placeholder {
        color: #B8D4DF !important;
        opacity: 0.85 !important;
    }
    .light .rt-TextFieldInput,
    .light-theme .rt-TextFieldInput {
        color: #1A2E35 !important;
    }
    .light .rt-TextFieldInput::placeholder,
    .light-theme .rt-TextFieldInput::placeholder {
        color: #4A636E !important;
        opacity: 0.85 !important;
    }
</style>
"""


def hashear_contrasena(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERACIONES_PBKDF2)
    return f"pbkdf2_sha256${ITERACIONES_PBKDF2}${salt}${dk.hex()}"


def verificar_contrasena(password: str, almacenada: str) -> tuple[bool, bool]:
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


def asegurar_bd_agrotech() -> None:
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
            hash_admin = hashear_contrasena("admin123")
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
            cols_s = {fila[1] for fila in cursor.fetchall()}
            col_id = "sensor_id" if "sensor_id" in cols_s and "id" not in cols_s else "id"

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


try:
    asegurar_bd_agrotech()
except sqlite3.Error as _err:
    print(f"Error inicializando agrotech.db desde login.py: {_err}")


class BaseState(rx.State):
    usuario_actual: str = rx.LocalStorage("")

    def cerrar_sesion(self):
        self.usuario_actual = ""
        return rx.redirect("/")


class LoginState(BaseState):
    username_input: str = ""
    password_input: str = ""
    error_mensaje: str = ""
    mostrar_password: bool = False

    def set_username_input(self, valor: str):
        self.username_input = valor

    def set_password_input(self, valor: str):
        self.password_input = valor

    def alternar_visibilidad_password(self):
        self.mostrar_password = not self.mostrar_password

    def manejar_tecla(self, tecla: str):
        if tecla == "Enter":
            return self.iniciar_sesion()

    def iniciar_sesion(self):
        self.error_mensaje = ""
        usuario = self.username_input.strip()
        clave = self.password_input

        if not usuario or not clave:
            self.error_mensaje = "Introduce usuario y contraseña."
            return

        try:
            asegurar_bd_agrotech()
            with sqlite3.connect(RUTA_DB, timeout=15.0) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (usuario,))
                fila = cursor.fetchone()

                if fila is None:
                    self.error_mensaje = "Usuario o contraseña incorrectos."
                    return

                user_id, password_hash = fila
                valida, migrar = verificar_contrasena(clave, str(password_hash or ""))
                if not valida:
                    self.error_mensaje = "Usuario o contraseña incorrectos."
                    return

                if migrar:
                    cursor.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (hashear_contrasena(clave), user_id),
                    )
                    conexion.commit()

            self.usuario_actual = usuario
            self.password_input = ""
            return rx.redirect("/panel")
        except sqlite3.Error as e:
            self.error_mensaje = f"Error de base de datos: {e}"


def login_page() -> rx.Component:
    return rx.box(
        rx.html(ESTILOS_LOGIN),
        rx.box(
            rx.color_mode.button(),
            position="absolute",
            top="1.5em",
            right="1.5em",
            z_index="10",
        ),
        rx.center(
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="lock", color="var(--grass-9)", size=34),
                        rx.heading(
                            "Acceso Agrotech",
                            size="6",
                            weight="bold",
                            color="var(--gray-12)",
                        ),
                        align="center",
                        justify="center",
                        spacing="2",
                        width="100%",
                        margin_bottom="0.8em",
                    ),
                    rx.vstack(
                        rx.text("Usuario", size="2", weight="bold", color="var(--gray-12)"),
                        rx.input(
                            rx.input.slot(rx.icon("user", size=16)),
                            placeholder="Introduce tu usuario",
                            value=LoginState.username_input,
                            on_change=LoginState.set_username_input,
                            on_key_down=LoginState.manejar_tecla,
                            variant="surface",
                            size="3",
                            width="100%",
                        ),
                        align="start",
                        width="100%",
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Contraseña", size="2", weight="bold", color="var(--gray-12)"),
                        rx.input(
                            rx.input.slot(rx.icon("lock", size=16)),
                            rx.input.slot(
                                rx.icon_button(
                                    rx.cond(
                                        LoginState.mostrar_password,
                                        rx.icon("eye-off", size=16),
                                        rx.icon("eye", size=16),
                                    ),
                                    on_click=LoginState.alternar_visibilidad_password,
                                    variant="ghost",
                                    size="1",
                                    type="button",
                                ),
                                side="right",
                            ),
                            type=rx.cond(LoginState.mostrar_password, "text", "password"),
                            placeholder="Introduce tu contraseña",
                            value=LoginState.password_input,
                            on_change=LoginState.set_password_input,
                            on_key_down=LoginState.manejar_tecla,
                            variant="surface",
                            size="3",
                            width="100%",
                        ),
                        align="start",
                        width="100%",
                        spacing="1",
                    ),
                    rx.cond(
                        LoginState.error_mensaje != "",
                        rx.callout(
                            LoginState.error_mensaje,
                            icon="triangle-alert",
                            color_scheme="red",
                            width="100%",
                        ),
                    ),
                    rx.button(
                        "Entrar",
                        on_click=LoginState.iniciar_sesion,
                        color_scheme="grass",
                        size="3",
                        width="100%",
                        cursor="pointer",
                        margin_top="0.5em",
                    ),
                    spacing="4",
                    width="100%",
                ),
                width="100%",
                max_width="400px",
                padding="2.2em",
                border="1px solid var(--gray-5)",
                border_radius="18px",
                background_color="var(--gray-2)",
                box_shadow="0 8px 30px rgba(0, 0, 0, 0.12)",
            ),
            width="100%",
            min_height="100vh",
            padding="1.5em",
        ),
        width="100%",
        min_height="100vh",
        position="relative",
        background_color="var(--gray-1)",
    )