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

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .block-container { padding-top: 1rem !important; }
    div[data-testid="stMetricValue"] { font-size: 18px !important; color: #00ffcc; }
    .report-card { background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 15px; border-left: 5px solid #00ffcc; }
    .stButton>button { width: 100%; border-radius: 12px; background-color: #00ffcc; color: black; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA INITIALIZATION
if 'daftar_laporan' not in st.session_state:
    st.session_state['daftar_laporan'] = []

# --- KAMUS ATRIBUT LENGKAP ---
# Di sini kita definisikan Nama, No Ruas, dan KM untuk setiap ID di GeoJSON kamu
DATA_ATRIBUT = {
    "Jalan Provinsi_1": {"nama": "Jl. Raya Jatinegara - Slawi", "no": "056", "km": "KM 10+000 - 15+000"},
    "Jalan Provinsi_2": {"nama": "Jl. Raya Slawi - Jatibarang", "no": "057", "km": "KM 05+200"},
    "Jalan Provinsi_3": {"nama": "Jl. Raya Jatibarang - Ketanggungan", "no": "058", "km": "KM 20+100"},
    "Jalan Provinsi_4": {"nama": "Jl. Raya Ketanggungan - Kersana", "no": "059", "km": "KM 12+000"},
    # Tambahkan seterusnya sesuai jumlah ruasmu (Jalan Provinsi_5, dsb)
}

@st.cache_data
def load_data():
    try:
        with open('jalan_tegal_brebes.geojson', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return None

data_jalan = load_data()

# 3. SIDEBAR & GPS
with st.sidebar:
    st.title("🛡️ SIGAP")
    mode_lokasi = st.sidebar.radio("📡 Lokasi", ["Simulasi (Slawi)", "GPS Real-time"])
    if st.button("🗑️ Reset Laporan"):
        st.session_state['daftar_laporan'] = []
        st.rerun()

if mode_lokasi == "Simulasi (Slawi)":
    loc = [-6.9833, 109.1333]
else:
    loc = streamlit_js_eval(js_expressions='new Promise((resolve) => { navigator.geolocation.getCurrentPosition((p) => resolve([p.coords.latitude, p.coords.longitude]), (e) => resolve(e.code), {enableHighAccuracy:true, timeout:5000}); })', key='gps_v4')

# 4. ANALYSIS ENGINE (SENSITIF TERHADAP PERUBAHAN TITIK)
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

# 5. HEADER & INFO RUAS
st.title("🛣️ SIGAP Monitoring")

# Mengambil data dari kamus berdasarkan ID GeoJSON
id_geojson = closest_feature['properties'].get('KML_FOLDER', '-') if closest_feature else "-"
info_ruas = DATA_ATRIBUT.get(id_geojson, {"nama": id_geojson, "no": "-", "km": "-"})

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Nama Ruas", info_ruas['nama'] if is_snapped else "Luar Jangkauan")
with col_b:
    st.metric("No Ruas | KM", f"{info_ruas['no']} | {info_ruas['km']}")
with col_c:
    st.metric("Jarak ke As", f"{min_dist*1000:.0f} m")

# 6. MAP SECTION
m = folium.Map(location=[display_lat, display_lon], zoom_start=17 if is_snapped else 12, tiles="OpenStreetMap")
if data_jalan:
    folium.GeoJson(data_jalan, style_function=lambda x: {'color': '#00ffcc', 'weight': 5, 'opacity': 0.5}).add_to(m)
folium.Marker([display_lat, display_lon], icon=folium.Icon(color='cadetblue' if is_snapped else 'red', icon='car', prefix='fa')).add_to(m)

# Menambahkan ID dinamis pada key agar peta dipaksa refresh saat pindah ruas
st_folium(m, width="100%", height=380, key=f"map_{id_geojson}_{display_lat}")

# 7. FORM LAPORAN
if is_snapped:
    with st.expander("📝 LAPOR KERUSAKAN", expanded=False):
        with st.form("lapor_form", clear_on_submit=True):
            tipe = st.selectbox("Masalah", ["Lubang", "Retak", "PJU Mati"])
            foto = st.camera_input("Foto")
            if st.form_submit_button("KIRIM"):
                st.session_state.daftar_laporan.append({
                    "Waktu": datetime.datetime.now().strftime("%H:%M"),
                    "Ruas": info_ruas['nama'],
                    "KM": info_ruas['km'],
                    "Masalah": tipe
                })
                st.toast("Tercatat!")

if st.session_state.daftar_laporan:
    st.dataframe(pd.DataFrame(st.session_state.daftar_laporan), use_container_width=True)