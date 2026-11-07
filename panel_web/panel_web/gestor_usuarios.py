import reflex as rx
import sqlite3
import os
import hashlib
from .login import BaseState

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")

# 1. ESTADO DEL GESTOR
class GestorUsuariosState(BaseState):
    usuarios_registrados: list[list[str]] = []
    
    # Variables de los formularios
    input_usuario: str = ""
    input_contrasena: str = ""
    input_rol: str = "usuario"
    
    # Mensajes
    error_mensaje: str = ""
    exito_mensaje: str = ""

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
                
                # Si no existe o no es administrador, lo echamos al panel
                if not resultado or resultado[0] != "administrador":
                    return rx.redirect("/panel")
        except sqlite3.Error:
            return rx.redirect("/panel")
            
        self.cargar_usuarios()

    def cargar_usuarios(self):
        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT username, role FROM users ORDER BY id ASC")
                self.usuarios_registrados = [[str(row[0]), str(row[1])] for row in cursor.fetchall()]
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
                
                pass_hash = hashlib.sha256(self.input_contrasena.encode('utf-8')).hexdigest()
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
                
                pass_hash = hashlib.sha256(self.input_contrasena.encode('utf-8')).hexdigest()
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


# 2. INTERFAZ
def fila_usuario(fila: list[str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(fila[0], weight="bold", color="var(--gray-12)")),
        rx.table.cell(
            rx.badge(
                fila[1].capitalize(), 
                color_scheme=rx.cond(fila[1] == "administrador", "crimson", "grass"), 
                variant="soft"
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
        
        # NAVBAR SIMPLE
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
        
        # CONTENIDO PRINCIPAL
        rx.hstack(
            # COLUMNA IZQUIERDA: Tabla de usuarios actuales
            rx.vstack(
                rx.heading("Usuarios Registrados", size="5", color="var(--gray-12)"),
                rx.card(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Usuario"),
                                rx.table.column_header_cell("Rol")
                            )
                        ),
                        rx.table.body(rx.foreach(GestorUsuariosState.usuarios_registrados, fila_usuario)),
                        variant="surface", size="3"
                    ),
                    width="100%", border="1px solid var(--gray-5)", background_color="var(--gray-2)", box_shadow="sm"
                ),
                width=["100%", "100%", "40%"],
                align_items="stretch",
                spacing="4"
            ),
            
            # COLUMNA DERECHA: Controles de administración
            rx.vstack(
                rx.heading("Acciones Administrativas", size="5", color="var(--gray-12)"),
                
                # Mensajes
                rx.cond(GestorUsuariosState.error_mensaje != "",
                    rx.callout.root(rx.callout.icon("alert-triangle"), rx.callout.text(GestorUsuariosState.error_mensaje), color_scheme="red", width="100%")),
                rx.cond(GestorUsuariosState.exito_mensaje != "",
                    rx.callout.root(rx.callout.icon("check-circle"), rx.callout.text(GestorUsuariosState.exito_mensaje), color_scheme="grass", width="100%")),
                
                # Pestañas de Acciones
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("Añadir", value="add"),
                        rx.tabs.trigger("Contraseña", value="pass"),
                        rx.tabs.trigger("Borrar", value="del"),
                        width="100%"
                    ),
                    
                    # 1. AÑADIR
                    rx.tabs.content(
                        rx.card(
                            rx.vstack(
                                rx.input(placeholder="Nombre de usuario", value=GestorUsuariosState.input_usuario, on_change=GestorUsuariosState.set_input_usuario, width="100%", variant="surface"),
                                rx.input(type="password", placeholder="Contraseña", value=GestorUsuariosState.input_contrasena, on_change=GestorUsuariosState.set_input_contrasena, width="100%", variant="surface"),
                                rx.select(["usuario", "administrador"], value=GestorUsuariosState.input_rol, on_change=GestorUsuariosState.set_input_rol, width="100%", variant="surface"),
                                rx.button("Añadir Usuario", on_click=GestorUsuariosState.anadir_usuario, color_scheme="grass", width="100%")
                            ),
                            background_color="var(--gray-2)", border="1px solid var(--gray-5)"
                        ), value="add"
                    ),
                    
                    # 2. CAMBIAR CLAVE
                    rx.tabs.content(
                        rx.card(
                            rx.vstack(
                                rx.text("Cambiar clave a un usuario existente", size="2", color="var(--gray-11)"),
                                rx.input(placeholder="Nombre de usuario exacto", value=GestorUsuariosState.input_usuario, on_change=GestorUsuariosState.set_input_usuario, width="100%", variant="surface"),
                                rx.input(type="password", placeholder="Nueva contraseña", value=GestorUsuariosState.input_contrasena, on_change=GestorUsuariosState.set_input_contrasena, width="100%", variant="surface"),
                                rx.button("Actualizar Contraseña", on_click=GestorUsuariosState.cambiar_contrasena, color_scheme="blue", width="100%")
                            ),
                            background_color="var(--gray-2)", border="1px solid var(--gray-5)"
                        ), value="pass"
                    ),
                    
                    # 3. BORRAR
                    rx.tabs.content(
                        rx.card(
                            rx.vstack(
                                rx.text("¡Atención! Acción irreversible", size="2", color="crimson"),
                                rx.input(placeholder="Nombre de usuario a borrar", value=GestorUsuariosState.input_usuario, on_change=GestorUsuariosState.set_input_usuario, width="100%", variant="surface"),
                                rx.button("Borrar Usuario", on_click=GestorUsuariosState.borrar_usuario, color_scheme="red", width="100%")
                            ),
                            background_color="var(--gray-2)", border="1px solid var(--gray-5)"
                        ), value="del"
                    ),
                    default_value="add", width="100%"
                ),
                width=["100%", "100%", "60%"],
                align_items="stretch",
                spacing="4"
            ),
            width=["100%", "95%", "85%", "1200px"],
            margin="0 auto",
            padding="2em 1em",
            align_items="start",
            flex_direction=["column", "column", "row"],
            spacing="6"
        ),
        width="100%",
        min_height="100vh",
        background_color="var(--gray-1)"
    )