import reflex as rx

try:
    from dashboard_state import EstadoAgrotech, METRICAS_CONFIG
    from login import BaseState
    from ui_shared import ESTILOS_TEMA_GLOBAL, ESTILO_TARJETA_BASE
except ImportError:
    from ..dashboard_state import EstadoAgrotech, METRICAS_CONFIG
    from ..login import BaseState
    from ..ui_shared import ESTILOS_TEMA_GLOBAL, ESTILO_TARJETA_BASE

def tarjeta_kpi_superior(
    titulo: str,
    valor: str,
    unidad: str,
    estado_txt: str,
    es_critico: bool,
    icono: str,
    color_icono: str,
    metrica_key: str,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(
                        tag=icono,
                        size=18,
                        color=rx.cond(es_critico, "var(--red-11)", color_icono),
                    ),
                    width="34px",
                    height="34px",
                    border_radius="10px",
                    background_color=rx.cond(es_critico, "var(--red-3)", "var(--gray-3)"),
                    border=rx.cond(es_critico, "1px solid var(--red-7)", "1px solid var(--gray-5)"),
                ),
                rx.text(titulo, size="2", weight="medium", color="var(--gray-11)"),
                rx.spacer(),
                rx.cond(
                    es_critico,
                    rx.icon("triangle-alert", size=16, color="var(--red-11)"),
                    rx.box(),
                ),
                align="center",
                width="100%",
                spacing="2",
            ),
            rx.hstack(
                rx.text(
                    valor,
                    size="7",
                    weight="bold",
                    color=rx.cond(es_critico, "var(--red-11)", "var(--gray-12)"),
                    line_height="1.1",
                ),
                rx.text(unidad, size="3", weight="medium", color="var(--gray-11)"),
                align="baseline",
                spacing="1",
                margin_y="0.25em",
            ),
            rx.text(
                estado_txt,
                size="1",
                weight="bold",
                color=rx.cond(es_critico, "var(--red-11)", "var(--grass-11)"),
            ),
            align="start",
            spacing="2",
            width="100%",
        ),
        on_click=lambda: EstadoAgrotech.set_grafica_tipo(metrica_key),
        cursor="pointer",
        padding="1.15em 1.25em",
        border_radius="16px",
        background_color="var(--gray-2)",
        border=rx.cond(
            es_critico,
            "1.5px solid var(--red-9)",
            rx.cond(
                EstadoAgrotech.grafica_tipo == metrica_key,
                "1.5px solid var(--grass-9)",
                "1px solid var(--gray-5)",
            ),
        ),
        box_shadow="0 2px 10px rgba(0, 0, 0, 0.03)",
        _hover={"border_color": "var(--grass-9)"},
        transition="all 0.15s ease",
        width="100%",
        min_width="0",
    )


def _tab_metrica_grafica(etiqueta: str, valor_key: str) -> rx.Component:
    activo = EstadoAgrotech.grafica_tipo == valor_key
    return rx.button(
        etiqueta,
        on_click=lambda: EstadoAgrotech.set_grafica_tipo(valor_key),
        size="1",
        variant=rx.cond(activo, "solid", "soft"),
        color_scheme=rx.cond(activo, "grass", "gray"),
        border_radius="8px",
        height="28px",
        padding_x="0.85em",
        display="inline-flex",
        align_items="center",
        justify_content="center",
        cursor="pointer",
        font_weight="600",
    )


def _controles_fecha_y_zoom() -> rx.Component:
    return rx.hstack(
        rx.input(
            type="date",
            value=EstadoAgrotech.grafica_fecha_inicio,
            max=EstadoAgrotech.grafica_fecha_fin,
            on_change=EstadoAgrotech.set_grafica_fecha_inicio,
            variant="soft",
            color_scheme="grass",
            size="1",
        ),
        rx.input(
            type="date",
            value=EstadoAgrotech.grafica_fecha_fin,
            min=EstadoAgrotech.grafica_fecha_inicio,
            on_change=EstadoAgrotech.set_grafica_fecha_fin,
            variant="soft",
            color_scheme="grass",
            size="1",
        ),
        rx.icon_button(
            rx.icon("minus", size=14),
            on_click=EstadoAgrotech.reducir_zoom_grafica,
            disabled=EstadoAgrotech.zoom_grafica <= 100,
            variant="soft",
            color_scheme="grass",
            size="1",
            cursor=rx.cond(EstadoAgrotech.zoom_grafica <= 100, "not-allowed", "pointer"),
            title="Desampliar gráfica",
        ),
        rx.text(
            EstadoAgrotech.ancho_grafica,
            size="1",
            weight="bold",
            color="var(--gray-12)",
            min_width="3em",
            text_align="center",
        ),
        rx.icon_button(
            rx.icon("plus", size=14),
            on_click=EstadoAgrotech.aumentar_zoom_grafica,
            disabled=EstadoAgrotech.zoom_grafica >= 400,
            variant="soft",
            color_scheme="grass",
            size="1",
            cursor=rx.cond(EstadoAgrotech.zoom_grafica >= 400, "not-allowed", "pointer"),
            title="Ampliar gráfica",
        ),
        wrap="wrap",
        align="center",
        spacing="2",
    )


def _lienzo_recharts() -> rx.Component:
    return rx.box(
        rx.box(
            rx.recharts.line_chart(
                rx.recharts.cartesian_grid(
                    stroke_dasharray="3 3",
                    stroke="var(--gray-5)",
                ),
                rx.recharts.line(
                    data_key="Valor",
                    stroke="#64B5F6",
                    stroke_width=3,
                    dot={"fill": "#64B5F6", "stroke": "var(--gray-12)", "strokeWidth": 1, "r": 3.5},
                    active_dot={"r": 6, "fill": "var(--grass-9)", "stroke": "var(--gray-12)"},
                ),
                rx.recharts.line(
                    data_key="Error",
                    stroke="none",
                    stroke_width=0,
                    connect_nulls=False,
                    dot={"fill": "#ff5252", "stroke": "#ffffff", "strokeWidth": 2, "r": 6.5},
                    active_dot={"r": 8, "fill": "#ff1744", "stroke": "#ffffff", "strokeWidth": 2},
                ),
                rx.recharts.reference_line(
                    y=EstadoAgrotech.valor_medio,
                    stroke="var(--grass-9)",
                    stroke_dasharray="4 4",
                    stroke_width=2,
                ),
                rx.recharts.reference_line(
                    y=EstadoAgrotech.grafica_rango_min,
                    stroke="#ff5252",
                    stroke_dasharray="5 5",
                    stroke_width=2,
                ),
                rx.recharts.reference_line(
                    y=EstadoAgrotech.grafica_rango_max,
                    stroke="#ff5252",
                    stroke_dasharray="5 5",
                    stroke_width=2,
                ),
                rx.recharts.x_axis(
                    data_key="hora",
                    stroke="var(--gray-6)",
                    tick={"fill": "var(--gray-12)", "fontSize": 12},
                ),
                rx.recharts.y_axis(
                    domain=["auto", "auto"],
                    stroke="var(--gray-6)",
                    tick={"fill": "var(--gray-12)", "fontSize": 12},
                ),
                rx.recharts.graphing_tooltip(
                    content_style={
                        "backgroundColor": "var(--gray-3)",
                        "borderColor": "var(--gray-5)",
                        "borderRadius": "10px",
                        "color": "var(--gray-12)",
                    },
                    label_style={"color": "var(--gray-12)", "fontWeight": "bold"},
                    item_style={"fontWeight": "bold"},
                ),
                data=EstadoAgrotech.datos_grafica,
                height=280,
                width="100%",
            ),
            width=EstadoAgrotech.ancho_grafica,
            min_width="100%",
            overflow="hidden",
        ),
        id="scroll-grafica",
        width="100%",
        min_width="0",
        overflow_x=rx.cond(EstadoAgrotech.zoom_grafica > 100, "auto", "hidden"),
        padding_bottom="0.5em",
    )


def tarjeta_evolucion_grafica() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Evolución de mediciones", size="4", weight="bold", color="var(--gray-12)"),
                    rx.text(
                        EstadoAgrotech.grafica_nombre_metrica,
                        " · ",
                        EstadoAgrotech.parcela_seleccionada,
                        size="2",
                        color="var(--gray-11)",
                    ),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                _controles_fecha_y_zoom(),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="3",
            ),
            rx.hstack(
                *[_tab_metrica_grafica(m.nombre, m.clave_ui) for m in METRICAS_CONFIG],
                padding="0.35em",
                border_radius="10px",
                background_color="var(--gray-3)",
                border="1px solid var(--gray-5)",
                align="center",
                wrap="wrap",
                spacing="2",
                width="100%",
            ),
            rx.cond(
                EstadoAgrotech.grafica_tiene_excesos,
                rx.callout.root(
                    rx.callout.icon(rx.icon("triangle-alert", size=16)),
                    rx.callout.text(
                        "Límite superado: ",
                        rx.text.span(EstadoAgrotech.grafica_resumen_excesos, weight="bold"),
                    ),
                    color_scheme="red",
                    variant="surface",
                    size="1",
                    width="100%",
                ),
            ),
            _lienzo_recharts(),
            rx.hstack(
                rx.hstack(
                    rx.box(width="8px", height="8px", border_radius="50%", background_color="#64B5F6"),
                    rx.text(EstadoAgrotech.grafica_nombre_metrica, size="1", color="var(--gray-11)"),
                    rx.text(
                        "· Media: ",
                        EstadoAgrotech.valor_medio,
                        " ",
                        EstadoAgrotech.grafica_unidad,
                        size="1",
                        weight="bold",
                        color="var(--gray-12)",
                    ),
                    rx.cond(
                        EstadoAgrotech.grafica_tiene_excesos,
                        rx.hstack(
                            rx.box(width="8px", height="8px", border_radius="50%", background_color="#ff5252"),
                            rx.text("Fuera de rango", size="1", weight="bold", color="var(--red-11)"),
                            align="center",
                            spacing="1",
                            margin_left="0.5em",
                        ),
                    ),
                    align="center",
                    spacing="2",
                    wrap="wrap",
                ),
                rx.spacer(),
                rx.text(
                    "Rango recomendado: ",
                    EstadoAgrotech.grafica_rango_min,
                    " – ",
                    EstadoAgrotech.grafica_rango_max,
                    " ",
                    EstadoAgrotech.grafica_unidad,
                    size="1",
                    weight="medium",
                    color=rx.cond(EstadoAgrotech.grafica_tiene_excesos, "var(--red-11)", "var(--gray-11)"),
                ),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="2",
            ),
            spacing="4",
            width="100%",
            min_width="0",
        ),
        border=rx.cond(
            EstadoAgrotech.grafica_tiene_excesos,
            "1.5px solid var(--red-8)",
            "1px solid var(--gray-5)",
        ),
        **ESTILO_TARJETA_BASE,
    )


def fila_sensor_panel(item: list[str]) -> rx.Component:
    return rx.hstack(
        rx.center(
            rx.icon(tag=item[4], size=18, color="var(--grass-11)"),
            width="38px",
            height="38px",
            border_radius="10px",
            background_color="var(--gray-3)",
            border="1px solid var(--gray-5)",
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(item[0], size="2", weight="bold", color="var(--gray-12)"),
            rx.text(item[1], size="1", color="var(--gray-11)"),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.vstack(
            rx.hstack(
                rx.box(
                    width="7px",
                    height="7px",
                    border_radius="50%",
                    background_color=rx.cond(item[3] == "Conectado", "var(--grass-9)", "var(--amber-9)"),
                ),
                rx.text(
                    item[3],
                    size="1",
                    weight="bold",
                    color=rx.cond(item[3] == "Conectado", "var(--grass-11)", "var(--gray-11)"),
                ),
                align="center",
                spacing="1",
            ),
            rx.text(item[2], size="1", weight="medium", color="var(--gray-12)"),
            spacing="0",
            align="end",
        ),
        width="100%",
        align="center",
        padding_y="0.65em",
        border_bottom="1px solid var(--gray-4)",
    )


def tarjeta_sensores_derecha() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Sensores", size="4", weight="bold", color="var(--gray-12)"),
                    rx.text("Dispositivos de ", EstadoAgrotech.parcela_seleccionada, size="2", color="var(--gray-11)"),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.badge("5 / 5 activos", color_scheme="grass", variant="soft", size="2"),
                width="100%",
                align="start",
            ),
            rx.vstack(
                rx.foreach(EstadoAgrotech.sensores_parcela, fila_sensor_panel),
                spacing="0",
                width="100%",
            ),
            rx.spacer(),
            rx.cond(
                EstadoAgrotech.puede_gestionar_parcelas,
                rx.hstack(
                    rx.link(
                        rx.hstack(
                            rx.text("Gestionar parcelas y rangos", size="2", weight="bold", color="var(--grass-11)"),
                            rx.icon("arrow-right", size=15, color="var(--grass-11)"),
                            align="center",
                            spacing="1",
                        ),
                        on_click=rx.redirect("/gestor-parcelas"),
                        cursor="pointer",
                    ),
                    width="100%",
                    padding_top="0.5em",
                ),
            ),
            spacing="3",
            height="100%",
            width="100%",
        ),
        border="1px solid var(--gray-5)",
        **ESTILO_TARJETA_BASE,
    )


def fila_mi_parcela(fila: list[str]) -> rx.Component:
    es_roja = fila[5] == "red"
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.center(
                    rx.icon(
                        "box",
                        size=16,
                        color=rx.cond(es_roja, "var(--red-11)", "var(--grass-11)"),
                    ),
                    width="32px",
                    height="32px",
                    border_radius="8px",
                    background_color=rx.cond(es_roja, "var(--red-3)", "var(--gray-3)"),
                    border=rx.cond(es_roja, "1px solid var(--red-7)", "1px solid var(--gray-5)"),
                ),
                rx.vstack(
                    rx.text(fila[0], size="2", weight="bold", color="var(--gray-12)"),
                    rx.text(fila[1], size="1", color="var(--gray-11)"),
                    spacing="0",
                    align="start",
                ),
                align="center",
                spacing="2",
            )
        ),
        rx.table.cell(rx.text(fila[2], size="2", color="var(--gray-11)")),
        rx.table.cell(rx.text(fila[3], size="2", weight="bold", color="var(--gray-12)")),
        rx.table.cell(rx.badge(fila[4], color_scheme=fila[5], variant="soft")),
        rx.table.cell(
            rx.icon_button(
                rx.icon("arrow-right", size=14),
                on_click=lambda: EstadoAgrotech.set_parcela_seleccionada(fila[0]),
                variant="ghost",
                color_scheme="gray",
                size="1",
                cursor="pointer",
                title="Seleccionar parcela",
            )
        ),
        on_click=lambda: EstadoAgrotech.set_parcela_seleccionada(fila[0]),
        cursor="pointer",
        _hover={"background_color": "var(--gray-3)"},
    )


def tarjeta_mis_parcelas() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("Mis parcelas", size="4", weight="bold", color="var(--gray-12)"),
                    rx.text("Pulsa sobre una parcela para ver sus métricas y gráfica", size="2", color="var(--gray-11)"),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.cond(
                    EstadoAgrotech.puede_gestionar_parcelas,
                    rx.link(
                        rx.hstack(
                            rx.text("Ver todas", size="2", weight="bold", color="var(--grass-11)"),
                            rx.icon("arrow-right", size=15, color="var(--grass-11)"),
                            align="center",
                            spacing="1",
                        ),
                        on_click=rx.redirect("/gestor-parcelas"),
                        cursor="pointer",
                    ),
                ),
                width="100%",
                align="center",
            ),
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("PARCELA"),
                            rx.table.column_header_cell("DISPOSITIVOS"),
                            rx.table.column_header_cell("H. SUELO"),
                            rx.table.column_header_cell("ESTADO"),
                            rx.table.column_header_cell(""),
                        )
                    ),
                    rx.table.body(rx.foreach(EstadoAgrotech.parcelas_resumen, fila_mi_parcela)),
                    variant="ghost",
                    size="2",
                    width="100%",
                ),
                width="100%",
                overflow_x="auto",
            ),
            spacing="3",
            width="100%",
        ),
        border="1px solid var(--gray-5)",
        **ESTILO_TARJETA_BASE,
    )


def item_alerta_reciente(alerta: list[str]) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.icon("triangle-alert", size=18, color="var(--red-11)", flex_shrink="0"),
            rx.vstack(
                rx.text(alerta[0], size="2", weight="bold", color="var(--red-11)"),
                rx.text(alerta[1], size="1", color="var(--gray-11)"),
                spacing="1",
                align="start",
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        on_click=lambda: EstadoAgrotech.set_parcela_seleccionada(alerta[2]),
        cursor="pointer",
        padding="0.85em 1em",
        border_radius="12px",
        background_color="var(--red-3)",
        border="1px solid var(--red-7)",
        width="100%",
    )


def tarjeta_alertas_recientes() -> rx.Component:
    tiene_alertas = EstadoAgrotech.alertas_recientes_lista.length() > 0
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Alertas recientes", size="4", weight="bold", color="var(--gray-12)"),
                rx.spacer(),
                rx.cond(
                    tiene_alertas,
                    rx.badge(
                        EstadoAgrotech.alertas_recientes_lista.length(),
                        " activas",
                        color_scheme="red",
                        variant="soft",
                        size="2",
                    ),
                    rx.badge("0 activas", color_scheme="grass", variant="soft", size="2"),
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                tiene_alertas,
                rx.vstack(
                    rx.foreach(EstadoAgrotech.alertas_recientes_lista, item_alerta_reciente),
                    spacing="2",
                    width="100%",
                    max_height="260px",
                    overflow_y="auto",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("circle-check", size=28, color="var(--grass-9)"),
                        rx.text(
                            "Todas las parcelas están dentro de rango",
                            size="2",
                            weight="medium",
                            color="var(--gray-11)",
                        ),
                        align="center",
                        spacing="2",
                    ),
                    padding="2.5em 1em",
                    border_radius="12px",
                    background_color="var(--gray-3)",
                    border="1px solid var(--gray-4)",
                    width="100%",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        border=rx.cond(tiene_alertas, "1.5px solid var(--red-8)", "1px solid var(--gray-5)"),
        **ESTILO_TARJETA_BASE,
    )


def fila_lectura(fila: list[str]) -> rx.Component:
    unidad = rx.cond(
        fila[0].contains("temp"),
        " ºC",
        rx.cond(
            fila[0].contains("humedad"),
            " %",
            rx.cond(
                fila[0].contains("lux"),
                " lux",
                rx.cond(fila[0].contains("ph"), " pH", ""),
            ),
        ),
    )
    return rx.table.row(
        rx.table.row_header_cell(rx.badge(fila[0], color_scheme="blue", variant="soft")),
        rx.table.cell(rx.text(fila[1], size="2", color="var(--gray-11)")),
        rx.table.cell(rx.text(fila[2] + unidad, weight="bold", color=fila[3])),
        rx.table.cell(rx.badge(fila[4], color_scheme=fila[5], variant="soft")),
    )


def _barra_navegacion() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.icon(tag="leaf", color="var(--grass-9)", size=28),
            rx.heading("Catálogo Agrotech", size="5", color="var(--grass-11)", weight="bold"),
            align_items="center",
            spacing="3",
        ),
        rx.hstack(
            rx.color_mode.button(),
            rx.menu.root(
                rx.menu.trigger(
                    rx.hstack(
                        rx.avatar(
                            fallback=BaseState.usuario_actual[:1].upper(),
                            size="1",
                            color_scheme="grass",
                            variant="solid",
                        ),
                        rx.vstack(
                            rx.text(BaseState.usuario_actual, weight="bold", size="2", color="var(--gray-12)"),
                            rx.text(
                                rx.match(
                                    EstadoAgrotech.rol_usuario,
                                    ("administrador", "Administrador"),
                                    ("tecnico_agricola", "Técnico Agrícola"),
                                    "Usuario",
                                ),
                                size="1",
                                color="var(--grass-10)",
                            ),
                            spacing="0",
                            align_items="start",
                        ),
                        padding="0.35em 0.75em",
                        border_radius="12px",
                        background_color="var(--gray-3)",
                        border="1px solid var(--gray-5)",
                        align_items="center",
                        spacing="2",
                        cursor="pointer",
                        _hover={"background_color": "var(--gray-4)"},
                    )
                ),
                rx.menu.content(
                    rx.cond(
                        EstadoAgrotech.rol_usuario == "administrador",
                        rx.menu.item(
                            rx.icon("users", size=16),
                            "Gestión de usuarios",
                            on_click=rx.redirect("/gestor-usuarios"),
                        ),
                    ),
                    rx.cond(
                        EstadoAgrotech.puede_gestionar_parcelas,
                        rx.menu.item(
                            rx.icon("map-pin", size=16),
                            "Gestión de parcelas",
                            on_click=rx.redirect("/gestor-parcelas"),
                        ),
                    ),
                    rx.cond(
                        EstadoAgrotech.puede_gestionar_parcelas,
                        rx.menu.separator(),
                    ),
                    rx.menu.item(
                        rx.icon("log-out", size=16),
                        "Cerrar Sesión",
                        on_click=BaseState.cerrar_sesion,
                        color="red",
                    ),
                ),
            ),
            spacing="4",
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


# ==============================================================================
# 4. INTERFAZ PRINCIPAL DEL PANEL (/panel)
# ==============================================================================

def index() -> rx.Component:
    return rx.box(
        rx.html(ESTILOS_TEMA_GLOBAL),
        _barra_navegacion(),
        rx.vstack(
            # 1. CABECERA PRINCIPAL + BOTÓN OCULTO #btn-actualizar CONSERVADO
            rx.hstack(
                rx.vstack(
                    rx.heading("Tu campo, de un vistazo", size="8", weight="bold", color="var(--gray-12)"),
                    rx.text("Monitoriza tus parcelas, sensores y alertas en tiempo real.", size="3", color="var(--gray-11)"),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.select(
                        EstadoAgrotech.opciones_parcelas,
                        value=EstadoAgrotech.parcela_seleccionada,
                        on_change=EstadoAgrotech.set_parcela_seleccionada,
                        variant="surface",
                        size="3",
                    ),
                    rx.button(
                        "Actualizar Datos",
                        id="btn-actualizar",
                        on_click=EstadoAgrotech.obtener_datos,
                        display="none",
                    ),
                    wrap="wrap",
                    align="center",
                    spacing="3",
                ),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="4",
                margin_bottom="0.5em",
            ),

            # 2. FILA DE TARJETAS KPI SUPERIORES
            rx.grid(
                tarjeta_kpi_superior(
                    "Tª Ambiente",
                    EstadoAgrotech.temp_amb_val,
                    "ºC",
                    EstadoAgrotech.temp_amb_estado,
                    EstadoAgrotech.temp_amb_critico,
                    "thermometer",
                    "#66cdaa",
                    "temperaturaAmb",
                ),
                tarjeta_kpi_superior(
                    "Tª Suelo",
                    EstadoAgrotech.temp_suelo_val,
                    "ºC",
                    EstadoAgrotech.temp_suelo_estado,
                    EstadoAgrotech.temp_suelo_critico,
                    "sprout",
                    "#66cdaa",
                    "temperaturaSuelo",
                ),
                tarjeta_kpi_superior(
                    "Humedad del suelo",
                    EstadoAgrotech.humedad_val,
                    "%",
                    EstadoAgrotech.humedad_estado,
                    EstadoAgrotech.humedad_critico,
                    "droplets",
                    "#4dd0e1",
                    "humedadSuelo",
                ),
                tarjeta_kpi_superior(
                    "Luminosidad",
                    EstadoAgrotech.lux_val,
                    "lx",
                    EstadoAgrotech.lux_estado,
                    EstadoAgrotech.lux_critico,
                    "sun",
                    "#ffd54f",
                    "luminosidad",
                ),
                tarjeta_kpi_superior(
                    "pH del suelo",
                    EstadoAgrotech.ph_val,
                    "pH",
                    EstadoAgrotech.ph_estado,
                    EstadoAgrotech.ph_critico,
                    "flask-conical",
                    "#b39ddb",
                    "ph",
                ),
                columns=rx.breakpoints(initial="1", sm="2", md="3", lg="5"),
                spacing="4",
                width="100%",
            ),

            # 3. FILA CENTRAL: GRÁFICA ÚNICA + SENSORES
            rx.grid(
                tarjeta_evolucion_grafica(),
                tarjeta_sensores_derecha(),
                columns=rx.breakpoints(initial="1", lg="2"),
                grid_template_columns=rx.breakpoints(initial="1fr", lg="1.65fr 1fr"),
                spacing="5",
                width="100%",
            ),

            # 4. FILA INFERIOR: MIS PARCELAS + ALERTAS RECIENTES
            rx.grid(
                tarjeta_mis_parcelas(),
                tarjeta_alertas_recientes(),
                columns=rx.breakpoints(initial="1", lg="2"),
                grid_template_columns=rx.breakpoints(initial="1fr", lg="1.65fr 1fr"),
                spacing="5",
                width="100%",
            ),

            # 5. REGISTRO DE ÚLTIMAS LECTURAS
            rx.accordion.root(
                rx.accordion.item(
                    header="Ver registro detallado de últimas 15 lecturas",
                    content=rx.box(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("ID Sensor"),
                                    rx.table.column_header_cell("Fecha / Hora"),
                                    rx.table.column_header_cell("Valor"),
                                    rx.table.column_header_cell("Estado"),
                                )
                            ),
                            rx.table.body(rx.foreach(EstadoAgrotech.lecturas, fila_lectura)),
                            variant="surface",
                            size="2",
                            width="100%",
                        ),
                        width="100%",
                        overflow_x="auto",
                    ),
                ),
                type="single",
                collapsible=True,
                variant="surface",
                width="100%",
            ),

            width="100%",
            max_width="1240px",
            min_width="0",
            margin="0 auto",
            padding=["1.5em 1em", "2em 1.5em"],
            spacing="5",
        ),
        width="100%",
        min_height="100vh",
        overflow_x="clip",
        background_color="var(--gray-1)",
    )


# ==============================================================================
# 5. CONFIGURACIÓN DE LA APP Y REGISTRO DE RUTAS
# ==============================================================================
