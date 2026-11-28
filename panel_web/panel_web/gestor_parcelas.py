import asyncio
import sqlite3

import reflex as rx
import websockets

try:
    from components.parcelas_helpers import (
        detectar_icono_parcela,
        parsear_rango,
        poblar_datos_iniciales_parcela,
        registrar_sensores_parcela,
    )
    from login import BaseState
except ImportError:
    from .components.parcelas_helpers import (
        detectar_icono_parcela,
        parsear_rango,
        poblar_datos_iniciales_parcela,
        registrar_sensores_parcela,
    )
    from .login import BaseState

from funcs import PARCELAS_INICIALES, conectar_db, init_db


class GestorParcelasState(BaseState):
    _token_streaming: int = 0
    _ultimo_id_sensor: int = -1

    rol_usuario: str = ""
    parcelas_lista: list[list[str]] = []

    # Formulario de alta de nueva parcela
    nueva_nombre: str = ""
    nueva_ubicacion: str = ""
    nuevo_cultivo: str = ""

    nueva_temp_amb_min: str = "15.0"
    nueva_temp_amb_max: str = "32.0"
    nueva_temp_suelo_min: str = "12.0"
    nueva_temp_suelo_max: str = "28.0"
    nueva_ph_min: str = "5.5"
    nueva_ph_max: str = "7.5"
    nueva_lux_min: str = "200"
    nueva_lux_max: str = "50000"
    nueva_humedad_min: str = "40"
    nueva_humedad_max: str = "85"

    # Filtros de búsqueda
    filtro_busqueda: str = ""
    filtro_estado: str = "Todas"

    # Mensajes
    error_mensaje: str = ""
    exito_mensaje: str = ""

    # Modal de edición de rangos, mantenimiento y cuaderno
    modal_abierto: bool = False
    edit_id: str = ""
    edit_nombre: str = ""
    edit_ubicacion: str = ""
    edit_cultivo: str = ""
    edit_superficie: str = ""
    edit_en_mantenimiento: bool = False
    edit_notas: str = ""

    edit_temp_amb_min: str = ""
    edit_temp_amb_max: str = ""
    edit_temp_suelo_min: str = ""
    edit_temp_suelo_max: str = ""
    edit_ph_min: str = ""
    edit_ph_max: str = ""
    edit_lux_min: str = ""
    edit_lux_max: str = ""
    edit_humedad_min: str = ""
    edit_humedad_max: str = ""

    @rx.var
    def total_parcelas(self) -> int:
        return len(self.parcelas_lista)

    @rx.var
    def total_criticas(self) -> int:
        return sum(1 for p in self.parcelas_lista if len(p) > 11 and p[11] == "1")

    @rx.var
    def parcelas_filtradas(self) -> list[list[str]]:
        termino = self.filtro_busqueda.strip().lower()
        resultado: list[list[str]] = []
        for p in self.parcelas_lista:
            en_mant = p[5] == "1"
            es_crit = p[11] == "1"

            if self.filtro_estado == "Críticas" and not es_crit:
                continue
            elif self.filtro_estado == "En mantenimiento" and not en_mant:
                continue
            elif self.filtro_estado == "Operativas" and (en_mant or es_crit):
                continue

            if termino:
                bloque = f"{p[1]} {p[2]} {p[3]} {p[0]}".lower()
                if termino not in bloque:
                    continue
            resultado.append(p)
        return resultado

    def set_campo(self, campo: str, valor: str):
        setattr(self, campo, valor)

    def set_campo_bool(self, campo: str, valor: Any) ->None:
        setattr(self, campo, valor)

    def comprobar_acceso_parcelas(self):
        if self.usuario_actual == "":
            return rx.redirect("/")

        try:
            init_db()
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("SELECT role FROM users WHERE username = ?", (self.usuario_actual,))
                resultado = cursor.fetchone()
                if not resultado or resultado[0] not in ("administrador", "tecnico_agricola"):
                    return rx.redirect("/panel")
                self.rol_usuario = resultado[0]
        except sqlite3.Error:
            return rx.redirect("/panel")

        self.error_mensaje = ""
        self.exito_mensaje = ""
        self.cargar_parcelas()
        return GestorParcelasState.iniciar_streaming_parcelas

    async def _escuchar_websocket_parcela(self, pid: int, token: int):
        """Escucha el canal WebSocket de una parcela concreta y actualiza en tiempo real."""
        uri = f"ws://localhost:8001/ws/parcels/{pid}"
        while True:
            async with self:
                if self._token_streaming != token or self.usuario_actual == "":
                    return
                if not any(p[0] == str(pid) for p in self.parcelas_lista):
                    return

            try:
                async with websockets.connect(uri) as websocket:
                    while True:
                        async with self:
                            if self._token_streaming != token or self.usuario_actual == "":
                                return
                        await websocket.recv()
                        async with self:
                            if self._token_streaming != token:
                                return
                            self.cargar_parcelas()
            except asyncio.CancelledError:
                return
            except Exception:
                await asyncio.sleep(2.0)

    @rx.event(background=True)
    async def iniciar_streaming_parcelas(self):
        """Mantiene actualizadas las tarjetas en tiempo real mediante WebSockets y respaldo SQLite."""
        async with self:
            self._token_streaming += 1
            mi_token = self._token_streaming

        tareas_ws: dict[int, asyncio.Task] = {}

        try:
            while True:
                async with self:
                    if self._token_streaming != mi_token or self.usuario_actual == "":
                        break
                    ids_actuales = [int(p[0]) for p in self.parcelas_lista]

                for pid in ids_actuales:
                    if pid not in tareas_ws or tareas_ws[pid].done():
                        tareas_ws[pid] = asyncio.create_task(
                            self._escuchar_websocket_parcela(pid, mi_token)
                        )

                try:
                    with conectar_db() as conexion:
                        cursor = conexion.cursor()
                        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM sensor_data")
                        fila_max = cursor.fetchone()
                        max_id_actual = int(fila_max[0]) if fila_max else 0

                    async with self:
                        if self._token_streaming != mi_token:
                            break
                        if max_id_actual != self._ultimo_id_sensor:
                            self._ultimo_id_sensor = max_id_actual
                            self.cargar_parcelas()
                except sqlite3.Error:
                    pass

                await asyncio.sleep(1.5)
        finally:
            for tarea in tareas_ws.values():
                if not tarea.done():
                    tarea.cancel()

    def cargar_parcelas(self):
        try:
            init_db()
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    SELECT id, name, location,
                           COALESCE(crop, 'Sin especificar'),
                           COALESCE(area, '1.5 ha'),
                           COALESCE(en_mantenimiento, 0),
                           COALESCE(notes, ''),
                           COALESCE(temp_amb_min, 15.0),
                           COALESCE(temp_amb_max, 32.0),
                           COALESCE(temp_suelo_min, 12.0),
                           COALESCE(temp_suelo_max, 28.0),
                           COALESCE(ph_min, 5.5),
                           COALESCE(ph_max, 7.5),
                           COALESCE(lux_min, 200.0),
                           COALESCE(lux_max, 50000.0),
                           COALESCE(humedad_min, 40.0),
                           COALESCE(humedad_max, 85.0)
                    FROM parcels
                    ORDER BY id ASC
                """)
                filas = cursor.fetchall()

                if not filas:
                    cursor.executemany("""
                        INSERT INTO parcels (
                            name, location, crop, area, en_mantenimiento, notes,
                            temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                            ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, PARCELAS_INICIALES)
                    conexion.commit()
                    cursor.execute("""
                        SELECT id, name, location, crop, area, en_mantenimiento, notes,
                               temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                               ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
                        FROM parcels
                        ORDER BY id ASC
                    """)
                    filas = cursor.fetchall()

                # Asegura que toda parcela tenga sus 5 sensores dados de alta en 'sensors'
                for row in filas:
                    registrar_sensores_parcela(cursor, int(row[0]))
                conexion.commit()

                conteo_sensores: dict[int, int] = {}
                cursor.execute("SELECT parcel_id, COUNT(*) FROM sensors GROUP BY parcel_id")
                for p_id_reg, total_s in cursor.fetchall():
                    if p_id_reg is not None:
                        conteo_sensores[int(p_id_reg)] = int(total_s)

                ultimos_valores: dict[str, float] = {}
                cursor.execute("SELECT COALESCE(MAX(id), 0) FROM sensor_data")
                fila_max = cursor.fetchone()
                if fila_max:
                    self._ultimo_id_sensor = int(fila_max[0])

                cursor.execute("""
                    SELECT sensor_id, value FROM sensor_data
                    WHERE id IN (SELECT MAX(id) FROM sensor_data GROUP BY sensor_id)
                """)
                for sid, val in cursor.fetchall():
                    if sid and val is not None:
                        ultimos_valores[str(sid)] = float(val)

                lista_construida: list[list[str]] = []
                for row in filas:
                    pid = int(row[0])
                    nombre = str(row[1])
                    ubicacion = str(row[2]) if row[2] else "Sin sector"
                    cultivo = str(row[3]) if row[3] else "Sin especificar"
                    superficie = str(row[4]) if row[4] else "1.5 ha"
                    en_mant = int(row[5]) if row[5] is not None else 0
                    notas = str(row[6]) if row[6] else ""

                    t_amb_min, t_amb_max = float(row[7]), float(row[8])
                    t_sue_min, t_sue_max = float(row[9]), float(row[10])
                    ph_min, ph_max = float(row[11]), float(row[12])
                    lux_min, lux_max = float(row[13]), float(row[14])
                    hum_min, hum_max = float(row[15]), float(row[16])

                    v_t_amb = ultimos_valores.get(f"p{pid}_temp_amb")
                    v_t_sue = ultimos_valores.get(f"p{pid}_temp_suelo")
                    v_ph = ultimos_valores.get(f"p{pid}_ph")
                    v_lux = ultimos_valores.get(f"p{pid}_lux")
                    v_hum = ultimos_valores.get(f"p{pid}_humedad")

                    alertas: list[str] = []
                    crit_t_amb = "0"
                    crit_t_sue = "0"
                    crit_ph = "0"
                    crit_lux = "0"
                    crit_hum = "0"

                    if v_t_amb is not None:
                        if v_t_amb > t_amb_max:
                            crit_t_amb = "1"
                            alertas.append(f"Tª Ambiente por encima del máximo ({round(v_t_amb, 1)} ºC / máx. {t_amb_max} ºC)")
                        elif v_t_amb < t_amb_min:
                            crit_t_amb = "1"
                            alertas.append(f"Tª Ambiente por debajo del mínimo ({round(v_t_amb, 1)} ºC / mín. {t_amb_min} ºC)")

                    if v_t_sue is not None:
                        if v_t_sue > t_sue_max:
                            crit_t_sue = "1"
                            alertas.append(f"Tª Suelo por encima del máximo ({round(v_t_sue, 1)} ºC / máx. {t_sue_max} ºC)")
                        elif v_t_sue < t_sue_min:
                            crit_t_sue = "1"
                            alertas.append(f"Tª Suelo por debajo del mínimo ({round(v_t_sue, 1)} ºC / mín. {t_sue_min} ºC)")

                    if v_ph is not None:
                        if v_ph > ph_max:
                            crit_ph = "1"
                            alertas.append(f"pH por encima del máximo ({round(v_ph, 2)} / máx. {ph_max})")
                        elif v_ph < ph_min:
                            crit_ph = "1"
                            alertas.append(f"pH por debajo del mínimo ({round(v_ph, 2)} / mín. {ph_min})")

                    if v_lux is not None:
                        if v_lux > lux_max:
                            crit_lux = "1"
                            alertas.append(f"Luminosidad por encima del máximo ({int(round(v_lux))} lux / máx. {int(lux_max)} lux)")
                        elif v_lux < lux_min:
                            crit_lux = "1"
                            alertas.append(f"Luminosidad por debajo del mínimo ({int(round(v_lux))} lux / mín. {int(lux_min)} lux)")

                    if v_hum is not None:
                        if v_hum > hum_max:
                            crit_hum = "1"
                            alertas.append(f"Humedad por encima del máximo ({round(v_hum, 1)}% / máx. {hum_max}%)")
                        elif v_hum < hum_min:
                            crit_hum = "1"
                            alertas.append(f"Humedad por debajo del mínimo ({round(v_hum, 1)}% / mín. {hum_min}%)")

                    n_sens = conteo_sensores.get(pid, 5)
                    sens_str = f"{n_sens} sensores" if n_sens != 1 else "1 sensor"

                    lista_construida.append([
                        str(pid),
                        nombre,
                        ubicacion,
                        cultivo,
                        superficie,
                        "1" if en_mant == 1 else "0",
                        notas,
                        f"{round(v_t_amb, 1)} ºC" if v_t_amb is not None else "-- ºC",
                        f"{int(round(v_hum))} %" if v_hum is not None else "-- %",
                        sens_str,
                        detectar_icono_parcela(nombre, cultivo),
                        "1" if len(alertas) > 0 else "0",
                        "\n".join(alertas),
                        str(t_amb_min),
                        str(t_amb_max),
                        str(t_sue_min),
                        str(t_sue_max),
                        str(ph_min),
                        str(ph_max),
                        str(lux_min),
                        str(lux_max),
                        str(hum_min),
                        str(hum_max),
                        f"{round(v_t_sue, 1)} ºC" if v_t_sue is not None else "-- ºC",
                        f"{round(v_ph, 2)} pH" if v_ph is not None else "-- pH",
                        f"{int(round(v_lux))} lux" if v_lux is not None else "-- lux",
                        crit_t_amb,
                        crit_t_sue,
                        crit_ph,
                        crit_lux,
                        crit_hum,
                    ])

                self.parcelas_lista = lista_construida
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al cargar parcelas: {e}"

    def anadir_parcela(self):
        self.error_mensaje = ""
        self.exito_mensaje = ""

        nombre = self.nueva_nombre.strip()
        ubicacion = self.nueva_ubicacion.strip()
        cultivo = self.nuevo_cultivo.strip() or "Sin especificar"

        if not nombre or not ubicacion:
            self.error_mensaje = "Indica el nombre de la parcela y su ubicación o sector."
            return

        try:
            t_amb_min, t_amb_max = parsear_rango(self.nueva_temp_amb_min, self.nueva_temp_amb_max, "Temperatura ambiental")
            t_sue_min, t_sue_max = parsear_rango(self.nueva_temp_suelo_min, self.nueva_temp_suelo_max, "Temperatura del suelo")
            ph_min, ph_max = parsear_rango(self.nueva_ph_min, self.nueva_ph_max, "pH")
            lux_min, lux_max = parsear_rango(self.nueva_lux_min, self.nueva_lux_max, "Luminosidad")
            hum_min, hum_max = parsear_rango(self.nueva_humedad_min, self.nueva_humedad_max, "Humedad")
        except ValueError as err:
            self.error_mensaje = str(err)
            return

        try:
            init_db()
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    INSERT INTO parcels (
                        name, location, crop, area, en_mantenimiento, notes,
                        temp_amb_min, temp_amb_max, temp_suelo_min, temp_suelo_max,
                        ph_min, ph_max, lux_min, lux_max, humedad_min, humedad_max
                    ) VALUES (?, ?, ?, ?, 0, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nombre, ubicacion, cultivo, "1.5 ha",
                    t_amb_min, t_amb_max, t_sue_min, t_sue_max,
                    ph_min, ph_max, lux_min, lux_max, hum_min, hum_max
                ))
                nueva_id = int(cursor.lastrowid)

                registrar_sensores_parcela(cursor, nueva_id)

                rangos_parcela = {
                    "temp_amb": (t_amb_min, t_amb_max),
                    "temp_suelo": (t_sue_min, t_sue_max),
                    "ph": (ph_min, ph_max),
                    "lux": (lux_min, lux_max),
                    "humedad": (hum_min, hum_max),
                }
                poblar_datos_iniciales_parcela(cursor, nueva_id, rangos_parcela)
                conexion.commit()

            self.nueva_nombre = ""
            self.nueva_ubicacion = ""
            self.nuevo_cultivo = ""
            self.exito_mensaje = f"Parcela '{nombre}' (#{nueva_id}) creada con sus 5 sensores y lecturas iniciales."
            self.cargar_parcelas()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al añadir parcela: {e}"

    def cambiar_mantenimiento(self, parcela_id: str, activo: bool):
        self.error_mensaje = ""
        self.exito_mensaje = ""
        valor_db = 1 if activo else 0
        try:
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute(
                    "UPDATE parcels SET en_mantenimiento = ? WHERE id = ?",
                    (valor_db, int(parcela_id))
                )
                conexion.commit()
            self.cargar_parcelas()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al cambiar estado de mantenimiento: {e}"

    def abrir_ficha_parcela(self, parcela: list[str]):
        self.error_mensaje = ""
        self.exito_mensaje = ""
        self.edit_id = parcela[0]
        self.edit_nombre = parcela[1]
        self.edit_ubicacion = parcela[2]
        self.edit_cultivo = parcela[3]
        self.edit_superficie = parcela[4]
        self.edit_en_mantenimiento = parcela[5] == "1"
        self.edit_notas = parcela[6]

        self.edit_temp_amb_min = parcela[13]
        self.edit_temp_amb_max = parcela[14]
        self.edit_temp_suelo_min = parcela[15]
        self.edit_temp_suelo_max = parcela[16]
        self.edit_ph_min = parcela[17]
        self.edit_ph_max = parcela[18]
        self.edit_lux_min = parcela[19]
        self.edit_lux_max = parcela[20]
        self.edit_humedad_min = parcela[21]
        self.edit_humedad_max = parcela[22]

        self.modal_abierto = True

    def guardar_ficha_parcela(self):
        if not self.edit_nombre.strip() or not self.edit_ubicacion.strip():
            self.error_mensaje = "El nombre y la ubicación no pueden quedar vacíos."
            return

        try:
            t_amb_min, t_amb_max = parsear_rango(self.edit_temp_amb_min, self.edit_temp_amb_max, "Temperatura ambiental")
            t_sue_min, t_sue_max = parsear_rango(self.edit_temp_suelo_min, self.edit_temp_suelo_max, "Temperatura del suelo")
            ph_min, ph_max = parsear_rango(self.edit_ph_min, self.edit_ph_max, "pH")
            lux_min, lux_max = parsear_rango(self.edit_lux_min, self.edit_lux_max, "Luminosidad")
            hum_min, hum_max = parsear_rango(self.edit_humedad_min, self.edit_humedad_max, "Humedad")
        except ValueError as err:
            self.error_mensaje = str(err)
            return

        try:
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("""
                    UPDATE parcels
                    SET name = ?, location = ?, crop = ?, area = ?,
                        en_mantenimiento = ?, notes = ?,
                        temp_amb_min = ?, temp_amb_max = ?,
                        temp_suelo_min = ?, temp_suelo_max = ?,
                        ph_min = ?, ph_max = ?,
                        lux_min = ?, lux_max = ?,
                        humedad_min = ?, humedad_max = ?
                    WHERE id = ?
                """, (
                    self.edit_nombre.strip(),
                    self.edit_ubicacion.strip(),
                    self.edit_cultivo.strip() or "Sin especificar",
                    self.edit_superficie.strip() or "1.5 ha",
                    1 if self.edit_en_mantenimiento else 0,
                    self.edit_notas.strip(),
                    t_amb_min, t_amb_max,
                    t_sue_min, t_sue_max,
                    ph_min, ph_max,
                    lux_min, lux_max,
                    hum_min, hum_max,
                    int(self.edit_id)
                ))
                conexion.commit()

            self.modal_abierto = False
            self.exito_mensaje = f"Rangos y ficha de '{self.edit_nombre}' actualizados."
            self.cargar_parcelas()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al actualizar parcela: {e}"

    def eliminar_parcela_actual(self):
        try:
            pid = int(self.edit_id)
            with conectar_db() as conexion:
                cursor = conexion.cursor()
                cursor.execute("DELETE FROM parcels WHERE id = ?", (pid,))
                cursor.execute("DELETE FROM sensors WHERE parcel_id = ?", (pid,))
                cursor.execute("DELETE FROM sensor_data WHERE sensor_id LIKE ?", (f"p{pid}_%",))
                conexion.commit()

            self.modal_abierto = False
            self.exito_mensaje = f"Parcela '{self.edit_nombre}' y sus sensores eliminados."
            self.cargar_parcelas()
        except sqlite3.Error as e:
            self.error_mensaje = f"Error al eliminar parcela: {e}"


