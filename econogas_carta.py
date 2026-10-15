from datetime import datetime, time, date
import time as time_module
from zoneinfo import ZoneInfo
import os
import json
import requests
import uuid
import streamlit as st
from PIL import Image

# Librerías de mapas, QR y PDF
try:
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    GEOPY_DISPONIBLE = True
except ImportError:
    GEOPY_DISPONIBLE = False

try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    FPDF_DISPONIBLE = False

try:
    import qrcode
    import io
    QRCODE_DISPONIBLE = True
except ImportError:
    QRCODE_DISPONIBLE = False

# Nombres de archivos de recursos y base de datos local
LOGO_FILE = "logo_econogas.jpg"
QR_TEMP_FILE = "temp_qr_econogas.png"
HISTORIAL_FILE = "historial_econogas.json"
CP_FILE = "cp_veracruz_puebla.json"

# ================= CARGA DE CATÁLOGO OFICIAL SEPOMEX (VERACRUZ Y PUEBLA) =================
@st.cache_data(show_spinner=False)
def cargar_catalogo_cp_oficial():
    if os.path.exists(CP_FILE):
        try:
            with open(CP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

CATALOGO_SEPOMEX = cargar_catalogo_cp_oficial()

def consultar_cp_mexico(cp):
    cp = str(cp).strip().zfill(5)
    if not cp or len(cp) != 5 or not cp.isdigit():
        return {"colonia": "", "municipio": "", "estado": "", "pais": "México"}
    
    # 1. Búsqueda local inmediata en base oficial Sepomex (Puebla y Veracruz)
    if cp in CATALOGO_SEPOMEX:
        return CATALOGO_SEPOMEX[cp]
    
    # 2. Respaldo API gratuita si no se encuentra en el archivo local
    try:
        url = f"https://api.zippopotam.us/MX/{cp}"
        resp = requests.get(url, timeout=2.5)
        if resp.status_code == 200:
            data = resp.json()
            places = data.get("places", [])
            if places:
                colonia = places[0].get("place name", "")
                estado = places[0].get("state", "")
                return {
                    "colonia": colonia,
                    "municipio": colonia,
                    "estado": estado,
                    "pais": "México"
                }
    except Exception:
        pass

    return {"colonia": "", "municipio": "", "estado": "", "pais": "México"}

# ================= FUNCIONES PARA MANEJO DE HISTORIAL PERSISTENTE =================
def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    if "fecha_dt_str" in item:
                        item["fecha_dt"] = datetime.strptime(item["fecha_dt_str"], "%Y-%m-%d").date()
                    else:
                        item["fecha_dt"] = datetime.now(ZoneInfo("America/Mexico_City")).date()
                return data
        except Exception:
            return []
    return []

def guardar_historial(historial):
    try:
        historial_a_guardar = []
        for item in historial:
            item_copy = item.copy()
            if "fecha_dt" in item_copy and isinstance(item_copy["fecha_dt"], date):
                item_copy["fecha_dt_str"] = item_copy["fecha_dt"].strftime("%Y-%m-%d")
                del item_copy["fecha_dt"]
            historial_a_guardar.append(item_copy)
            
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial_a_guardar, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ================= CONFIGURACIÓN DE LA PÁGINA Y ESTILO AZUL CIELO =================
st.set_page_config(
    page_title="ECONOGAS - Módulo Carta Porte 3.1",
    page_icon=LOGO_FILE if os.path.exists(LOGO_FILE) else "🔵",
    layout="wide"
)

st.markdown("""
    <style>
    .stApp {
        background-color: #f4f8fb;
    }
    .stButton>button {
        background-color: #0077b6;
        color: white;
        border-radius: 6px;
    }
    .stButton>button:hover {
        background-color: #0096c7;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

MASTER_PASSWORD = "ECONO2026"

if "auth_econogas" not in st.session_state:
    st.session_state.auth_econogas = False

if "historial_econogas" not in st.session_state:
    st.session_state.historial_econogas = cargar_historial()

if "ultimo_registro_hash_econogas" not in st.session_state:
    st.session_state.ultimo_registro_hash_econogas = None

if "registro_bloqueado_econogas" not in st.session_state:
    st.session_state.registro_bloqueado_econogas = False

def calcular_distancia_km(origen_str, destino_str):
    if not GEOPY_DISPONIBLE:
        return None
    try:
        geolocator = Nominatim(user_agent="econogas_carta_porte_app")
        loc_origen = geolocator.geocode(f"{origen_str}, Mexico")
        loc_destino = geolocator.geocode(f"{destino_str}, Mexico")
        
        if loc_origen and loc_destino:
            coords_origen = (loc_origen.latitude, loc_origen.longitude)
            coords_destino = (loc_destino.latitude, loc_destino.longitude)
            distancia_recta = geodesic(coords_origen, coords_destino).km
            distancia_carretera = round(distancia_recta * 1.27, 1)
            return distancia_carretera
    except:
        return None
    return None

def generar_qr_archivo(contenido):
    if not QRCODE_DISPONIBLE:
        return False
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=1,
        )
        qr.add_data(contenido)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(QR_TEMP_FILE)
        return True
    except Exception:
        return False

# ================= FUNCIÓN PARA GENERAR EL PDF =================
def generar_pdf(d):
    try:
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        
        if os.path.exists(LOGO_FILE):
            try:
                pdf.image(LOGO_FILE, 10, 10, 25)
            except:
                pass
                
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 8, "ECONOGAS S.A. DE C.V.", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 6, "COMPLEMENTO CARTA PORTE 3.1 - TRÁNSITO FEDERAL", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, f"Fecha de Emisión: {d.get('fecha_registro', '')} | IDCCP: {d.get('idccp', '')}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        def seccion_pdf(titulo):
            pdf.set_fill_color(217, 234, 253)
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(0, 6, f"  {titulo}", fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        # 1. Datos del Emisor
        seccion_pdf("1. DATOS DEL EMISOR Y PERMISOS SCT")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, f"Empresa / Razón Social: {d.get('nombre_emisor', '')}", new_x="RIGHT", new_y="TOP")
        pdf.cell(95, 5, f"RFC Emisor: {d.get('rfc_emisor', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(95, 5, f"Tipo Permiso SCT: {d.get('tipo_permiso_sct', '')}", new_x="RIGHT", new_y="TOP")
        pdf.cell(95, 5, f"Número Permiso SCT: {d.get('num_permiso_sct', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # 2. Datos del Operador / Chofer
        seccion_pdf("2. DATOS DEL OPERADOR / CHOFER (FIGURA TRANSPORTE)")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, f"Chofer: {d.get('nombre_chofer', '')}", new_x="RIGHT", new_y="TOP")
        pdf.cell(95, 5, f"RFC Chofer: {d.get('rfc_chofer', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(95, 5, f"Tipo de Licencia: {d.get('tipo_licencia', '')}", new_x="RIGHT", new_y="TOP")
        pdf.cell(95, 5, f"Número de Licencia: {d.get('num_licencia', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # 3. Unidad y Seguro
        seccion_pdf("3. DATOS DE LA UNIDAD Y SEGURO DE RESPONSABILIDAD")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(95, 5, f"Unidad: {d.get('tipo_unidad', '')} - Eco: {d.get('eco_unidad', '')}", new_x="RIGHT", new_y="TOP")
        pdf.cell(95, 5, f"Placas: {d.get('placas', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(95, 5, f"Marca/Modelo: {d.get('marca_modelo', '')} (Cap: {d.get('capacidad', '')})", new_x="RIGHT", new_y="TOP")
        pdf.cell(95, 5, f"Aseguradora: {d.get('aseguradora', '')} | Póliza: {d.get('num_poliza', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # 4. Origen y Destino
        seccion_pdf("4. RUTA DE TRÁNSITO (ORIGEN Y DESTINO)")
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, "ORIGEN:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(100, 5, f"{d.get('nombre_origen', '')}", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(12, 5, "RFC:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, f"{d.get('rfc_origen', '')}", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(28, 5, "Fecha de Salida:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, f"{d.get('fecha_salida', '')}", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, "Dirección:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        pdf.multi_cell(0, 5, f"{d.get('dir_origen', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, "DESTINO:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(100, 5, f"{d.get('nombre_destino', '')}", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(12, 5, "RFC:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        rfc_dest_val = d.get('rfc_destino', '') if d.get('rfc_destino', '').strip() else "S/N (Público General)"
        pdf.cell(0, 5, f"{rfc_dest_val}", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(28, 5, "Llegada Estimada:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, f"{d.get('fecha_llegada', '')}", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(18, 5, "Dirección:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        pdf.multi_cell(0, 5, f"{d.get('dir_destino', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(42, 5, "Distancia Total Estimada:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, f"{d.get('distancia_km', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # 5. Mercancía SAT
        seccion_pdf("5. DESCRIPCIÓN Y CLAVES SAT DE LA MERCANCÍA")
        pdf.set_font("helvetica", "", 8)
        pdf.cell(0, 5, f"Producto: {d.get('desc_mercancia', '')} | Clave SAT: {d.get('clave_prod_sat', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(95, 5, f"Cantidad: {d.get('cantidad_mercancia', '')} {d.get('clave_unidad_sat', '')}", new_x="RIGHT", new_y="TOP")
        pdf.cell(95, 5, f"Peso Total: {d.get('peso_mercancia', '')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # 6. SECCIÓN DE VALIDACIÓN Y CÓDIGO QR AMPLIADO (38mm)
        seccion_pdf("6. VALIDACIÓN Y VERIFICACIÓN OPERATIVA")
        
        enlace_qr = "https://loginda.siat.sat.gob.mx/nidp/app/login?id=ciec&sid=0&option=credential&sid=0&target=https%3A%2F%2Fverificacfdi.facturaelectronica.sat.gob.mx%2Foauth2%2Fcallback%26scope%3Dmscontribuyente%26code_challenge%3DOfkQhIkHLKEVoxtqW3F3RnIR-cUvRqWF3NEUPFGPvDA%26code_challenge_method%3DS256%26state%3Dg9GL1UZNuFOWSrNeAdEUDRF0RATmkhaCjnz2YOldQ1ZgPIAx8nxrxm6gYV5G1eBLVRAx7nBtdUo9q96KfBfMWfdiXOKoG7l3HcjW78km4jpb7puSzBmW0gYKHClUT5op93de%2BGqEUdwbQXvy%2Bq%2B%2FR08agJatdq5sWNUI6A%2B9qQfRrIcsV6DW5LBStnxqskw4icV%2Fo52LwkOgjZ%2FZHQP46N2Jvxk01CXpItNYWoFSnug9voK72sLWEjiqxv8L6LRvz0Vym3cltWNSE%2FXA%2BzROnWevc0wtsaE5cqW1%2FqvEYcxD5az6nsdVasiSWl%2BeD7bCgZ%2FiFPeFIZhNocmdgS70YS1UQjhlKGue%2B%2BflJAB3XYoQcA0cNDL1QkrNTzd7J0OY8DEiqQBJyoAyC4w62vdIw1AiLzS9THpXuVm6Hd%2FBq56zyLRi9IGBxXn3NyWd0ns9DDGTslm2WAnS2YlAs8rU4Q2Ocu837Vf1T4r3mwOw0ppA6ZpsaAtARRh%2BNjf49BmiCBY%2BVJjbu2fJ60vLdEorUmbkyd7y4DUDqYMK6%2FF3WWs6QFHpX4Thuw2sPvVj8U4duCVgNp6CMkHBkOS2J1zG%2FKFuMNLlJSOeg%2FYSJ%2BgSwyn55wCqlPzpZCqIHwxAFh3gm4wHFWgpOArJZB1hMcrO9T98YF7GQ2uLZNm4vFjxgaU%3D"
        
        if generar_qr_archivo(enlace_qr) and os.path.exists(QR_TEMP_FILE):
            y_qr = pdf.get_y()
            try:
                pdf.image(QR_TEMP_FILE, x=12, y=y_qr, w=38)
            except:
                pass
            
            pdf.set_xy(53, y_qr + 2)
            pdf.set_font("helvetica", "B", 8)
            pdf.cell(0, 5, f"IDCCP (Folio Carta Porte): {d.get('idccp', '')}", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_x(53)
            pdf.set_font("helvetica", "", 7.5)
            pdf.cell(0, 5, f"Estatus de Verificación: ACCESO AL PORTAL DE ACCESO / SAT", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_x(53)
            pdf.cell(0, 5, f"Permiso SCT: {d.get('tipo_permiso_sct', '')} - {d.get('num_permiso_sct', '')}", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_x(53)
            pdf.multi_cell(0, 4.5, "Este documento ampara el traslado operado con las especificaciones técnicas del catálogo SCT / SAT versión 3.1.", new_x="LMARGIN", new_y="NEXT")
            
            pdf.ln(12)

        return bytes(pdf.output(dest='S'))
    except Exception as e:
        pdf_err = FPDF()
        pdf_err.add_page()
        pdf_err.set_font("helvetica", "B", 12)
        pdf_err.cell(0, 10, "Error al generar vista completa del PDF.", ln=True)
        return bytes(pdf_err.output(dest='S'))

# ================= AUTENTICACIÓN RÁPIDA =================
if not st.session_state.auth_econogas:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, use_container_width=True)
        else:
            st.markdown("<h1 style='text-align: center;'>🔵</h1>", unsafe_allow_html=True)
            
    st.markdown("<h2 style='text-align: center; color: #0077b6;'>ECONOGAS S.A. DE C.V.</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Módulo de Generación de Carta Porte 3.1</p>", unsafe_allow_html=True)
    
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

# ================= MENÚ PRINCIPAL DEL MÓDULO =================
with st.sidebar:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, use_container_width=True)
    st.markdown("---")
    st.markdown("### 🎛️ Menú de Navegación")
    accion = st.radio("Selecciona una opción:", ["Nueva Carta Porte", "Historial de Documentos"])
    st.markdown("---")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.auth_econogas = False
        st.rerun()

ahora_mx = datetime.now(ZoneInfo("America/Mexico_City"))

st.session_state.historial_econogas = cargar_historial()

# ================= FORMULARIO PRINCIPAL =================
if accion == "Nueva Carta Porte":
    st.title("📄 ECONOGAS - Generador de Carta Porte 3.1")
    st.write("Complete los campos oficiales requeridos para el tránsito seguro de la unidad.")
    st.markdown("---")

    # --- PARTE 1: DATOS DE LA EMPRESA Y REGISTRO SCT ---
    with st.container(border=True):
        st.subheader("1. 🏢 Datos del Emisor y Registro SCT")
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            nombre_emisor = st.text_input("Razón Social / Empresa Emisora", value="ECONOGAS S.A. de C.V.")
            tipo_permiso_sct = st.selectbox("Tipo de Permiso SCT", ["TPXX00 - Permiso no contemplado", "AUTR02 - Autotransporte Carga Federal", "AUTR01 - Autotransporte Cargas Específicas"])
        with col_e2:
            rfc_emisor = st.text_input("RFC del Emisor", value="ECO1205188P5")
            num_permiso_sct = st.text_input("Número de Permiso SCT", value="TPXX00-ECONO-2026")

    # --- PARTE 2: DATOS DEL CHOFER ---
    with st.container(border=True):
        st.subheader("2. 👤 Datos del Operador / Chofer (Figura Transporte)")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            nombre_chofer = st.text_input("Nombre Completo del Chofer", placeholder="Juan Pérez Gómez")
            rfc_chofer = st.text_input("RFC del Chofer", placeholder="XAXX010101000")
        with col_c2:
            tipo_licencia = st.selectbox("Tipo de Licencia", ["Federal", "Estatal", "Chofer / Vendedor"])
            num_licencia = st.text_input("Número de Licencia", placeholder="Número oficial")

    # --- PARTE 3: DATOS DE LA UNIDAD ---
    with st.container(border=True):
        st.subheader("3. ⛽ Datos de la Unidad")
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            tipo_unidad = st.selectbox("Tipo de Unidad", ["Autotanque (Pipa)", "Vehículo Repartidor (Cilindrera)"])
            eco_unidad = st.text_input("Número Económico", placeholder="Ej. PIPA-01")
            placas = st.text_input("Placas", placeholder="Ej. XX-00-XXX")
        with col_u2:
            marca_modelo = st.text_input("Marca / Modelo", placeholder="Ej. Ford F-350 2020")
            capacidad = st.text_input("Capacidad de la Unidad", placeholder="Ej. 5,000 Litros")
            vin_chasis = st.text_input("Número de Serie / VIN", placeholder="Serie de la unidad")

    # --- PARTE 4: DATOS DE SEGUROS ---
    with st.container(border=True):
        st.subheader("4. 🛡️ Póliza de Seguro")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            aseguradora = st.text_input("Compañía Aseguradora", placeholder="Ej. GNP, Qualitas, AXA")
        with col_s2:
            num_poliza = st.text_input("Número de Póliza", placeholder="Ej. POL-987654321")

    # --- PARTE 5: ORIGEN Y DESTINO ---
    with st.container(border=True):
        st.subheader("5. 📍 Ruta de Tránsito (Origen y Destino)")
        col_origen, col_destino = st.columns(2)

        with col_origen:
            st.markdown("#### 🛫 ORIGEN")
            rfc_origen = st.text_input("RFC Salida / Planta", placeholder="RFC de origen")
            nombre_origen = st.text_input("Nombre / Empresa de Salida", placeholder="Ej. ECONOGAS Planta")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_salida_date = st.date_input("Fecha de Salida", value=ahora_mx.date())
            with col_f2:
                f_salida_time = st.time_input("Hora de Salida", value=ahora_mx.time())
            
            cp_origen = st.text_input("CP Origen", max_chars=5, placeholder="Ej. 91400, 72000")
            info_o = consultar_cp_mexico(cp_origen)
            
            col_o1, col_o2 = st.columns(2)
            with col_o1:
                colonia_origen = st.text_input("Colonia Origen", value=info_o["colonia"], placeholder="Colonia")
                municipio_origen = st.text_input("Municipio Origen", value=info_o["municipio"], placeholder="Municipio")
            with col_o2:
                estado_origen = st.text_input("Estado Origen", value=info_o["estado"], placeholder="Estado")
                pais_origen = st.text_input("País Origen", value=info_o["pais"])
                
            calle_origen = st.text_input("Calle y Número de Salida", placeholder="Ej. Carretera Principal Km 2")

        with col_destino:
            st.markdown("#### 🛬 DESTINO")
            rfc_destino = st.text_input("RFC Llegada / Cliente (Opcional)", placeholder="RFC de destino (Vacío si es público general)")
            nombre_destino = st.text_input("Nombre / Empresa de Llegada", placeholder="Ej. Cliente Destino")
            
            col_f3, col_f4 = st.columns(2)
            with col_f3:
                f_llegada_date = st.date_input("Fecha Estimada Llegada", value=ahora_mx.date())
            with col_f4:
                f_llegada_time = st.time_input("Hora Estimada Llegada", value=time(18, 0))
            
            cp_destino = st.text_input("CP Destino", max_chars=5, placeholder="Ej. 91000, 72100")
            info_d = consultar_cp_mexico(cp_destino)
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                colonia_destino = st.text_input("Colonia Destino", value=info_d["colonia"], placeholder="Colonia")
                municipio_destino = st.text_input("Municipio Destino", value=info_d["municipio"], placeholder="Municipio")
            with col_d2:
                estado_destino = st.text_input("Estado Destino", value=info_d["estado"], placeholder="Estado")
                pais_destino = st.text_input("País Destino", value=info_d["pais"])
                
            calle_destino = st.text_input("Calle y Número de Llegada", placeholder="Ej. Av. Principal #10")

    # --- PARTE 6: MERCANCÍA Y CLAVES SAT ---
    with st.container(border=True):
        st.subheader("6. 📦 Descripción y Claves SAT de la Mercancía")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            cantidad_mercancia = st.text_input("Cantidad", placeholder="Ej. 5,000")
            clave_unidad_sat = st.selectbox("Clave Unidad SAT", ["LTR - Litros", "KGM - Kilogramos"])
        with col_m2:
            desc_mercancia = st.text_input("Descripción / Producto", value="Gas Licuado de Petróleo (Gas LP)")
            clave_prod_sat = st.text_input("Clave Producto SAT", value="15111510 (Gas LP)")
        with col_m3:
            peso_mercancia = st.text_input("Peso Total (KG / Litros)", placeholder="Ej. 2,500 KG")

    # --- CAMPO DE DISTANCIA ---
    with st.container(border=True):
        st.subheader("📏 Distancia del Viaje")
        km_input = st.text_input("Distancia Estimada (KM)", placeholder="Ej. 275 km (Automático si dejas vacío)")

    st.markdown("---")
    
    str_salida_check = f"{f_salida_date.strftime('%d/%m/%Y')} {f_salida_time.strftime('%H:%M')}"
    actual_hash = f"{eco_unidad.strip().upper()}-{nombre_chofer.strip().upper()}-{str_salida_check}"

    if st.session_state.get("ultimo_registro_hash_econogas") != actual_hash:
        st.session_state.registro_bloqueado_econogas = False

    if st.session_state.registro_bloqueado_econogas:
        st.success("✅ Esta carta ya fue registrada con éxito en el Historial. Modifica la información si deseas generar una nueva.")
        submitted_carta = False
    else:
        submitted_carta = st.button("Generar y Registrar Carta Porte", type="primary", use_container_width=True)

    if submitted_carta and not st.session_state.registro_bloqueado_econogas:
        if not nombre_chofer or not rfc_chofer or not num_poliza or not desc_mercancia:
            st.warning("⚠️ Por favor completa los datos obligatorios del chofer, póliza y mercancía.")
        else:
            st.session_state.registro_bloqueado_econogas = True
            st.session_state.ultimo_registro_hash_econogas = actual_hash

            distancia_final = km_input
            if not distancia_final and municipio_origen and municipio_destino:
                km_calculados = calcular_distancia_km(f"{municipio_origen}, {estado_origen}", f"{municipio_destino}, {estado_destino}")
                if km_calculados:
                    distancia_final = f"{km_calculados} km (Aprox.)"
                else:
                    distancia_final = "No calculada"

            str_salida = f"{f_salida_date.strftime('%d/%m/%Y')} {f_salida_time.strftime('%H:%M')}"
            str_llegada = f"{f_llegada_date.strftime('%d/%m/%Y')} {f_llegada_time.strftime('%H:%M')}"

            idccp_generado = f"CCC{str(uuid.uuid4()).upper()[:20]}"

            datos_nueva_carta = {
                "idccp": idccp_generado,
                "nombre_emisor": nombre_emisor,
                "rfc_emisor": rfc_emisor,
                "tipo_permiso_sct": tipo_permiso_sct,
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
                "dir_origen": f"{calle_origen}, Col. {colonia_origen}, C.P. {cp_origen}, {municipio_origen}, {estado_origen}",
                "rfc_destino": rfc_destino,
                "nombre_destino": nombre_destino,
                "fecha_llegada": str_llegada,
                "dir_destino": f"{calle_destino}, Col. {colonia_destino}, C.P. {cp_destino}, {municipio_destino}, {estado_destino}",
                "cantidad_mercancia": cantidad_mercancia,
                "clave_unidad_sat": clave_unidad_sat.split(" - ")[0],
                "desc_mercancia": desc_mercancia,
                "clave_prod_sat": clave_prod_sat,
                "peso_mercancia": peso_mercancia,
                "distancia_km": distancia_final,
                "fecha_registro": ahora_mx.strftime("%d/%m/%Y %H:%M"),
                "fecha_dt": ahora_mx.date()
            }

            st.session_state.historial_econogas.insert(0, datos_nueva_carta)
            guardar_historial(st.session_state.historial_econogas)
            
            st.rerun()

elif accion == "Historial de Documentos":
    st.title("📁 ECONOGAS - Historial de Cartas Generadas")
    st.write("Consulta, filtra por fecha, descarga o elimina registros individuales.")
    st.markdown("---")

    if not st.session_state.historial_econogas:
        st.info("No hay cartas registradas todavía. Genera una nueva en el menú de la izquierda.")
    else:
        with st.container(border=True):
            st.markdown("### 📅 Filtrar por Rango de Fechas")
            col_f_inicio, col_f_fin = st.columns(2)
            with col_f_inicio:
                fecha_inicio = st.date_input("Desde", value=ahora_mx.date())
            with col_f_fin:
                fecha_fin = st.date_input("Hasta", value=ahora_mx.date())

        if "modo_borrado_econogas" not in st.session_state:
            st.session_state.modo_borrado_econogas = False

        with st.expander("🔑 Habilitar Botones de Borrado"):
            pass_del = st.text_input("Ingresa la contraseña para permitir eliminar registros", type="password", key="pass_individual_econogas")
            if pass_del == MASTER_PASSWORD:
                st.session_state.modo_borrado_econogas = True
                st.success("Modo borrado activo. Ahora puedes eliminar registros uno por uno.")
            elif pass_del:
                st.error("Contraseña incorrecta.")
                st.session_state.modo_borrado_econogas = False

        st.markdown("---")
        
        registros_visibles = []
        for idx, carta in enumerate(st.session_state.historial_econogas):
            f_carta = carta.get("fecha_dt", ahora_mx.date())
            if fecha_inicio <= f_carta <= fecha_fin:
                registros_visibles.append((idx, carta))

        if not registros_visibles:
            st.warning(f"No se encontraron cartas registradas entre el {fecha_inicio.strftime('%d/%m/%Y')} y el {fecha_fin.strftime('%d/%m/%Y')}.")
        else:
            indices_a_borrar = None
            for idx, carta in registros_visibles:
                with st.container(border=True):
                    col_h1, col_h2, col_h3 = st.columns([2.5, 3, 2.5])
                    with col_h1:
                        st.write(f"📅 **Fecha:** {carta['fecha_registro']}")
                        st.write(f"⛽ **Unidad:** {carta['tipo_unidad']} ({carta['eco_unidad']})")
                        st.write(f"🆔 **IDCCP:** `{carta.get('idccp', 'N/A')}`")
                    with col_h2:
                        st.write(f"👤 **Chofer:** {carta['nombre_chofer']}")
                        st.write(f"🛣️ **Ruta:** {carta['nombre_origen']} ➔ {carta['nombre_destino']}")
                    with col_h3:
                        pdf_hist_bytes = generar_pdf(carta)
                        st.download_button(
                            label="📄 Descargar PDF SAT",
                            data=pdf_hist_bytes,
                            file_name=f"Econogas_Carta_{carta['eco_unidad']}_{idx}.pdf",
                            mime="application/pdf",
                            key=f"dl_econogas_{idx}"
                        )
                        if st.session_state.modo_borrado_econogas:
                            if st.button("🗑️ Eliminar Registro", key=f"del_econogas_{idx}"):
                                indices_a_borrar = idx

            if indices_a_borrar is not None:
                st.session_state.historial_econogas.pop(indices_a_borrar)
                guardar_historial(st.session_state.historial_econogas)
                st.rerun()
