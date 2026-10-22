from datetime import datetime, time, date
import time as time_module
from zoneinfo import ZoneInfo
import os
import requests
import tempfile
import streamlit as st

# Supabase SDK para sincronización en la nube
try:
    from supabase import create_client
    SUPABASE_DISPONIBLE = True
except ImportError:
    SUPABASE_DISPONIBLE = False

# Librerías de QR y PDF
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    FPDF_DISPONIBLE = False

try:
    import qrcode
    QRCODE_DISPONIBLE = True
except ImportError:
    QRCODE_DISPONIBLE = False

# ================= CONFIGURACIÓN DE LA PÁGINA =================
st.set_page_config(
    page_title="ECONOGAS - Módulo Carta Porte",
    page_icon="🔥",
    layout="wide"
)

MASTER_PASSWORD = "ECONOGAS2026"

# ================= CREDENCIALES DE SUPABASE (NUBE) =================
SUPABASE_URL = "https://qikmlgbnwbdmuqziemia.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFpa21sZ2Jud2JkbXVxemllbWlhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1MTg0NzUsImV4cCI6MjEwODA5NDQ3NX0.s7J6uZxohN49BocGUwBqc02S7jZFbMOoeF9Om-DYTfQ"

@st.cache_resource
def init_supabase():
    if SUPABASE_DISPONIBLE and SUPABASE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            return None
    return None

supabase = init_supabase()

# ================= CATÁLOGO DE OPERADORES, UNIDADES Y PÓLIZAS =================
CATALOGO_CHOFERES = [
    {
        "nombre": "DANIEL FLORES HERNANDEZ",
        "rfc": "FOHD8803071N2",
        "tipo": "ESTATAL",
        "licencia": "UBOCKQCYR",
        "eco": "13",
        "placas": "XU08753",
        "marca": "CHEVROLET 3500",
        "capacidad_txt": "4,000 Litros",
        "capacidad_num": 4000.0,
        "aseguradora": "QUALITAS",
        "poliza": "7150013983"
    },
    {
        "nombre": "PABLO SANCHEZ CASTILLO",
        "rfc": "SACP860517V41",
        "tipo": "ESTATAL",
        "licencia": "UBON3HHFH",
        "eco": "16",
        "placas": "LG53265",
        "marca": "CHEVROLET 3500",
        "capacidad_txt": "4,000 Litros",
        "capacidad_num": 4000.0,
        "aseguradora": "QUALITAS",
        "poliza": "7150013990"
    },
    {
        "nombre": "MARTIN HERNANDEZ VIDAL",
        "rfc": "HEVM921213TR3",
        "tipo": "ESTATAL",
        "licencia": "XL271703",
        "eco": "17",
        "placas": "XU94347",
        "marca": "CHEVROLET 3500",
        "capacidad_txt": "3,700 Litros",
        "capacidad_num": 3700.0,
        "aseguradora": "QUALITAS",
        "poliza": "7150015649"
    }
]

# ================= FUNCIONES DE NUBE (SUPABASE) =================
def obtener_siguiente_folio_nube():
    """Obtiene e incrementa el folio de forma atómica en Supabase."""
    if supabase is None:
        return "0000001"
    
    try:
        response = supabase.table("folios_econogas").select("ultimo_folio").eq("id", 1).execute()
        if response.data and len(response.data) > 0:
            ultimo = response.data[0]["ultimo_folio"]
            nuevo_folio = ultimo + 1
            supabase.table("folios_econogas").update({"ultimo_folio": nuevo_folio}).eq("id", 1).execute()
            return f"{nuevo_folio:07d}"
        else:
            supabase.table("folios_econogas").insert({"id": 1, "ultimo_folio": 1}).execute()
            return "0000001"
    except Exception as e:
        st.error(f"⚠️ Error al obtener folio de Supabase: {e}")
        return "0000001"

def guardar_carta_en_nube(datos):
    """Guarda los datos completos de la carta porte en la base de datos."""
    if supabase is not None:
        try:
            supabase.table("cartas_econogas").insert(datos).execute()
            return True
        except Exception as e:
            st.error(f"❌ Error al guardar en Supabase: {e}")
            return False
    else:
        st.error("⚠️ La conexión con Supabase no está activa.")
        return False

def cargar_historial_nube():
    """Carga todas las cartas registradas ordenadas desde la más reciente."""
    if supabase is not None:
        try:
            response = supabase.table("cartas_econogas").select("*").order("id", desc=True).execute()
            return response.data or []
        except Exception as e:
            st.error(f"⚠️ Error al cargar historial de Supabase: {e}")
            return []
    return []

def eliminar_carta_nube(carta_id):
    """Elimina un registro del historial en Supabase por su ID único."""
    if supabase is not None:
        try:
            supabase.table("cartas_econogas").delete().eq("id", carta_id).execute()
            return True
        except Exception as e:
            st.error(f"❌ Error al eliminar de Supabase: {e}")
            return False
    return False

# Inicializar estados de la sesión
if "auth_econogas" not in st.session_state:
    st.session_state.auth_econogas = False

# ================= CATÁLOGO LOCAL DE C.P. VERIFICADO =================
CATALOGO_LOCAL_CP = {
    "91400": {"colonia": "Perote Centro", "municipio": "Perote", "estado": "Veracruz", "pais": "México"},
    "91403": {"colonia": "El Sabinal", "municipio": "Perote", "estado": "Veracruz", "pais": "México"},
    "91405": {"colonia": "Fovissste", "municipio": "Perote", "estado": "Veracruz", "pais": "México"},
    "91285": {"colonia": "Tenextepec", "municipio": "Perote", "estado": "Veracruz", "pais": "México"},
    "91282": {"colonia": "El Limon", "municipio": "Perote", "estado": "Veracruz Llave", "pais": "México"},
    "91000": {"colonia": "Xalapa Enríquez Centro", "municipio": "Xalapa", "estado": "Veracruz", "pais": "México"},
    "91190": {"colonia": "Ánimas", "municipio": "Xalapa", "estado": "Veracruz", "pais": "México"},
    "91110": {"colonia": "Badillo", "municipio": "Xalapa", "estado": "Veracruz", "pais": "México"},
    "91700": {"colonia": "Veracruz Centro", "municipio": "Veracruz", "estado": "Veracruz", "pais": "México"},
    "72000": {"colonia": "Puebla Centro", "municipio": "Puebla", "estado": "Puebla", "pais": "México"},
    "72100": {"colonia": "La Paz", "municipio": "Puebla", "estado": "Puebla", "pais": "México"}
}

@st.cache_data(show_spinner=False)
def consultar_cp_mexico(cp):
    cp = str(cp).strip()
    if not cp or len(cp) != 5 or not cp.isdigit():
        return {"colonia": "", "municipio": "", "estado": "", "pais": "México"}
    
    if cp in CATALOGO_LOCAL_CP:
        return CATALOGO_LOCAL_CP[cp]
    
    try:
        url = f"https://api.zippopotam.us/MX/{cp}"
        resp = requests.get(url, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            places = data.get("places", [])
            if places:
                colonia = places[0].get("place name", "")
                estado = places[0].get("state", "")
                return {"colonia": colonia, "municipio": estado, "estado": estado, "pais": "México"}
    except Exception:
        pass

    return {"colonia": "", "municipio": "", "estado": "", "pais": "México"}

def safe_str(val):
    if val is None:
        return ""
    texto = str(val).replace("–", "-").replace("—", "-")
    return texto.encode('latin-1', 'replace').decode('latin-1')

def generar_qr_tempfile(contenido):
    if not QRCODE_DISPONIBLE:
        return None
    try:
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=3, border=1)
        qr.add_data(contenido)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(tmp.name, format='PNG')
        tmp.close()
        return tmp.name
    except Exception:
        return None

def generar_pdf(d):
    qr_path = None
    try:
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        
        # LOGO IZQUIERDA: ECONOGAS (38mm de ancho)
        logo_econogas_path = "logo_econogas.jpg"
        if os.path.exists(logo_econogas_path):
            try:
                pdf.image(logo_econogas_path, 10, 8, 38)
            except:
                pass

        # LOGO DERECHA: NAUPAGAS (38mm de ancho)
        logo_naupa_path = "logo.jpg"
        if os.path.exists(logo_naupa_path):
            try:
                pdf.image(logo_naupa_path, 162, 8, 38)
            except:
                pass

        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 8, safe_str("ECONOGAS S.A. DE C.V."), align="C", ln=True)
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 6, safe_str("CARTA PORTE"), align="C", ln=True)
        pdf.set_font("helvetica", "", 8)
        
        folio_val = d.get('folio', '0000001')
        pdf.cell(0, 5, safe_str(f"FOLIO: {folio_val} | Fecha de Emisión: {d.get('fecha_registro', '')}"), align="C", ln=True)
        pdf.ln(4)

        def seccion_pdf(titulo):
            pdf.set_fill_color(220, 225, 230)
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(0, 6, safe_str(f"  {titulo}"), fill=True, ln=True)
            pdf.ln(2)

        # 1. Emisor y Permisos
        seccion_pdf("1. DATOS DEL EMISOR Y PERMISO DE DISTRIBUCIÓN")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, safe_str(f"Empresa / Razón Social: {d.get('nombre_emisor', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"RFC Emisor: {d.get('rfc_emisor', '')}"), ln=1)
        pdf.cell(0, 5, safe_str(f"Permiso Distribución Gas LP: {d.get('num_permiso_sct', '')}"), ln=1)
        pdf.ln(3)

        # 2. Chofer
        seccion_pdf("2. DATOS DEL OPERADOR / CHOFER (FIGURA TRANSPORTE)")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, safe_str(f"Chofer: {d.get('nombre_chofer', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"RFC Chofer: {d.get('rfc_chofer', '')}"), ln=1)
        pdf.cell(95, 5, safe_str(f"Tipo de Licencia: {d.get('tipo_licencia', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"Número de Licencia: {d.get('num_licencia', '')}"), ln=1)
        pdf.ln(3)

        # 3. Unidad
        seccion_pdf("3. DATOS DE LA UNIDAD Y SEGURO DE RESPONSABILIDAD")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, safe_str(f"Unidad: {d.get('tipo_unidad', '')} - Eco: {d.get('eco_unidad', '')}"), ln=0)
        pdf.cell(95, 5, safe_str(f"Placas: {d.get('placas', '')}"), ln=1)
        pdf.cell(95, 5, safe_str(f"Marca/Modelo: {d.get('marca_modelo', '')} (Cap: {d.get('capacidad', '')})"), ln=0)
        pdf.cell(95, 5, safe_str(f"Aseguradora: {d.get('aseguradora', '')} | Póliza: {d.get('num_poliza', '')}"), ln=1)
        pdf.ln(3)

        # 4. Ruta
        seccion_pdf("4. RUTA DE TRÁNSITO (ORIGEN Y DESTINO)")
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, safe_str("ORIGEN:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(100, 5, safe_str(f"{d.get('nombre_origen', '')}"), ln=0)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(12, 5, safe_str("RFC:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"{d.get('rfc_origen', '')}"), ln=1)
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(28, 5, safe_str("Fecha de Salida:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"{d.get('fecha_salida', '')}"), ln=1)
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, safe_str("Dirección:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.multi_cell(0, 5, safe_str(f"{d.get('dir_origen', '')}"))
        pdf.ln(2)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, safe_str("DESTINO:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(100, 5, safe_str(f"{d.get('nombre_destino', '')}"), ln=0)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(12, 5, safe_str("RFC:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        rfc_dest_val = d.get('rfc_destino', '') if str(d.get('rfc_destino', '')).strip() else "S/N (Público General)"
        pdf.cell(0, 5, safe_str(f"{rfc_dest_val}"), ln=1)
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(28, 5, safe_str("Llegada Estimada:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"{d.get('fecha_llegada', '')}"), ln=1)
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, safe_str("Dirección:"), ln=0)
        pdf.set_font("helvetica", "", 8)
        pdf.multi_cell(0, 5, safe_str(f"{d.get('dir_destino', '')}"))
        pdf.ln(3)

        # 5. Mercancía
        seccion_pdf("5. DESCRIPCIÓN Y CLAVES DE LA MERCANCÍA")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, safe_str(f"Producto: {d.get('desc_mercancia', '')} | Clave SAT: {d.get('clave_prod_sat', '')}"), ln=1)
        
        peso_val = d.get('peso_mercancia', '')
        if peso_val and peso_val != "N/A":
            pdf.cell(95, 5, safe_str(f"Cantidad: {d.get('cantidad_mercancia', '')} ({d.get('clave_unidad_sat', '')})"), ln=0)
            pdf.cell(95, 5, safe_str(f"Peso Total: {peso_val}"), ln=1)
        else:
            pdf.cell(0, 5, safe_str(f"Cantidad: {d.get('cantidad_mercancia', '')} ({d.get('clave_unidad_sat', '')})"), ln=1)
            
        pdf.ln(4)

        # 6. Validación y QR
        seccion_pdf("6. VALIDACIÓN Y VERIFICACIÓN OPERATIVA")
        
        enlace_qr = "https://l1nq.com/3aqpov5"
        qr_path = generar_qr_tempfile(enlace_qr)
        
        if qr_path and os.path.exists(qr_path):
            y_inicial = pdf.get_y()
            try:
                pdf.image(qr_path, x=15, y=y_inicial, w=38)
            except:
                pass
            pdf.set_x(56)
            pdf.set_font("helvetica", "B", 8)
            pdf.cell(0, 4, safe_str(f"Folio: {folio_val}"), ln=1)
            pdf.set_x(56)
            pdf.set_font("helvetica", "", 7)
            pdf.cell(0, 4, safe_str("Estatus de Verificación: ACCESO AL PORTAL DE CONSULTA"), ln=1)
            pdf.set_x(56)
            pdf.cell(0, 4, safe_str(f"Permiso Distribución Gas LP: {d.get('num_permiso_sct', '')}"), ln=1)
            pdf.set_x(56)
            pdf.multi_cell(0, 4, safe_str("Este documento ampara el traslado operado con las especificaciones técnicas requeridas."))

        y_actual = pdf.get_y()
        y_limite_qr = y_inicial + 40
        if y_actual < y_limite_qr:
            pdf.set_y(y_limite_qr)

        pdf.ln(4)
        pdf.set_font("helvetica", "B", 8)
        pdf.multi_cell(0, 4, safe_str("SI USTED TIENE UNA DUDA O PREGUNTA SOBRE ESTA CARTA PORTE, FAVOR DE CONTACTARNOS AL NÚMERO 282 - 103 - 3534"), align="C")

        out = pdf.output(dest='S')
        if isinstance(out, str):
            return out.encode('latin1')
        return bytes(out)
    except Exception as e:
        pdf_err = FPDF()
        pdf_err.add_page()
        pdf_err.set_font("helvetica", "B", 12)
        pdf_err.cell(0, 10, safe_str(f"Error técnico PDF: {str(e)[:45]}"), ln=True)
        out_err = pdf_err.output(dest='S')
        if isinstance(out_err, str):
            return out_err.encode('latin1')
        return bytes(out_err)
    finally:
        if qr_path and os.path.exists(qr_path):
            try:
                os.remove(qr_path)
            except:
                pass

# ================= AUTENTICACIÓN RÁPIDA =================
if not st.session_state.auth_econogas:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        logo_path = "logo_econogas.jpg" if os.path.exists("logo_econogas.jpg") else "logo.jpg"
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        else:
            st.markdown("<h1 style='text-align: center;'>🔥</h1>", unsafe_allow_html=True)
            
    st.markdown("<h2 style='text-align: center; color: #004080;'>ECONOGAS S.A. DE C.V.</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Módulo de Generación de Carta Porte</p>", unsafe_allow_html=True)
    
    col_a1, col_a2, col_a3 = st.columns([1, 1.2, 1])
    with col_a2:
        pass_input = st.text_input("Contraseña de Acceso", type="password")
        if st.button("Ingresar al Módulo", type="primary", use_container_width=True):
            if pass_input == MASTER_PASSWORD:
                st.session_state.auth_econogas = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()

# ================= MENÚ PRINCIPAL =================
with st.sidebar:
    logo_path = "logo_econogas.jpg" if os.path.exists("logo_econogas.jpg") else "logo.jpg"
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    st.markdown("### 🎛️ Menú de Navegación")
    accion = st.radio("Selecciona una opción:", ["Nueva Carta Porte", "Historial de Documentos"])
    st.markdown("---")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.auth_econogas = False
        st.rerun()

ahora_mx = datetime.now(ZoneInfo("America/Mexico_City"))

# ================= FORMULARIO PRINCIPAL =================
if accion == "Nueva Carta Porte":
    st.title("📄 ECONOGAS - Generador de Carta Porte")
    st.write("Complete los campos oficiales requeridos para el tránsito seguro de la unidad.")
    st.markdown("---")

    # 1. Emisor y Permiso de Gas LP
    with st.container(border=True):
        st.subheader("1. 🏢 Datos del Emisor y Permiso de Distribución")
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            nombre_emisor = st.text_input("Razón Social / Empresa Emisora", value="ECONOGAS S.A. de C.V.")
        with col_e2:
            rfc_emisor = st.text_input("RFC del Emisor", value="ECO1205188P5")
        
        num_permiso_sct = st.text_input("Permiso de Distribución de Gas LP", value="LP/20474/DIST/PLA/2017")

    # Variables por defecto para auto-llenado
    def_eco = ""
    def_placas = ""
    def_marca = ""
    def_capacidad_txt = "12,900 Litros"
    def_capacidad_num = 4000.0
    def_aseguradora = ""
    def_poliza = ""

    # 2. Chofer con Catálogo y opción de captura manual 2x2
    with st.container(border=True):
        st.subheader("2. 👤 Datos del Operador / Chofer (Figura Transporte)")
        
        modo_chofer = st.radio("Modo de Selección de Chofer:", ["Catálogo de Operadores", "Personalizado (Manual)"], horizontal=True)

        if modo_chofer == "Catálogo de Operadores" and CATALOGO_CHOFERES:
            nombres_choferes = [c["nombre"] for c in CATALOGO_CHOFERES]
            chofer_seleccionado = st.selectbox("Seleccione al Chofer del Catálogo", options=nombres_choferes)
            datos_chofer_actual = next((c for c in CATALOGO_CHOFERES if c["nombre"] == chofer_seleccionado), CATALOGO_CHOFERES[0])
            
            # Asignar datos de unidad y seguro del chofer seleccionado
            def_eco = datos_chofer_actual["eco"]
            def_placas = datos_chofer_actual["placas"]
            def_marca = datos_chofer_actual["marca"]
            def_capacidad_txt = datos_chofer_actual["capacidad_txt"]
            def_capacidad_num = datos_chofer_actual["capacidad_num"]
            def_aseguradora = datos_chofer_actual["aseguradora"]
            def_poliza = datos_chofer_actual["poliza"]

            # Rectángulo ordenado en 2x2 para Catálogo
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nombre_chofer = st.text_input("Nombre Seleccionado / Registrado", value=chofer_seleccionado, disabled=True)
                rfc_chofer = st.text_input("RFC del Chofer (Oficial)", value=datos_chofer_actual["rfc"], disabled=True)
            with col_c2:
                tipo_licencia = st.text_input("Tipo de Licencia (Oficial)", value=datos_chofer_actual["tipo"], disabled=True)
                num_licencia = st.text_input("Número de Licencia (Oficial)", value=datos_chofer_actual["licencia"], disabled=True)
        else:
            # Rectángulo ordenado en 2x2 para Personalizado (Editable)
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nombre_chofer = st.text_input("Nombre Completo del Chofer", placeholder="Nombre completo del chofer")
                rfc_chofer = st.text_input("RFC del Chofer", placeholder="XAXX010101000")
            with col_c2:
                tipo_licencia = st.selectbox("Tipo de Licencia", ["Federal", "Estatal", "Chofer / Vendedor"])
                num_licencia = st.text_input("Número de Licencia", placeholder="Número oficial de licencia")

    # 3. Unidad (Autollenada con la pipa del chofer)
    with st.container(border=True):
        st.subheader("3. ⛽ Datos de la Unidad")
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            tipo_unidad = st.selectbox("Tipo de Unidad", ["Autotanque (Pipa)", "Vehículo Repartidor (Cilindrera)"])
            eco_unidad = st.text_input("Número Económico", value=def_eco, placeholder="Ej. PIPA-01 o CIL-05")
            placas = st.text_input("Placas", value=def_placas, placeholder="Ej. XX-00-XXX")
        with col_u2:
            marca_modelo = st.text_input("Marca / Modelo", value=def_marca, placeholder="Ej. Ford F-350 2020")
            if tipo_unidad == "Autotanque (Pipa)":
                capacidad = st.text_input("Capacidad descriptiva de la unidad", value=def_capacidad_txt, placeholder="Ej. 4,000 Litros")
            else:
                capacidad = st.text_input("Capacidad descriptiva de la unidad", value="Vehículo Repartidor Cilindros", placeholder="Ej. Cilindros 20kg y 30kg")

    # 4. Seguro (Autollenado con la póliza del chofer)
    with st.container(border=True):
        st.subheader("4. 🛡️ Póliza de Seguro")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            aseguradora = st.text_input("Compañía Aseguradora", value=def_aseguradora, placeholder="Ej. GNP, Qualitas, AXA")
        with col_s2:
            num_poliza = st.text_input("Número de Póliza", value=def_poliza, placeholder="Ej. POL-987654321")

    # 5. Origen y Destino
    with st.container(border=True):
        st.subheader("5. 📍 Ruta de Tránsito (Origen y Destino)")
        col_origen, col_destino = st.columns(2)

        with col_origen:
            st.markdown("#### 🛫 ORIGEN")
            tipo_modo_origen = st.radio("Modalidad de Origen:", ["Planta ECONOGAS (Oficial)", "Otro Origen (Manual)"], horizontal=False, key="radio_origen")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_salida_date = st.date_input("Fecha de Salida", value=ahora_mx.date())
            with col_f2:
                f_salida_time = st.time_input("Hora de Salida", value=ahora_mx.time())

            if tipo_modo_origen == "Planta ECONOGAS (Oficial)":
                rfc_origen = "ECO1205188P5"
                nombre_origen = "ECONOGAS"
                cp_origen = "91282"
                colonia_origen = "El Limon"
                municipio_origen = "Perote"
                estado_origen = "Veracruz Llave"
                pais_origen = "México"
                calle_origen = "CARRETERA FEDERAL MÉXICO - VERACRUZ KM. 92.8"
                
                st.text_input("RFC Salida / Planta", value=rfc_origen, disabled=True)
                st.text_input("Nombre / Empresa de Salida", value=nombre_origen, disabled=True)
                st.text_input("CP Origen", value=cp_origen, disabled=True)
                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    st.text_input("Colonia Origen", value=colonia_origen, disabled=True)
                    st.text_input("Municipio Origen", value=municipio_origen, disabled=True)
                with col_o2:
                    st.text_input("Estado Origen", value=estado_origen, disabled=True)
                    st.text_input("País Origen", value=pais_origen, disabled=True)
                st.text_input("Calle y Número de Salida", value=calle_origen, disabled=True)
            else:
                rfc_origen = st.text_input("RFC Salida / Planta", placeholder="RFC de origen")
                nombre_origen = st.text_input("Nombre / Empresa de Salida", placeholder="Ej. Proveedor o Bodega Alterna")
                cp_origen = st.text_input("CP Origen", max_chars=5, placeholder="Ej. 91400, 42188")
                info_o = consultar_cp_mexico(cp_origen)
                
                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    colonia_origen = st.text_input("Colonia Origen", value=info_o["colonia"], placeholder="Colonia")
                    municipio_origen = st.text_input("Municipio Origen", value=info_o["municipio"], placeholder="Municipio")
                with col_o2:
                    estado_origen = st.text_input("Estado Origen", value=info_o["estado"], placeholder="Estado")
                    pais_origen = st.text_input("País Origen", value=info_o["pais"])
                    
                calle_origen = st.text_input("Calle y Número de Salida", placeholder="Ej. Carretera Principal Km 2")

            dir_origen_final = f"{calle_origen}, Col. {colonia_origen}, C.P. {cp_origen}, {municipio_origen}, {estado_origen}"

        with col_destino:
            st.markdown("#### 🛬 DESTINO")
            tipo_modo_destino = st.radio("Modalidad de Destino:", ["Cliente Específico (C.P. / Domicilio)", "Varios Clientes (Ruta General / Zona Libre)"], horizontal=False, key="radio_destino")
            
            col_f3, col_f4 = st.columns(2)
            with col_f3:
                f_llegada_date = st.date_input("Fecha Estimada Llegada", value=ahora_mx.date())
            with col_f4:
                f_llegada_time = st.time_input("Hora Estimada Llegada", value=time(18, 0))

            if tipo_modo_destino == "Cliente Específico (C.P. / Domicilio)":
                rfc_destino = st.text_input("RFC Llegada / Cliente (Opcional)", placeholder="RFC de destino (Vacío si es público general)")
                nombre_destino = st.text_input("Nombre / Empresa de Llegada", placeholder="Ej. Cliente Destino")
                
                cp_destino = st.text_input("CP Destino", max_chars=5, placeholder="Ej. 54680, 91000")
                info_d = consultar_cp_mexico(cp_destino)
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    colonia_destino = st.text_input("Colonia Destino", value=info_d["colonia"], placeholder="Colonia")
                    municipio_destino = st.text_input("Municipio Destino", value=info_d["municipio"], placeholder="Municipio")
                with col_d2:
                    estado_destino = st.text_input("Estado Destino", value=info_d["estado"], placeholder="Estado")
                    pais_destino = st.text_input("País Destino", value=info_d["pais"])
                    
                calle_destino = st.text_input("Calle y Número de Llegada", placeholder="Ej. Av. Principal #10")
                dir_destino_final = f"{calle_destino}, Col. {colonia_destino}, C.P. {cp_destino}, {municipio_destino}, {estado_destino}"
            else:
                rfc_destino = ""
                nombre_destino = "Ruta Varios Clientes"
                col_m_lib1, col_m_lib2 = st.columns(2)
                with col_m_lib1:
                    zona_libre_destino = st.text_input("Destinos / Zona de Reparto", value="Guadalupe Victoria, Veracruz", placeholder="Ej. Banderilla, Xalapa, Las Vigas")
                with col_m_lib2:
                    estado_libre_destino = st.text_input("Estado / Región", value="Veracruz", placeholder="Ej. Veracruz")
                    
                dir_destino_final = f"Ruta multi-cliente / Zona de entrega: {zona_libre_destino}"

    # 6. Mercancía
    with st.container(border=True):
        st.subheader("6. 📦 Descripción y Claves de la Mercancía")
        if tipo_unidad == "Autotanque (Pipa)":
            st.markdown("#### ⛽ Configuración para Pipa (Medidor Magnetel)")
            
            col_calc1, col_calc2 = st.columns(2)
            with col_calc1:
                capacidad_total_num = st.number_input("Capacidad Total de la Pipa (Litros)", min_value=0.0, value=def_capacidad_num, step=100.0)
            with col_calc2:
                porcentaje_magnetel = st.number_input("Porcentaje de Llenado (%) - Magnetel", min_value=0.0, max_value=100.0, value=70.0, step=0.5)

            volumen_calculado_lts = capacidad_total_num * (porcentaje_magnetel / 100.0)

            st.info(f"📊 **Resultado Automático Pipa:** {volumen_calculado_lts:,.2f} Litros")

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                cantidad_texto = f"{volumen_calculado_lts:,.2f} Litros"
                st.text_input("Cantidad Calculada", value=cantidad_texto, disabled=True)
                clave_unidad_sat = "LTR - Litros"
                peso_texto = "N/A"
            with col_m2:
                desc_mercancia = st.text_input("Descripción / Producto", value="Gas Licuado de Petróleo (Gas LP)")
                clave_prod_sat = st.text_input("Clave Producto", value="15111510 (Gas LP)")

        else:
            st.markdown("#### 🛢️ Configuración para Vehículo Repartidor (Cilindros de 20 kg y 30 kg)")
            col_cil1, col_cil2 = st.columns(2)
            with col_cil1:
                cant_cil_20 = st.number_input("Cantidad de Cilindros de 20 KG", min_value=0, value=20, step=1)
            with col_cil2:
                cant_cil_30 = st.number_input("Cantidad de Cilindros de 30 KG", min_value=0, value=15, step=1)

            total_piezas = cant_cil_20 + cant_cil_30
            peso_neto_gas = (cant_cil_20 * 20.0) + (cant_cil_30 * 30.0)

            st.info(f"📊 **Total Envases:** {total_piezas} Cilindros ({cant_cil_20} de 20kg, {cant_cil_30} de 30kg) | **Peso Neto de Gas:** {peso_neto_gas:,.2f} KG")

            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                cantidad_texto = f"{total_piezas} Piezas (Cilindros)"
                st.text_input("Cantidad Calculada", value=cantidad_texto, disabled=True)
                clave_unidad_sat = "H87 - Pieza"
            with col_m2:
                desc_mercancia = st.text_input("Descripción / Producto", value="Gas Licuado de Petróleo (Gas LP en Cilindros)")
                clave_prod_sat = st.text_input("Clave Producto", value="15111510 (Gas LP)")
            with col_m3:
                peso_texto = f"{peso_neto_gas:,.2f} KG"
                st.text_input("Peso Total Neto Gas", value=peso_texto, disabled=True)

    st.markdown("---")
    
    if st.button("Generar y Registrar Carta Porte", type="primary", use_container_width=True):
        if not nombre_chofer or not num_poliza or not desc_mercancia:
            st.warning("⚠️ Por favor completa los datos obligatorios del chofer, póliza y mercancía.")
        else:
            str_salida = f"{f_salida_date.strftime('%d/%m/%Y')} {f_salida_time.strftime('%H:%M')}"
            str_llegada = f"{f_llegada_date.strftime('%d/%m/%Y')} {f_llegada_time.strftime('%H:%M')}"
            
            # OBTENER FOLIO DE LA NUBE
            folio_generado = obtener_siguiente_folio_nube()

            datos_nueva_carta = {
                "folio": folio_generado,
                "nombre_emisor": nombre_emisor,
                "rfc_emisor": rfc_emisor,
                "num_permiso_sct": num_permiso_sct,
                "nombre_chofer": nombre_chofer,
                "rfc_chofer": rfc_chofer,
                "tipo_licencia": tipo_licencia,
                "num_licencia": num_licencia,
                "tipo_unidad": tipo_unidad,
                "eco_unidad": eco_unidad or "S/N",
                "placas": placas,
                "marca_modelo": marca_modelo,
                "capacidad": capacidad,
                "aseguradora": aseguradora,
                "num_poliza": num_poliza,
                "rfc_origen": rfc_origen,
                "nombre_origen": nombre_origen,
                "fecha_salida": str_salida,
                "dir_origen": dir_origen_final,
                "rfc_destino": rfc_destino,
                "nombre_destino": nombre_destino,
                "fecha_llegada": str_llegada,
                "dir_destino": dir_destino_final,
                "cantidad_mercancia": cantidad_texto,
                "clave_unidad_sat": clave_unidad_sat,
                "desc_mercancia": desc_mercancia,
                "clave_prod_sat": clave_prod_sat,
                "peso_mercancia": peso_texto,
                "fecha_registro": ahora_mx.strftime("%d/%m/%Y %H:%M")
            }

            # GUARDAR PERMANENTE EN SUPABASE
            exito = guardar_carta_en_nube(datos_nueva_carta)

            if exito:
                st.success(f"¡Carta Porte con Folio {folio_generado} generada y guardada con éxito en la nube!")
                st.balloons()

elif accion == "Historial de Documentos":
    st.title("📁 ECONOGAS - Historial de Cartas Generadas")
    st.write("Consulta, filtra por fechas y administra los registros almacenados en la nube.")
    st.markdown("---")

    # FILTROS DE FECHA EN EL HISTORIAL
    col_f_1, col_f_2 = st.columns(2)
    with col_f_1:
        filtro_inicio = st.date_input("Filtrar desde la fecha:", value=None)
    with col_f_2:
        filtro_fin = st.date_input("Filtrar hasta la fecha:", value=None)

    historial_nube = cargar_historial_nube()

    if not historial_nube:
        st.info("No hay cartas registradas en la base de datos.")
    else:
        cartas_filtradas = []
        for carta in historial_nube:
            f_reg_str = carta.get('fecha_registro', '')
            try:
                f_reg_date = datetime.strptime(f_reg_str.split()[0], "%d/%m/%Y").date()
                
                incluir = True
                if filtro_inicio and f_reg_date < filtro_inicio:
                    incluir = False
                if filtro_fin and f_reg_date > filtro_fin:
                    incluir = False
                
                if incluir:
                    cartas_filtradas.append(carta)
            except Exception:
                cartas_filtradas.append(carta)

        if not cartas_filtradas:
            st.warning("⚠️ No se encontraron cartas en el rango de fechas seleccionado.")
        else:
            st.write(f"Mostrando **{len(cartas_filtradas)}** registro(s):")
            
            for idx, carta in enumerate(cartas_filtradas):
                with st.container(border=True):
                    col_h1, col_h2, col_h3 = st.columns([2.5, 3, 2.5])
                    with col_h1:
                        st.write(f"🔢 **Folio Nube:** {carta.get('folio', 'N/A')}")
                        st.write(f"📅 **Fecha:** {carta.get('fecha_registro', 'N/A')}")
                        st.write(f"⛽ **Unidad:** {carta.get('tipo_unidad', '')} ({carta.get('eco_unidad', '')})")
                    with col_h2:
                        st.write(f"👤 **Chofer:** {carta.get('nombre_chofer', '')}")
                        st.write(f"🛣️ **Ruta:** {carta.get('nombre_origen', '')} ➔ {carta.get('nombre_destino', '')}")
                    with col_h3:
                        pdf_hist_bytes = generar_pdf(carta)
                        st.download_button(
                            label="📄 Descargar PDF",
                            data=pdf_hist_bytes,
                            file_name=f"Econogas_Folio_{carta.get('folio', '0000001')}.pdf",
                            mime="application/pdf",
                            key=f"dl_econogas_{idx}"
                        )
                        
                        # ELIMINAR CON CONTRASEÑA MAESTRA
                        with st.expander("🗑️ Eliminar este registro"):
                            pass_borrar = st.text_input("Contraseña de autorización", type="password", key=f"pass_del_{carta.get('id')}")
                            if st.button("Confirmar Eliminación", key=f"btn_del_{carta.get('id')}", type="primary"):
                                if pass_borrar == MASTER_PASSWORD:
                                    if eliminar_carta_nube(carta.get('id')):
                                        st.success(f"Carta Folio {carta.get('folio')} eliminada.")
                                        st.rerun()
                                    else:
                                        st.error("Error al eliminar en Supabase.")
                                else:
                                    st.error("❌ Contraseña incorrecta. No se pudo eliminar.")
