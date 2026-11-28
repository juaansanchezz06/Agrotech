import sqlite3

import reflex as rx

try:
    from login import BaseState
except ImportError:
    from .login import BaseState

from funcs import conectar_db, generar_hash_password


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
            with conectar_db() as conexion:
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
            with conectar_db() as conexion:
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
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (self.input_usuario,))
                if cursor.fetchone():
                    self.error_mensaje = "El usuario ya existe."
                    return

                pass_hash = generar_hash_password(self.input_contrasena)
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (self.input_usuario, pass_hash, self.input_rol),
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
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (self.input_usuario,))
                if not cursor.fetchone():
                    self.error_mensaje = "El usuario no existe."
                    return

                pass_hash = generar_hash_password(self.input_contrasena)
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
            with conectar_db() as conexion:
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



    


