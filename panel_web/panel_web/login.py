import reflex as rx   
import sqlite3   
import os   
import hashlib   
   
DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))   
RUTA_DB = os.path.join(DIR_ACTUAL, "..", "..", "agrotech.db")   
   
# 1. ESTADO GLOBAL   
class BaseState(rx.State):   
    usuario_actual: str = rx.LocalStorage("")   
   
    def cerrar_sesion(self):   
        self.usuario_actual = ""   
        return rx.redirect("/")   
   
# 2. ESTADO DEL LOGIN
class LoginState(BaseState):   
    usuario: str = ""   
    contrasena: str = ""   
    error_mensaje: str = ""   
    mostrar_contrasena: bool = False 
  
    def limpiar_campos(self):
        self.error_mensaje = ""  
        self.usuario = ""
        self.contrasena = ""
        self.mostrar_contrasena = False

    def cambiar_visibilidad(self):
        self.mostrar_contrasena = not self.mostrar_contrasena
  
    def set_usuario(self, valor: str):   
        self.usuario = valor   
   
    def set_contrasena(self, valor: str):   
        self.contrasena = valor   
   
    def validar_login(self):   
        self.error_mensaje = ""   
            
        if not self.usuario or not self.contrasena:   
            self.error_mensaje = "Por favor, rellena todos los campos."   
            return   
   
        try:   
            with sqlite3.connect(RUTA_DB) as conexion:   
                cursor = conexion.cursor()   
                  
                cursor.execute("""   
                    CREATE TABLE IF NOT EXISTS users (   
                        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT   
                    )   
                """)   
                  
                cursor.execute("SELECT id FROM users WHERE username = 'admin'")
                if not cursor.fetchone():
                    admin_hash = hashlib.sha256("admin123".encode('utf-8')).hexdigest()   
                    cursor.execute(  
                        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",   
                        ('admin', admin_hash, 'administrador')  
                    )   
                conexion.commit()   
   
                pass_hash = hashlib.sha256(self.contrasena.encode('utf-8')).hexdigest()  
   
                cursor.execute(   
                    "SELECT id FROM users WHERE username = ? AND password_hash = ?",     
                    (self.usuario, pass_hash)   
                )   
                    
                if cursor.fetchone():   
                    self.usuario_actual = self.usuario     
                    self.limpiar_campos()
                    return rx.redirect("/panel")     
                else:   
                    self.error_mensaje = "Usuario o contraseña incorrectos."   
                        
        except sqlite3.Error as e:   
            self.error_mensaje = f"Error de base de datos: {e}"   
   
# 3. INTERFAZ    
def login_page() -> rx.Component:   
    return rx.box(   
        # INYECCIÓN DE LA NUEVA PALETA DE COLORES DEL PANEL_WEB
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
                    --gray-6: #24657D !important;
                    --gray-11: #8FB4C2 !important;
                    --gray-12: #E2F1F5 !important;
                }

                /* Aplicar color dinámico a los inputs (el placeholder en un tono más suave) */
                html body .rt-TextFieldRoot .rt-TextFieldInput::placeholder,
                html body .rt-TextFieldInput::placeholder {
                    color: var(--gray-11) !important;
                    -webkit-text-fill-color: var(--gray-11) !important;
                    opacity: 1 !important;
                }
                html body .rt-TextFieldRoot .rt-TextFieldInput,
                html body .rt-TextFieldInput {
                    color: var(--gray-12) !important;
                    -webkit-text-fill-color: var(--gray-12) !important;
                }
            </style>
        """),
        
        # --- BOTÓN MODO OSCURO/CLARO FLOTANTE ---
        rx.box(
            rx.color_mode.button(),
            position="absolute",
            top="1.5em",
            right="1.5em",
            z_index="10"
        ),
        
        rx.center(   
            rx.card(   
                rx.vstack(   
                    # --- CABECERA ---
                    rx.center(   
                        rx.icon(tag="lock", size=40, color="var(--grass-9)"),  
                        rx.heading("Acceso Agrotech", size="6", margin_top="1em", color="var(--gray-12)"),  
                        margin_bottom="1em",    
                        width="100%"    
                    ),    
                    
                    # --- BARRA DE USUARIO ---
                    rx.text("Usuario", weight="bold", size="2", color="var(--gray-12)"),    
                    rx.input(
                        rx.input.slot(rx.icon("user", size=18, color="var(--gray-11)")),
                        value=LoginState.usuario, 
                        placeholder="Introduce tu usuario...", 
                        on_change=LoginState.set_usuario, 
                        width="100%",
                        size="3",
                        variant="surface",
                        border="1px solid var(--gray-5)",
                        background_color="var(--gray-1)"
                    ),    
                    
                    # --- BARRA DE CONTRASEÑA ---
                    rx.text("Contraseña", weight="bold", size="2", margin_top="1em", color="var(--gray-12)"),    
                    rx.input(
                        rx.input.slot(rx.icon("lock", size=18, color="var(--gray-11)")),
                        rx.input.slot(
                            rx.icon(
                                tag=rx.cond(LoginState.mostrar_contrasena, "eye-off", "eye"),
                                cursor="pointer",
                                on_click=LoginState.cambiar_visibilidad,
                                color="var(--gray-11)",
                                _hover={"color": "var(--grass-9)"}
                            )
                        ),
                        value=LoginState.contrasena, 
                        type=rx.cond(LoginState.mostrar_contrasena, "text", "password"), 
                        placeholder="••••••••", 
                        on_change=LoginState.set_contrasena, 
                        width="100%",
                        size="3",
                        variant="surface",
                        border="1px solid var(--gray-5)",
                        background_color="var(--gray-1)"
                    ),
                        
                    # --- MENSAJES DE ALERTA ---
                    rx.cond(   
                        LoginState.error_mensaje != "",   
                        rx.callout.root(   
                            rx.callout.icon("alert-triangle"),   
                            rx.callout.text(LoginState.error_mensaje),   
                            color_scheme="red", role="alert", margin_top="1em", width="100%"   
                        )   
                    ),   
                        
                    # --- BOTÓN DE ACCIÓN PRINCIPAL ---
                    rx.button("Entrar", on_click=LoginState.validar_login, color_scheme="grass", width="100%", margin_top="2em", size="3"),  
                      
                    width="100%", align_items="start", padding="2em"    
                ),    
                width=["90%", "400px"], 
                box_shadow="0 8px 24px rgba(0,0,0,0.08)", 
                border_radius="16px",
                border="1px solid var(--gray-5)",
                background_color="var(--gray-2)"
            ),    
            width="100%", 
            height="100vh", 
            background_color="var(--gray-1)"    
        )    
    )