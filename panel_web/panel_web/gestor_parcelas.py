import reflex as rx
import sqlite3
import os

try:
    from login import BaseState
except ImportError:
    from .login import BaseState

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")


class GestorParcelasState(BaseState):
    def comprobar_acceso_parcelas(self):
        if self.usuario_actual == "":
            return rx.redirect("/")

        try:
            with sqlite3.connect(RUTA_DB) as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT role FROM users WHERE username = ?", (self.usuario_actual,))
                resultado = cursor.fetchone()

                if not resultado or resultado[0] not in ["administrador", "tecnico_agricola"]:
                    return rx.redirect("/panel")
        except sqlite3.Error:
            return rx.redirect("/panel")


def panel_gestor_parcelas() -> rx.Component:
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
                rx.icon(tag="map-pin", color="var(--grass-9)", size=30),
                rx.heading("Gestión de Parcelas", size="5", color="var(--gray-12)", weight="bold"),
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

        rx.vstack(
            rx.card(
                rx.vstack(
                    rx.heading("Panel de Parcelas", size="5", color="var(--gray-12)"),
                    rx.text("Sección accesible solo para Administrador y Técnico Agrícola.", color="var(--gray-11)"),
                    spacing="2"
                ),
                width="100%",
                padding="2em",
                border="1px solid var(--gray-5)",
                background_color="var(--gray-2)"
            ),
            width=["100%", "95%", "85%", "1200px"],
            margin="0 auto",
            padding="2em 1em"
        ),
        width="100%",
        min_height="100vh",
        background_color="var(--gray-1)"
    )