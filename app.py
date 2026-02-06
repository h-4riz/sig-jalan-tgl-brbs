import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import datetime
from shapely.geometry import shape, Point
from shapely.ops import nearest_points
from streamlit_js_eval import streamlit_js_eval

# 1. THEME & CONFIG
st.set_page_config(layout="wide", page_title="SIGAP - Tegal Brebes", page_icon="🛣️")

# Custom CSS untuk Menu Modern dan Layout Bersih
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .block-container { padding-top: 1rem !important; }
    
    /* Style untuk area menu di bawah judul */
    .nav-container {
        background: rgba(255, 255, 255, 0.05);
        padding: 10px;
        border-radius: 15px;
        margin-bottom: 20px;
    }
    
    /* Sembunyikan Sidebar Default Streamlit */
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stSidebarNav"] { display: none; }
    
    /* Metrik Styling */
    div[data-testid="stMetricValue"] { font-size: 16px !important; color: #00ffcc; font-weight: bold; }
    div[data-testid="stMetricLabel"] { font-size: 11px !important; }
    
    /* Card Laporan */
    .report-card { background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 15px; border-left: 5px solid #00ffcc; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA INITIALIZATION
if 'daftar_laporan' not in st.session_state:
    st.session_state['daftar_laporan'] = []

DATA_ATRIBUT = {
    "Jalan Provinsi_1": {"nama": "Jl. Raya Jatinegara - Slawi", "no": "056", "km": "KM 10+000 - 15+000"},
    "Jalan Provinsi_2": {"nama": "Jl. Raya Slawi - Jatibarang", "no": "057", "km": "KM 05+200"},
    "Jalan Provinsi_3": {"nama": "Jl. Raya Jatibarang - Ketanggungan", "no": "058", "km": "KM 20+100"},
    "Jalan Provinsi_4": {"nama": "Jl. Raya Ketanggungan - Kersana", "no": "059", "km": "KM 12+000"},
    "Jalan Provinsi_5": {"nama": "Jl. Raya Kersana - Bandungsari", "no": "060", "km": "-"},
    "Jalan Provinsi_6": {"nama": "Jl. Raya Bandungsari - Penanggapan", "no": "061", "km": "-"},
    "Jalan Provinsi_7": {"nama": "Jl. Raya Bandungsari - Salem", "no": "062", "km": "-"},
    "Jalan Provinsi_8": {"nama": "Jl. Raya Bumiayu - Salem", "no": "063", "km": "-"},
    "Jalan Provinsi_9": {"nama": "Jl. Raya Salem - Bts. Kab. Cilacap", "no": "064", "km": "-"},
    "Jalan Provinsi_10": {"nama": "Jl. Raya Sirampog - Bumiayu", "no": "065", "km": "-"},
    "Jalan Provinsi_11": {"nama": "Jl. Raya Morongso - Tuwel - Sirampog", "no": "066", "km": "-"},
}

@st.cache_data
def load_data():
    try:
        with open('jalan_tegal_brebes.geojson', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return None

data_jalan = load_data()

# 3. HEADER & MENU NAVIGASI (PENGGANTI SIDEBAR)
st.title("🛡️ SIGAP TEGAL-BREBES")

# Area Menu Utama
with st.container():
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    col_menu1, col_menu2, col_menu3 = st.columns(3)
    
    with col_menu1:
        mode_peta = st.selectbox("🗺️ Peta", ["Street", "Satellite", "Dark"], label_visibility="collapsed")
    with col_menu2:
        mode_lokasi = st.selectbox("📡 Lokasi", ["Simulasi", "GPS Live"], label_visibility="collapsed")
    with col_menu3:
        if st.button("🗑️ Reset", use_container_width=True):
            st.session_state['daftar_laporan'] = []
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 4. GPS LOGIC
if mode_lokasi == "Simulasi":
    loc = [-6.9833, 109.1333]
else:
    loc = streamlit_js_eval(js_expressions='new Promise((resolve) => { navigator.geolocation.getCurrentPosition((p) => resolve([p.coords.latitude, p.coords.longitude]), (e) => resolve(e.code), {enableHighAccuracy:true, timeout:5000}); })', key='gps_no_sidebar')

# 5. ANALYSIS ENGINE
user_lat, user_lon = (loc[0], loc[1]) if isinstance(loc, list) else (-6.98, 109.13)
display_lat, display_lon, is_snapped, closest_feature, min_dist = user_lat, user_lon, False, None, 0

if isinstance(loc, list) and data_jalan:
    user_point = Point(user_lon, user_lat)
    min_dist_val = float('inf')
    target_feat = None
    
    for f in data_jalan['features']:
        dist = shape(f['geometry']).distance(user_point) * 111.32
        if dist < min_dist_val:
            min_dist_val = dist
            target_feat = f
    
    min_dist = min_dist_val
    closest_feature = target_feat

    if min_dist < 0.2:
        p1, _ = nearest_points(shape(closest_feature['geometry']), user_point)
        display_lat, display_lon, is_snapped = p1.y, p1.x, True

# 6. INFO DASHBOARD (RINGKAS)
id_geojson = closest_feature['properties'].get('KML_FOLDER', '-') if closest_feature else "-"
info_ruas = DATA_ATRIBUT.get(id_geojson, {"nama": id_geojson, "no": "-", "km": "-"})

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Nama Ruas", info_ruas['nama'] if is_snapped else "Luar Jangkauan")
with c2:
    st.metric("No | KM", f"{info_ruas['no']} | {info_ruas['km']}")
with c3:
    st.metric("Jarak", f"{min_dist*1000:.0f} m")

# 7. MAP SECTION
tiles = "OpenStreetMap"
if mode_peta == "Satellite":
    tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
elif mode_peta == "Dark":
    tiles = "CartoDB dark_matter"

m = folium.Map(location=[display_lat, display_lon], zoom_start=17 if is_snapped else 12, tiles=tiles, attr="Google" if "Satellite" in mode_peta else None)
if data_jalan:
    folium.GeoJson(data_jalan, style_function=lambda x: {'color': '#00ffcc', 'weight': 5, 'opacity': 0.5}).add_to(m)
folium.Marker([display_lat, display_lon], icon=folium.Icon(color='cadetblue' if is_snapped else 'red', icon='car', prefix='fa')).add_to(m)

st_folium(m, width="100%", height=400, key=f"map_main_{id_geojson}_{display_lat}")

# 8. FORM LAPORAN (FLOATING-LIKE BUTTON)
if is_snapped:
    with st.expander("📝 BUAT LAPORAN KERUSAKAN", expanded=False):
        st.markdown('<div class="report-card">', unsafe_allow_html=True)
        with st.form("lapor_form", clear_on_submit=True):
            tipe = st.selectbox("Jenis Gangguan", ["Lubang", "Retak", "PJU Mati", "Marka Pudar"])
            foto = st.camera_input("Foto Bukti")
            if st.form_submit_button("KIRIM DATA"):
                st.session_state.daftar_laporan.append({
                    "Waktu": datetime.datetime.now().strftime("%H:%M"),
                    "Ruas": info_ruas['nama'],
                    "KM": info_ruas['km'],
                    "Masalah": tipe
                })
                st.toast("Laporan Terkirim!", icon="🚀")
        st.markdown('</div>', unsafe_allow_html=True)

# 9. DATA LOG (TABEL)
if st.session_state.daftar_laporan:
    st.divider()
    st.subheader("📋 Log Laporan")
    st.dataframe(pd.DataFrame(st.session_state.daftar_laporan), use_container_width=True)