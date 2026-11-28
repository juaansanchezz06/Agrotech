import reflex as rx

try:
    from components.dashboard_ui import index
    from components.parcelas_ui import panel_gestor_parcelas
    from components.usuarios_ui import panel_gestor_usuarios
    from dashboard_state import EstadoAgrotech
    from gestor_parcelas import GestorParcelasState
    from gestor_usuarios import GestorUsuariosState
    from login import login_page
except ImportError:
    from .components.dashboard_ui import index
    from .components.parcelas_ui import panel_gestor_parcelas
    from .components.usuarios_ui import panel_gestor_usuarios
    from .dashboard_state import EstadoAgrotech
    from .gestor_parcelas import GestorParcelasState
    from .gestor_usuarios import GestorUsuariosState
    from .login import login_page

app = rx.App()
app.add_page(login_page, route="/", title="Login | Agrotech")
app.add_page(index, route="/panel", on_load=EstadoAgrotech.comprobar_acceso, title="Panel Agrotech")
app.add_page(
    panel_gestor_usuarios,
    route="/gestor-usuarios",
    on_load=GestorUsuariosState.comprobar_acceso_admin,
    title="Gestor de Usuarios",
)
app.add_page(
    panel_gestor_parcelas,
    route="/gestor-parcelas",
    on_load=GestorParcelasState.comprobar_acceso_parcelas,
    title="Gestión de Parcelas",
)


