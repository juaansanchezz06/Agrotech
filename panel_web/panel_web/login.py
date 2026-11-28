import sqlite3

import reflex as rx

try:
    from ui_shared import ESTILOS_TEMA_GLOBAL
except ImportError:
    from .ui_shared import ESTILOS_TEMA_GLOBAL

from funcs import conectar_db, generar_hash_password, init_db, verificar_password

try:
    init_db()
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
            init_db()
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (usuario,))
                fila = cursor.fetchone()

                if fila is None:
                    self.error_mensaje = "Usuario o contraseña incorrectos."
                    return

                user_id, password_hash = fila
                valida, migrar = verificar_password(clave, str(password_hash or ""))
                if not valida:
                    self.error_mensaje = "Usuario o contraseña incorrectos."
                    return

                if migrar:
                    cursor.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (generar_hash_password(clave), user_id),
                    )
                    conexion.commit()

            self.usuario_actual = usuario
            self.password_input = ""
            return rx.redirect("/panel")
        except sqlite3.Error as e:
            self.error_mensaje = f"Error de base de datos: {e}"


def login_page() -> rx.Component:
    return rx.box(
        rx.html(ESTILOS_TEMA_GLOBAL),
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