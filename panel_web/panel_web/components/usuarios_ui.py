import reflex as rx

try:
    from gestor_usuarios import GestorUsuariosState
    from ui_shared import ESTILOS_TEMA_GLOBAL, barra_navegacion_simple
except ImportError:
    from ..gestor_usuarios import GestorUsuariosState
    from ..ui_shared import ESTILOS_TEMA_GLOBAL, barra_navegacion_simple


def fila_usuario(fila: list[str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.cond(
                fila[0] != "",
                rx.text(fila[0], weight="bold", size="3", color="var(--gray-12)"),
                rx.text("-", size="3", opacity="0"),
            )
        ),
        rx.table.cell(
            rx.cond(
                fila[1] != "",
                rx.cond(
                    fila[1] == "administrador",
                    rx.badge("Administrador", color_scheme="crimson", variant="soft", size="2"),
                    rx.cond(
                        fila[1] == "tecnico_agricola",
                        rx.badge("Técnico Agrícola", color_scheme="blue", variant="soft", size="2"),
                        rx.badge("Usuario", color_scheme="grass", variant="soft", size="2"),
                    ),
                ),
                rx.badge("Usuario", variant="soft", size="2", opacity="0"),
            )
        ),
    )


def panel_gestor_usuarios() -> rx.Component:
    return rx.box(
        rx.html(ESTILOS_TEMA_GLOBAL),
        barra_navegacion_simple(
            "Gestión de Usuarios",
            icono="shield-alert",
            color_icono="crimson",
            color_titulo="var(--gray-12)",
        )
    ),

def panel_gestor_usuarios() -> rx.Component:
    return rx.box(
        rx.html(ESTILOS_TEMA_GLOBAL),
        rx.hstack(
            rx.hstack(
                rx.icon(tag="shield-alert", color="crimson", size=30),
                rx.heading("Gestión de Usuarios", size="5", color="var(--gray-12)", weight="bold"),
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
                ),
                spacing="4",
                align_items="center",
            ),
            justify_content="space-between",
            width="100%",
            padding="0.8em 2em",
            border_bottom="1px solid var(--gray-5)",
            background_color="var(--gray-2)",
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
                                        rx.table.column_header_cell("Rol", width="45%"),
                                    )
                                ),
                                rx.table.body(rx.foreach(GestorUsuariosState.usuarios_paginados, lambda fila: fila_usuario(fila))),
                                variant="surface",
                                size="3",
                                width="100%",
                                style={"table_layout": "fixed"},
                            ),
                            rx.hstack(
                                rx.button(
                                    rx.icon(tag="chevron-left", size=16),
                                    "Anterior",
                                    on_click=GestorUsuariosState.pagina_anterior,
                                    disabled=GestorUsuariosState.pagina_actual <= 1,
                                    color_scheme="gray",
                                    variant="soft",
                                    size="2",
                                ),
                                rx.text(
                                    "Página ",
                                    GestorUsuariosState.pagina_actual,
                                    " de ",
                                    GestorUsuariosState.total_paginas,
                                    size="2",
                                    weight="medium",
                                    color="var(--gray-11)",
                                ),
                                rx.button(
                                    "Siguiente",
                                    rx.icon(tag="chevron-right", size=16),
                                    on_click=GestorUsuariosState.pagina_siguiente,
                                    disabled=GestorUsuariosState.pagina_actual >= GestorUsuariosState.total_paginas,
                                    color_scheme="gray",
                                    variant="soft",
                                    size="2",
                                ),
                                justify_content="space-between",
                                align_items="center",
                                width="100%",
                                padding_top="1em",
                            ),
                            justify_content="space-between",
                            height="100%",
                            spacing="4",
                            width="100%",
                        ),
                        flex="1",
                        width="100%",
                        padding="1.8em",
                        border="1px solid var(--gray-5)",
                        background_color="var(--gray-2)",
                        box_shadow="md",
                        border_radius="16px",
                    ),
                    width=["100%", "100%", "47%"],
                    align_items="stretch",
                    spacing="4",
                ),
                rx.vstack(
                    rx.heading("Acciones Administrativas", size="6", color="var(--gray-12)"),
                    rx.cond(
                        GestorUsuariosState.error_mensaje != "",
                        rx.callout.root(
                            rx.callout.icon("alert-triangle"),
                            rx.callout.text(GestorUsuariosState.error_mensaje),
                            color_scheme="red",
                            width="100%",
                        ),
                    ),
                    rx.cond(
                        GestorUsuariosState.exito_mensaje != "",
                        rx.callout.root(
                            rx.callout.icon("check-circle"),
                            rx.callout.text(GestorUsuariosState.exito_mensaje),
                            color_scheme="grass",
                            width="100%",
                        ),
                    ),
                    rx.tabs.root(
                        rx.tabs.list(
                            rx.tabs.trigger("Añadir", value="add"),
                            rx.tabs.trigger("Contraseña", value="pass"),
                            rx.tabs.trigger("Borrar", value="del"),
                            size="2",
                            width="100%",
                        ),
                        rx.tabs.content(
                            rx.card(
                                rx.vstack(
                                    rx.text("Alta de nueva cuenta en el sistema", size="2", color="var(--gray-11)"),
                                    rx.input(
                                        placeholder="Nombre de usuario",
                                        value=GestorUsuariosState.input_usuario,
                                        on_change=GestorUsuariosState.set_input_usuario,
                                        width="100%",
                                        size="3",
                                        variant="surface",
                                    ),
                                    rx.input(
                                        type="password",
                                        placeholder="Contraseña",
                                        value=GestorUsuariosState.input_contrasena,
                                        on_change=GestorUsuariosState.set_input_contrasena,
                                        width="100%",
                                        size="3",
                                        variant="surface",
                                    ),
                                    rx.select(
                                        ["usuario", "tecnico_agricola", "administrador"],
                                        value=GestorUsuariosState.input_rol,
                                        on_change=GestorUsuariosState.set_input_rol,
                                        width="100%",
                                        size="3",
                                        variant="surface",
                                    ),
                                    rx.button(
                                        "Añadir Usuario",
                                        on_click=GestorUsuariosState.anadir_usuario,
                                        color_scheme="grass",
                                        width="100%",
                                        size="3",
                                        margin_top="0.5em",
                                    ),
                                    spacing="4",
                                    width="100%",
                                ),
                                padding="2em",
                                background_color="var(--gray-2)",
                                border="1px solid var(--gray-5)",
                                box_shadow="md",
                                border_radius="16px",
                                width="100%",
                            ),
                            value="add",
                            width="100%",
                            padding_top="0.8em",
                        ),
                        rx.tabs.content(
                            rx.card(
                                rx.vstack(
                                    rx.text("Cambiar clave a un usuario existente", size="2", color="var(--gray-11)"),
                                    rx.input(
                                        placeholder="Nombre de usuario exacto",
                                        value=GestorUsuariosState.input_usuario,
                                        on_change=GestorUsuariosState.set_input_usuario,
                                        width="100%",
                                        size="3",
                                        variant="surface",
                                    ),
                                    rx.input(
                                        type="password",
                                        placeholder="Nueva contraseña",
                                        value=GestorUsuariosState.input_contrasena,
                                        on_change=GestorUsuariosState.set_input_contrasena,
                                        width="100%",
                                        size="3",
                                        variant="surface",
                                    ),
                                    rx.button(
                                        "Actualizar Contraseña",
                                        on_click=GestorUsuariosState.cambiar_contrasena,
                                        color_scheme="blue",
                                        width="100%",
                                        size="3",
                                        margin_top="0.5em",
                                    ),
                                    spacing="4",
                                    width="100%",
                                ),
                                padding="2em",
                                background_color="var(--gray-2)",
                                border="1px solid var(--gray-5)",
                                box_shadow="md",
                                border_radius="16px",
                                width="100%",
                            ),
                            value="pass",
                            width="100%",
                            padding_top="0.8em",
                        ),
                        rx.tabs.content(
                            rx.card(
                                rx.vstack(
                                    rx.text(
                                        "¡Atención! Esta acción elimina el acceso de forma permanente.",
                                        size="2",
                                        color="crimson",
                                    ),
                                    rx.input(
                                        placeholder="Nombre de usuario a borrar",
                                        value=GestorUsuariosState.input_usuario,
                                        on_change=GestorUsuariosState.set_input_usuario,
                                        width="100%",
                                        size="3",
                                        variant="surface",
                                    ),
                                    rx.button(
                                        "Borrar Usuario",
                                        on_click=GestorUsuariosState.borrar_usuario,
                                        color_scheme="red",
                                        width="100%",
                                        size="3",
                                        margin_top="0.5em",
                                    ),
                                    spacing="4",
                                    width="100%",
                                ),
                                padding="2em",
                                background_color="var(--gray-2)",
                                border="1px solid var(--gray-5)",
                                box_shadow="md",
                                border_radius="16px",
                                width="100%",
                            ),
                            value="del",
                            width="100%",
                            padding_top="0.8em",
                        ),
                        default_value="add",
                        flex="1",
                        width="100%",
                    ),
                    width=["100%", "100%", "49%"],
                    align_items="stretch",
                    spacing="4",
                ),
                width=["100%", "95%", "92%", "1300px"],
                justify_content="between",
                align_items="stretch",
                flex_direction=["column", "column", "row"],
                spacing="9",
            ),
            flex="1",
            width="100%",
            padding="2.5em 1.5em",
        ),
        display="flex",
        flex_direction="column",
        width="100%",
        min_height="100vh",
        background_color="var(--gray-1)",
    )
           # ... Pega aquí desde rx.center( hasta el cierre de panel_gestor_usuarios() ...