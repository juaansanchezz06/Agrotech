import os
import sys
import reflex as rx

RUTA_PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if RUTA_PROYECTO not in sys.path:
    sys.path.insert(0, RUTA_PROYECTO)

ESTILOS_TEMA_GLOBAL = """
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

SVG_CAMPO = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <polygon points="90,26 146,52 90,78 34,52" fill="#6BBF6B" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="62" y1="39" x2="118" y2="65" stroke="#EBF0F2" stroke-width="2.5"/>
  <line x1="118" y1="39" x2="62" y2="65" stroke="#EBF0F2" stroke-width="2.5"/>
  <path d="M68,14 C61,14 56,19 56,26 C56,35 68,46 68,46 C68,46 80,35 80,26 C80,19 75,14 68,14 Z" fill="#81C784" stroke="#2F6F3E" stroke-width="2"/>
  <circle cx="68" cy="25" r="4" fill="#FFFFFF"/>
</svg>
"""

SVG_SURCOS = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <polygon points="92,28 148,54 88,82 32,56" fill="#6BBF6B" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="46" y1="50" x2="104" y2="76" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="58" y1="44" x2="116" y2="70" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="70" y1="38" x2="128" y2="64" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="82" y1="33" x2="140" y2="59" stroke="#2F6F3E" stroke-width="1.6"/>
  <path d="M62,14 C55,14 50,19 50,26 C50,35 62,46 62,46 C62,46 74,35 74,26 C74,19 69,14 62,14 Z" fill="#81C784" stroke="#2F6F3E" stroke-width="2"/>
  <circle cx="62" cy="25" r="4" fill="#FFFFFF"/>
</svg>
"""

SVG_INVERNADERO = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <path d="M44,58 L44,40 C44,24 76,24 76,40 L76,58 Z" fill="rgba(107,191,107,0.18)" stroke="#2F6F3E" stroke-width="2"/>
  <path d="M44,40 C44,24 76,24 76,40 L134,26 C134,12 104,12 104,26 Z" fill="rgba(107,191,107,0.12)" stroke="#2F6F3E" stroke-width="1.8"/>
  <polyline points="76,58 134,44 134,26" fill="none" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="44" y1="58" x2="76" y2="58" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="60" y1="28" x2="60" y2="58" stroke="#2F6F3E" stroke-width="1.4"/>
  <line x1="95" y1="35" x2="95" y2="53" stroke="#2F6F3E" stroke-width="1.4"/>
  <line x1="115" y1="30" x2="115" y2="48" stroke="#2F6F3E" stroke-width="1.4"/>
  <line x1="44" y1="45" x2="134" y2="31" stroke="#2F6F3E" stroke-width="1.3"/>
</svg>
"""

SVG_VINEDO = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <line x1="40" y1="68" x2="95" y2="26" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="65" y1="74" x2="120" y2="32" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="90" y1="80" x2="145" y2="38" stroke="#2F6F3E" stroke-width="1.6"/>
  <line x1="40" y1="54" x2="95" y2="14" stroke="#2F6F3E" stroke-width="1.3" stroke-dasharray="3,2"/>
  <line x1="65" y1="60" x2="120" y2="20" stroke="#2F6F3E" stroke-width="1.3" stroke-dasharray="3,2"/>
  <line x1="90" y1="66" x2="145" y2="26" stroke="#2F6F3E" stroke-width="1.3" stroke-dasharray="3,2"/>
  <line x1="45" y1="48" x2="45" y2="72" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="70" y1="54" x2="70" y2="78" stroke="#2F6F3E" stroke-width="2"/>
  <line x1="95" y1="60" x2="95" y2="84" stroke="#2F6F3E" stroke-width="2"/>
  <circle cx="56" cy="52" r="4" fill="#6BBF6B"/>
  <circle cx="81" cy="58" r="4" fill="#6BBF6B"/>
  <circle cx="106" cy="64" r="4" fill="#6BBF6B"/>
</svg>
"""

SVG_HUERTO = """
<svg viewBox="0 0 180 100" width="145" height="82" xmlns="http://www.w3.org/2000/svg">
  <rect x="34" y="18" width="112" height="64" rx="8" fill="rgba(107,191,107,0.14)" stroke="#2F6F3E" stroke-width="2"/>
  <rect x="42" y="25" width="38" height="22" rx="3" fill="#6BBF6B" opacity="0.75"/>
  <rect x="42" y="53" width="38" height="22" rx="3" fill="#6BBF6B" opacity="0.55"/>
  <line x1="46" y1="59" x2="76" y2="59" stroke="#2F6F3E" stroke-width="1.5"/>
  <line x1="46" y1="65" x2="76" y2="65" stroke="#2F6F3E" stroke-width="1.5"/>
  <line x1="46" y1="71" x2="76" y2="71" stroke="#2F6F3E" stroke-width="1.5"/>
  <rect x="88" y="25" width="18" height="50" rx="3" fill="rgba(77,208,225,0.22)" stroke="#2F6F3E" stroke-width="1.4"/>
  <circle cx="97" cy="36" r="3" fill="#2F6F3E"/>
  <circle cx="97" cy="50" r="3" fill="#2F6F3E"/>
  <circle cx="97" cy="64" r="3" fill="#2F6F3E"/>
  <rect x="114" y="25" width="24" height="50" rx="3" fill="rgba(107,191,107,0.28)" stroke="#2F6F3E" stroke-width="1.4"/>
  <circle cx="126" cy="60" r="5" fill="#6BBF6B" stroke="#2F6F3E" stroke-width="1.4"/>
</svg>
"""

ESTILO_TARJETA_BASE = {
    "padding": "1.5em",
    "border_radius": "16px",
    "background_color": "var(--gray-2)",
    "box_shadow": "0 2px 10px rgba(0, 0, 0, 0.03)",
    "width": "100%",
    "min_width": "0",
}


def barra_navegacion_simple(
    titulo: str,
    icono: str = "leaf",
    color_icono: str = "var(--grass-9)",
    color_titulo: str = "var(--grass-11)",
    usuario: str = "",
) -> rx.Component:
    """Cabecera unificada para pantallas secundarias (/gestor-parcelas, /gestor-usuarios)."""
    return rx.hstack(
        rx.hstack(
            rx.icon(tag=icono, color=color_icono, size=28),
            rx.heading(titulo, size="5", color=color_titulo, weight="bold"),
            align_items="center",
            spacing="3",
        ),
        rx.hstack(
            rx.color_mode.button(),
            rx.button(
                rx.icon(tag="arrow-left", size=16),
                "Volver al Panel",
                on_click=rx.redirect("/panel"),
                color_scheme="gray",
                variant="soft",
                size="2",
                cursor="pointer",
            ),
            rx.cond(
                usuario != "",
                rx.hstack(
                    rx.box(width="8px", height="8px", border_radius="50%", background_color="var(--grass-9)"),
                    rx.text(usuario, weight="bold", size="2", color="var(--gray-12)"),
                    rx.avatar(fallback=usuario[:1].upper(), size="1", color_scheme="grass", variant="soft"),
                    padding="0.35em 0.75em",
                    border_radius="12px",
                    background_color="var(--gray-3)",
                    border="1px solid var(--gray-5)",
                    align_items="center",
                    spacing="2",
                ),
            ),
            spacing="3",
            align_items="center",
        ),
        justify_content="space-between",
        align_items="center",
        wrap="wrap",
        spacing="3",
        width="100%",
        min_width="0",
        padding=["0.8em 1em", "0.8em 2em"],
        border_bottom="1px solid var(--gray-5)",
        background_color="var(--gray-2)",
    )

    return rx.hstack(
        rx.hstack(
            rx.icon(tag=icono, color=color_icono, size=28),
            rx.heading(titulo, size="5", color=color_titulo, weight="bold"),
            align_items="center",
            spacing="3",
        ),
        rx.hstack(*derecha, spacing="3", align_items="center"),
        justify_content="space-between",
        align_items="center",
        wrap="wrap",
        spacing="3",
        width="100%",
        min_width="0",
        padding=["0.8em 1em", "0.8em 2em"],
        border_bottom="1px solid var(--gray-5)",
        background_color="var(--gray-2)",
    )