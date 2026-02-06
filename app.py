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

# Custom CSS untuk tampilan modern (Glassmorphism & Clean Typography)
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #00ffcc; }
    .stButton>button { width: 100%; border-radius: 20px; background-color: #00ffcc; color: black; font-weight: bold; }
    .report-card { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px; border-left: 5px solid #00ffcc; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA INITIALIZATION
if 'daftar_laporan' not in st.session_state:
    st.session_state['daftar_laporan'] = []

KAMUS_JALAN = {
    "Jalan Provinsi_1": "Jl. Raya Jatinegara - Slawi",
    "Jalan Provinsi_2": "Jl. Raya Slawi - Jatibarang",
    "Jalan Provinsi_3": "Jl. Raya Jatibarang - Ketanggungan",
    "Jalan Provinsi_4": "Jl. Raya Ketanggungan - Kersana - Bantarsari",
    "Jalan Provinsi_5": "Jl. Raya Kersana - Bandungsari ",
    "Jalan Provinsi_6": "Jl. Raya Bandungsari - Penanggapan",
    "Jalan Provinsi_7": "Jl. Raya Bandungsari - Salem",
    "Jalan Provinsi_8": "Jl. Raya Bumiayu - Salem",
    "Jalan Provinsi_9": "Jl. Raya Salem - Bts. Kab. Cilacap",
    "Jalan Provinsi_10": "Jl. Raya Sirampog - Bumiayu",
    "Jalan Provinsi_11": "Jl. Raya Morongso - Tuwel - Sirampog",
}
@st.cache_data
def load_data():
    try:
        with open('jalan_tegal_brebes.geojson', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return None

data_jalan = load_data()

# 3. SIDEBAR NAVIGATION
with st.sidebar:
    st.title("🛡️ SIGAP")
    st.subheader("Sistem Informasi Gangguan Jalan Provinsi")
    st.divider()
    
    mode_peta = st.selectbox("🗺️ Tampilan Peta", ["Standard Street", "High-Res Satellite", "Dark Mode Canvas"])
    mode_lokasi = st.radio("📡 Sensor Lokasi", ["Simulasi (Dev Mode)", "GPS Real-time"])
    
    st.divider()
    if st.button("🗑️ Reset Semua Laporan"):
        st.session_state['daftar_laporan'] = []
        st.rerun()

# 4. GPS LOGIC
if mode_lokasi == "Simulasi (Dev Mode)":
    loc = [-6.9833, 109.1333]
else:
    loc = streamlit_js_eval(js_expressions='new Promise((resolve) => { navigator.geolocation.getCurrentPosition((p) => resolve([p.coords.latitude, p.coords.longitude]), (e) => resolve(e.code), {enableHighAccuracy:true}); })', key='gps_pro')

# 5. ANALYSIS ENGINE
user_lat, user_lon = (loc[0], loc[1]) if isinstance(loc, list) else (-6.98, 109.13)
display_lat, display_lon, is_snapped, closest_feature, min_dist = user_lat, user_lon, False, None, 0

if isinstance(loc, list) and data_jalan:
    user_point = Point(user_lon, user_lat)
    min_dist_val = float('inf')
    for f in data_jalan['features']:
        dist = shape(f['geometry']).distance(user_point) * 111.32
        if dist < min_dist_val:
            min_dist_val, closest_feature = dist, f
    
    min_dist = min_dist_val
    if min_dist < 0.2: # Snap if within 200m
        p1, _ = nearest_points(shape(closest_feature['geometry']), user_point)
        display_lat, display_lon, is_snapped = p1.y, p1.x, True

# 6. MAIN DASHBOARD LAYOUT
col_map, col_info = st.columns([2, 1])

with col_map:
    # Tiles Selection
    tiles = "OpenStreetMap"
    if mode_peta == "High-Res Satellite":
        tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
    elif mode_peta == "Dark Mode Canvas":
        tiles = "CartoDB dark_matter"

    m = folium.Map(location=[display_lat, display_lon], zoom_start=16 if is_snapped else 12, tiles=tiles, attr="Google" if "google" in tiles else None)
    
    # Draw Roads
    if data_jalan:
        folium.GeoJson(data_jalan, style_function=lambda x: {'color': '#00ffcc', 'weight': 4, 'opacity': 0.6}).add_to(m)
    
    # User Marker
    folium.Marker(
        [display_lat, display_lon], 
        icon=folium.Icon(color='cadetblue' if is_snapped else 'red', icon='person-walking', prefix='fa')
    ).add_to(m)
    
    st_folium(m, width="100%", height=550, key=f"peta_{mode_peta}_{display_lat}")

with col_info:
    st.markdown("### 📊 Real-time Monitoring")
    raw_name = closest_feature['properties'].get('KML_FOLDER', 'Unknown') if closest_feature else "-"
    nama_jalan = KAMUS_JALAN.get(raw_name, raw_name)
    
    st.metric("📍 Lokasi Saat Ini", nama_jalan if is_snapped else "Luar Jangkauan")
    st.metric("📏 Jarak ke Jalan", f"{min_dist*1000:.1f} meter")
    
    if is_snapped:
        st.success("🎯 Terkunci pada aset jalan")
        with st.container():
            st.markdown('<div class="report-card">', unsafe_allow_html=True)
            st.markdown("#### 📝 Lapor Gangguan")
            with st.form("lapor_form", clear_on_submit=True):
                tipe = st.selectbox("Jenis Masalah", ["Lubang", "Penerangan Jalan", "Drainase Mampet", "Marka Pudar"])
                ket = st.text_area("Catatan")
                if st.form_submit_button("KIRIM LAPORAN"):
                    st.session_state.daftar_laporan.append({
                        "Waktu": datetime.datetime.now().strftime("%H:%M:%S"),
                        "Ruas": nama_jalan,
                        "Masalah": tipe
                    })
                    st.toast("Laporan Terkirim!", icon="🚀")
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("Dekati jalan provinsi untuk melapor.")

# 7. ANALYTICS SECTION (DATA TABLE & CHART)
st.divider()
st.subheader("📋 Log Laporan Masyarakat")
if st.session_state.daftar_laporan:
    df = pd.DataFrame(st.session_state.daftar_laporan)
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.dataframe(df, use_container_width=True)
    with c2:
        # Mini chart menggunakan bar chart bawaan streamlit
        st.write("Statistik Masalah")
        chart_data = df['Masalah'].value_counts()
        st.bar_chart(chart_data)
else:
    st.write("Belum ada data laporan masuk.")