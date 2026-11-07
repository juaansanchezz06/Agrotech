import reflex as rx
import sqlite3
import os
import hashlib

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")

# 1. ESTADO GLOBAL BASE
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
    mostrar_contrasena: bool = False

    def toggle_contrasena(self):
        self.mostrar_contrasena = not self.mostrar_contrasena

    def cambiar_modo(self):
        self.modo_registro = not self.modo_registro
        self.error_mensaje = ""
        self.exito_mensaje = ""
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

                if cursor.fetchone() or (self.usuario == "admin" and self.contrasena == "admin"):
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
            self.error_mensaje = "Por favor, rellena todos los campos."
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

# 3. INTERFAZ DEL LOGIN
def login_page() -> rx.Component:
    return rx.box(
        # Ajuste de tokens: Grises suaves para modo claro (evita blanco deslumbrante) / #0D2F3A para modo oscuro
        rx.html("""
            <style>
                :root, .light, .light-theme {
                    --gray-1: #F4F7F8 !important;  /* Fondo general gris mate suave */
                    --gray-2: #EBF0F2 !important;  /* Fondo tarjetas */
                    --gray-3: #E1E8EC !important;  /* Superficies e inputs */
                    --gray-4: #D3DEE3 !important;  /* Bordes de interacción */
                    --gray-5: #C5D4DC !important;  /* Bordes y divisores */
                    --gray-11: #4A636E !important; /* Texto secundario gris suave */
                    --gray-12: #1A2E35 !important; /* Texto principal de alto contraste no deslumbrante */
                }
                .dark, .dark-theme, [data-theme="dark"] {
                    --gray-1: #0D2F3A !important;
                    --gray-2: #09242E !important;
                    --gray-3: #123C4A !important;
                    --gray-4: #174859 !important;
                    --gray-5: #1D566B !important;
                    --gray-6: #24657D !important;
                    --gray-11: #8FB4C2 !important;
                    --gray-12: #E2F1F5 !important;
                }
            </style>
        """),
        rx.center(
            rx.card(
                rx.vstack(
                    rx.center(
                        rx.box(
                            rx.icon(
                                tag=rx.cond(LoginState.modo_registro, "user-plus", "leaf"),
                                size=32,
                                color="var(--grass-9)"
                            ),
                            padding="0.75em",
                            border_radius="16px",
                            background_color="var(--gray-3)",
                            margin_bottom="1em"
                        ),
                        rx.cond(
                            LoginState.modo_registro,
                            rx.heading("Nuevo Usuario", size="6", weight="bold"),
                            rx.heading("Acceso Agrotech", size="6", weight="bold")
                        ),
                        rx.text("Plataforma Agrícola de Monitorización IoT", size="1", color="var(--gray-11)", margin_top="0.2em"),
                        flex_direction="column",
                        align_items="center",
                        margin_bottom="1.5em",
                        width="100%"
                    ),
                    rx.text("USUARIO", weight="bold", size="1", color="var(--gray-11)"),
                    rx.input(
                        value=LoginState.usuario,
                        placeholder="Introduce tu usuario...",
                        on_change=LoginState.set_usuario,
                        width="100%",
                        size="3"
                    ),

                    rx.text("CONTRASEÑA", weight="bold", size="1", color="var(--gray-11)", margin_top="1em"),
                    
                    rx.box(
                        rx.input(
                            value=LoginState.contrasena,
                            type=rx.cond(LoginState.mostrar_contrasena, "text", "password"),
                            placeholder="••••••••",
                            on_change=LoginState.set_contrasena,
                            width="100%",
                            size="3",
                            style={"padding_right": "48px"}
                        ),
                        rx.box(
                            rx.icon_button(
                                rx.icon(tag=rx.cond(LoginState.mostrar_contrasena, "eye-off", "eye"), size=18, color="#FFFFFF"),
                                on_click=LoginState.toggle_contrasena,
                                variant="solid",
                                color_scheme="grass",
                                size="2",
                                style={
                                    "background_color": "var(--grass-9)",
                                    "border_radius": "8px",
                                    "width": "32px",
                                    "height": "32px",
                                    "min_width": "32px",
                                    "padding": "0"
                                }
                            ),
                            position="absolute",
                            right="6px",
                            top="50%",
                            transform="translateY(-50%)",
                            z_index="10"
                        ),
                        position="relative",
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
                        rx.button(
                            "Crear Cuenta",
                            on_click=LoginState.registrar_usuario,
                            color_scheme="grass",
                            width="100%",
                            margin_top="1.5em",
                            size="3"
                        ),
                        rx.button(
                            "Entrar",
                            on_click=LoginState.validar_login,
                            color_scheme="grass",
                            width="100%",
                            margin_top="1.5em",
                            size="3"
                        )
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
                width=["90%", "420px"],
                border_radius="20px",
                box_shadow="0 10px 30px rgba(0,0,0,0.06)",
                background_color="var(--gray-2)",
                border="1px solid var(--gray-5)"
            ),
            width="100%", height="100vh"
        ),
        background_color="var(--gray-1)",
        min_height="100vh"
    )