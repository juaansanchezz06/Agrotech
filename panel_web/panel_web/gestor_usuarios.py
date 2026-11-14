import reflex as rx
import sqlite3
import os

try:
    from login import BaseState, hashear_contrasena
except ImportError:
    from .login import BaseState, hashear_contrasena

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")


class GestorUsuariosState(BaseState):
    usuarios_registrados: list[list[str]] = []
    pagina_actual: int = 1

    input_usuario: str = ""
    input_contrasena: str = ""
    input_rol: str = "usuario"

    error_mensaje: str = ""
    exito_mensaje: str = ""

    @rx.var
    def total_paginas(self) -> int:
        return max(1, (len(self.usuarios_registrados) + 4) // 5)

    @rx.var
    def usuarios_paginados(self) -> list[list[str]]:
        inicio = (self.pagina_actual - 1) * 5
        pagina = list(self.usuarios_registrados[inicio : inicio + 5])
        while len(pagina) < 5:
            pagina.append(["", ""])
        return pagina

    def pagina_anterior(self):
        if self.pagina_actual > 1:
            self.pagina_actual -= 1

    def pagina_siguiente(self):
        if self.pagina_actual < self.total_paginas:
            self.pagina_actual += 1

    def set_input_usuario(self, valor: str):
        self.input_usuario = valor

    def set_input_contrasena(self, valor: str):
        self.input_contrasena = valor

    def set_input_rol(self, valor: str):
        self.input_rol = valor

    def limpiar_formularios(self):
        self.input_usuario = ""
        self.input_contrasena = ""
        self.input_rol = "usuario"
        self.error_mensaje = ""
        self.exito_mensaje = ""

    def comprobar_acceso_admin(self):
        if self.usuario_actual == "":
            return rx.redirect("/")

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT role FROM users WHERE username = ?", (self.usuario_actual,))
                resultado = cursor.fetchone()

                if not resultado or resultado[0] != "administrador":
                    return rx.redirect("/panel")
        except sqlite3.Error:
            return rx.redirect("/panel")

        self.pagina_actual = 1
        self.cargar_usuarios()

    def cargar_usuarios(self):
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT username, role FROM users ORDER BY id ASC")
                self.usuarios_registrados = [[str(row[0]), str(row[1])] for row in cursor.fetchall()]

                max_paginas = max(1, (len(self.usuarios_registrados) + 4) // 5)
                if self.pagina_actual > max_paginas:
                    self.pagina_actual = max_paginas
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al cargar usuarios: {e}"

    def anadir_usuario(self):
        self.error_mensaje = ""
        self.exito_mensaje = ""

        if not self.input_usuario or not self.input_contrasena:
            self.error_mensaje = "Rellena el nombre y la contraseña."
            return

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (self.input_usuario,))
                if cursor.fetchone():
                    self.error_mensaje = "El usuario ya existe."
                    return

                pass_hash = hashear_contrasena(self.input_contrasena)
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (self.input_usuario, pass_hash, self.input_rol)
                )
                conexion.commit()
                self.exito_mensaje = f"Usuario '{self.input_usuario}' añadido correctamente."
                self.limpiar_formularios()
                self.cargar_usuarios()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al crear: {e}"

    def cambiar_contrasena(self):
        self.error_mensaje = ""
        self.exito_mensaje = ""

        if not self.input_usuario or not self.input_contrasena:
            self.error_mensaje = "Introduce el usuario y la nueva contraseña."
            return

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (self.input_usuario,))
                if not cursor.fetchone():
                    self.error_mensaje = "El usuario no existe."
                    return

                pass_hash = hashear_contrasena(self.input_contrasena)
                cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pass_hash, self.input_usuario))
                conexion.commit()
                self.exito_mensaje = f"Contraseña de '{self.input_usuario}' actualizada."
                self.limpiar_formularios()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al actualizar: {e}"

    def borrar_usuario(self):
        self.error_mensaje = ""
        self.exito_mensaje = ""

        if not self.input_usuario:
            self.error_mensaje = "Introduce el nombre del usuario a borrar."
            return

        if self.input_usuario == "admin":
            self.error_mensaje = "Por seguridad, no se puede borrar al superadministrador."
            return

        if self.input_usuario == self.usuario_actual:
            self.error_mensaje = "No puedes borrar tu propia cuenta mientras estás conectado."
            return

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (self.input_usuario,))
                if not cursor.fetchone():
                    self.error_mensaje = "El usuario no existe."
                    return

                cursor.execute("DELETE FROM users WHERE username = ?", (self.input_usuario,))
                conexion.commit()
                self.exito_mensaje = f"Usuario '{self.input_usuario}' eliminado."
                self.limpiar_formularios()
                self.cargar_usuarios()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al borrar: {e}"


def fila_usuario(fila: list[str]) -> rx.Component:
    nombre_rol = rx.match(
        fila[1],
        ("administrador", "Administrador"),
        ("tecnico_agricola", "Técnico Agrícola"),
        "Usuario"
    )
    color_rol = rx.match(
        fila[1],
        ("administrador", "crimson"),
        ("tecnico_agricola", "blue"),
        "grass"
    )
    return rx.table.row(
        rx.table.cell(
            rx.cond(
                fila[0] != "",
                rx.text(fila[0], weight="bold", size="3", color="var(--gray-12)"),
                rx.text("-", size="3", opacity="0")
            )
        ),
        rx.table.cell(
            rx.cond(
                fila[1] != "",
                rx.badge(
                    nombre_rol,
                    color_scheme=color_rol,
                    variant="soft",
                    size="2"
                ),
                rx.badge("Usuario", variant="soft", size="2", opacity="0")
            )
        )
    )


def panel_gestor_usuarios() -> rx.Component:
    return rx.box(
        rx.html("""
            <style>
                :root, .light, .light-theme {
                    --gray-1: #F4F7F8 !important;
                    --gray-2: #EBF0F2 !important;
                    --gray-3: #E1E8EC !important;
                    --gray-4: #D3DEE3 !important;
                    --gray-5: #C5D4DC !important;
                    --gray-11: #4A636E !important;
                    --gray-12: #1A2E35 !important;
                }
                .dark, .dark-theme, [data-theme="dark"] {
                    --gray-1: #0D2F3A !important;
                    --gray-2: #09242E !important;
                    --gray-3: #123C4A !important;
                    --gray-4: #174859 !important;
                    --gray-5: #1D566B !important;
                    --gray-11: #8FB4C2 !important;
                    --gray-12: #E2F1F5 !important;
                }
            </style>
        """),

        rx.hstack(
            rx.hstack(
                rx.icon(tag="shield-alert", color="crimson", size=30),
                rx.heading("Gestión de Usuarios", size="5", color="var(--gray-12)", weight="bold"),
                align_items="center",
                spacing="3"
            ),
            rx.hstack(
                rx.color_mode.button(),
                rx.button(
                    rx.icon(tag="arrow-left", size=16),
                    "Volver al Panel",
                    on_click=rx.redirect("/panel"),
                    color_scheme="gray",
                    variant="soft",
                    size="2"
                ),
                spacing="4",
                align_items="center"
            ),
            justify_content="space-between",
            width="100%",
            padding="0.8em 2em",
            border_bottom="1px solid var(--gray-5)",
            background_color="var(--gray-2)"
        ),

        rx.center(
            rx.hstack(
                rx.vstack(
                    rx.heading("Usuarios Registrados", size="6", color="var(--gray-12)"),
                    rx.card(
                        rx.vstack(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell("Usuario", width="55%"),
                                        rx.table.column_header_cell("Rol", width="45%")
                                    )
                                ),
                                rx.table.body(rx.foreach(GestorUsuariosState.usuarios_paginados, fila_usuario)),
                                variant="surface",
                                size="3",
                                width="100%",
                                style={"table_layout": "fixed"}
                            ),
                            rx.hstack(
                                rx.button(
                                    rx.icon(tag="chevron-left", size=16),
                                    "Anterior",
                                    on_click=GestorUsuariosState.pagina_anterior,
                                    disabled=GestorUsuariosState.pagina_actual <= 1,
                                    color_scheme="gray",
                                    variant="soft",
                                    size="2"
                                ),
                                rx.text(
                                    "Página ",
                                    GestorUsuariosState.pagina_actual,
                                    " de ",
                                    GestorUsuariosState.total_paginas,
                                    size="2",
                                    weight="medium",
                                    color="var(--gray-11)"
                                ),
                                rx.button(
                                    "Siguiente",
                                    rx.icon(tag="chevron-right", size=16),
                                    on_click=GestorUsuariosState.pagina_siguiente,
                                    disabled=GestorUsuariosState.pagina_actual >= GestorUsuariosState.total_paginas,
                                    color_scheme="gray",
                                    variant="soft",
                                    size="2"
                                ),
                                justify_content="space-between",
                                align_items="center",
                                width="100%",
                                padding_top="1em"
                            ),
                            justify_content="space-between",
                            height="100%",
                            spacing="4",
                            width="100%"
                        ),
                        flex="1",
                        width="100%",
                        padding="1.8em",
                        border="1px solid var(--gray-5)",
                        background_color="var(--gray-2)",
                        box_shadow="md",
                        border_radius="16px"
                    ),
                    width=["100%", "100%", "47%"],
                    align_items="stretch",
                    spacing="4"
                ),

                rx.vstack(
                    rx.heading("Acciones Administrativas", size="6", color="var(--gray-12)"),

                    rx.cond(GestorUsuariosState.error_mensaje != "",
                        rx.callout.root(rx.callout.icon("alert-triangle"), rx.callout.text(GestorUsuariosState.error_mensaje), color_scheme="red", width="100%")),
                    rx.cond(GestorUsuariosState.exito_mensaje != "",
                        rx.callout.root(rx.callout.icon("check-circle"), rx.callout.text(GestorUsuariosState.exito_mensaje), color_scheme="grass", width="100%")),

                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("Añadir", value="add"),
                            rx.tabs.trigger("Contraseña", value="pass"),
                            rx.tabs.trigger("Borrar", value="del"),
                            size="2",
                            width="100%"
                        ),

                        rx.tabs.content(
                            rx.card(
                                rx.vstack(
                                    rx.text("Alta de nueva cuenta en el sistema", size="2", color="var(--gray-11)"),
                                    rx.input(placeholder="Nombre de usuario", value=GestorUsuariosState.input_usuario, on_change=GestorUsuariosState.set_input_usuario, width="100%", size="3", variant="surface"),
                                    rx.input(type="password", placeholder="Contraseña", value=GestorUsuariosState.input_contrasena, on_change=GestorUsuariosState.set_input_contrasena, width="100%", size="3", variant="surface"),
                                    rx.select(["usuario", "tecnico_agricola", "administrador"], value=GestorUsuariosState.input_rol, on_change=GestorUsuariosState.set_input_rol, width="100%", size="3", variant="surface"),
                                    rx.button("Añadir Usuario", on_click=GestorUsuariosState.anadir_usuario, color_scheme="grass", width="100%", size="3", margin_top="0.5em"),
                                    spacing="4",
                                    width="100%"
                                ),
                                padding="2em",
                                background_color="var(--gray-2)",
                                border="1px solid var(--gray-5)",
                                box_shadow="md",
                                border_radius="16px",
                                width="100%"
                            ), value="add", width="100%", padding_top="0.8em"
                        ),

                        rx.tabs.content(
                            rx.card(
                                rx.vstack(
                                    rx.text("Cambiar clave a un usuario existente", size="2", color="var(--gray-11)"),
                                    rx.input(placeholder="Nombre de usuario exacto", value=GestorUsuariosState.input_usuario, on_change=GestorUsuariosState.set_input_usuario, width="100%", size="3", variant="surface"),
                                    rx.input(type="password", placeholder="Nueva contraseña", value=GestorUsuariosState.input_contrasena, on_change=GestorUsuariosState.set_input_contrasena, width="100%", size="3", variant="surface"),
                                    rx.button("Actualizar Contraseña", on_click=GestorUsuariosState.cambiar_contrasena, color_scheme="blue", width="100%", size="3", margin_top="0.5em"),
                                    spacing="4",
                                    width="100%"
                                ),
                                padding="2em",
                                background_color="var(--gray-2)",
                                border="1px solid var(--gray-5)",
                                box_shadow="md",
                                border_radius="16px",
                                width="100%"
                            ), value="pass", width="100%", padding_top="0.8em"
                        ),

                        rx.tabs.content(
                            rx.card(
                                rx.vstack(
                                    rx.text("¡Atención! Esta acción elimina el acceso de forma permanente.", size="2", color="crimson"),
                                    rx.input(placeholder="Nombre de usuario a borrar", value=GestorUsuariosState.input_usuario, on_change=GestorUsuariosState.set_input_usuario, width="100%", size="3", variant="surface"),
                                    rx.button("Borrar Usuario", on_click=GestorUsuariosState.borrar_usuario, color_scheme="red", width="100%", size="3", margin_top="0.5em"),
                                    spacing="4",
                                    width="100%"
                                ),
                                padding="2em",
                                background_color="var(--gray-2)",
                                border="1px solid var(--gray-5)",
                                box_shadow="md",
                                border_radius="16px",
                                width="100%"
                            ), value="del", width="100%", padding_top="0.8em"
                        ),
                        default_value="add",
                        flex="1",
                        width="100%"
                    ),
                    width=["100%", "100%", "49%"],
                    align_items="stretch",
                    spacing="4"
                ),
                width=["100%", "95%", "92%", "1300px"],
                justify_content="between",
                align_items="stretch",
                flex_direction=["column", "column", "row"],
                spacing="9"
            ),
            flex="1",
            width="100%",
            padding="2.5em 1.5em"
        ),
        display="flex",
        flex_direction="column",
        width="100%",
        min_height="100vh",
        background_color="var(--gray-1)"
    )