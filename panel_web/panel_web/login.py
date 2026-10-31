import reflex as rx
import sqlite3
import os
import hashlib

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")

# 1. ESTADO GLOBAL
class BaseState(rx.State):
    usuario_actual: str = rx.LocalStorage("")

    def cerrar_sesion(self):
        self.usuario_actual = ""
        return rx.redirect("/")

# 2. ESTADO DEL LOGIN Y REGISTRO
class LoginState(BaseState):
    usuario: str = ""
    contrasena: str = ""
    error_mensaje: str = ""
    exito_mensaje: str = ""
    modo_registro: bool = False
    
    # Control de visibilidad de la contraseña
    mostrar_contrasena: bool = False

    def toggle_contrasena(self):
        self.mostrar_contrasena = not self.mostrar_contrasena

    def cambiar_modo(self):
        self.modo_registro = not self.modo_registro
        self.error_mensaje = ""
        self.exito_mensaje = ""
        # Vaciamos los campos de texto al cambiar de pantalla
        self.usuario = ""
        self.contrasena = ""

    def set_usuario(self, valor: str):
        self.usuario = valor

    def set_contrasena(self, valor: str):
        self.contrasena = valor

    def validar_login(self):
        self.error_mensaje = ""
        self.exito_mensaje = ""

        if not self.usuario or not self.contrasena:
            self.error_mensaje = "Por favor, rellena todos los campos."
            return

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT
                    )
                """)

                cursor.execute("SELECT id FROM users WHERE username = 'admin'")
                if not cursor.fetchone():
                    admin_hash = hashlib.sha256("admin123".encode('utf-8')).hexdigest()
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                        ('admin', admin_hash, 'administrador')
                    )
                conexion.commit()

                pass_hash = hashlib.sha256(self.contrasena.encode('utf-8')).hexdigest()

                cursor.execute(
                    "SELECT id FROM users WHERE username = ? AND password_hash = ?",
                    (self.usuario, pass_hash)
                )

                if cursor.fetchone():
                    self.usuario_actual = self.usuario
                    self.usuario = ""
                    self.contrasena = ""
                    return rx.redirect("/panel")
                else:
                    self.error_mensaje = "Usuario o contraseña incorrectos."

        except sqlite3.Error as e:
            self.error_mensaje = f"Error de base de datos: {e}"

    def registrar_usuario(self):
        self.error_mensaje = ""
        self.exito_mensaje = ""

        if not self.usuario or not self.contrasena:
            self.error_mensaje = "Por favor, rellena todos los campos para registrarte."
            return

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()

                cursor.execute("SELECT id FROM users WHERE username = ?", (self.usuario,))
                if cursor.fetchone():
                    self.error_mensaje = "Ese nombre de usuario ya está en uso."
                    return

                pass_hash = hashlib.sha256(self.contrasena.encode('utf-8')).hexdigest()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (self.usuario, pass_hash, 'usuario')
                )
                conexion.commit()

                self.exito_mensaje = "¡Cuenta creada con éxito! Ya puedes iniciar sesión."
                self.modo_registro = False
                self.contrasena = ""

        except sqlite3.Error as e:
            self.error_mensaje = f"Error al crear usuario: {e}"

# 3. INTERFAZ
def login_page() -> rx.Component:
    return rx.box(
        rx.center(
            rx.card(
                rx.vstack(
                    rx.center(
                        rx.cond(
                            LoginState.modo_registro,
                            rx.icon(tag="user-plus", size=40, color="var(--grass-9)"),
                            rx.icon(tag="lock", size=40, color="var(--grass-9)")
                        ),
                        rx.cond(
                            LoginState.modo_registro,
                            rx.heading("Nuevo Usuario", size="6", margin_top="1em"),
                            rx.heading("Acceso Agrotech", size="6", margin_top="1em")
                        ),
                        margin_bottom="1em",
                        width="100%"
                    ),
                    rx.text("Usuario", weight="bold", size="2"),
                    rx.input(value=LoginState.usuario, placeholder="Introduce tu usuario...", on_change=LoginState.set_usuario, width="100%"),

                    rx.text("Contraseña", weight="bold", size="2", margin_top="1em"),
                    rx.hstack(
                        rx.input(
                            value=LoginState.contrasena,
                            type=rx.cond(LoginState.mostrar_contrasena, "text", "password"),
                            placeholder="••••••••",
                            on_change=LoginState.set_contrasena,
                            width="100%"
                        ),
                        rx.icon_button(
                            rx.icon(tag=rx.cond(LoginState.mostrar_contrasena, "eye-off", "eye")),
                            on_click=LoginState.toggle_contrasena,
                            variant="ghost",
                            color_scheme="gray"
                        ),
                        width="100%"
                    ),

                    rx.cond(
                        LoginState.error_mensaje != "",
                        rx.callout.root(
                            rx.callout.icon("alert-triangle"),
                            rx.callout.text(LoginState.error_mensaje),
                            color_scheme="red", role="alert", margin_top="1em", width="100%"
                        )
                    ),

                    rx.cond(
                        LoginState.exito_mensaje != "",
                        rx.callout.root(
                            rx.callout.icon("check-circle"),
                            rx.callout.text(LoginState.exito_mensaje),
                            color_scheme="grass", role="alert", margin_top="1em", width="100%"
                        )
                    ),

                    rx.cond(
                        LoginState.modo_registro,
                        rx.button("Crear Cuenta", on_click=LoginState.registrar_usuario, color_scheme="grass", width="100%", margin_top="2em", size="3"),
                        rx.button("Entrar", on_click=LoginState.validar_login, color_scheme="grass", width="100%", margin_top="2em", size="3")
                    ),

                    rx.center(
                        rx.button(
                            rx.cond(
                                LoginState.modo_registro,
                                "¿Ya tienes cuenta? Inicia sesión",
                                "¿No tienes cuenta? Regístrate"
                            ),
                            on_click=LoginState.cambiar_modo,
                            variant="ghost",
                            color_scheme="gray",
                            size="2"
                        ),
                        width="100%",
                        margin_top="1em"
                    ),

                    width="100%", align_items="start", padding="2em"
                ),
                width=["90%", "400px"], box_shadow="lg"
            ),
            width="100%", height="100vh", background_color="var(--gray-2)"
        )
    )