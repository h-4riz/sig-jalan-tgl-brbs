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
st.set_page_config(layout="wide", page_title="SIGAP Premium", page_icon="🛣️")

# Custom CSS: Ultra Modern Design
st.markdown("""
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');

    <style>
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Background Gradient Soft & Professional */
    .main { 
        background: radial-gradient(circle at top right, #1e293b, #0f172a);
        color: #f1f5f9;
    }
    
    /* Proteksi Scrolling & Margin */
    .block-container { 
        padding-left: 6% !important; 
        padding-right: 12% !important; 
        padding-top: 2rem !important; 
    }
    
    /* Card Navigasi Transparan Mewah */
    .nav-container {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 24px;
        margin-bottom: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    
    /* Header Font */
    h2 { 
        font-weight: 800 !important; 
        letter-spacing: -1px;
        background: linear-gradient(to right, #fbbf24, #f59e0b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Metric Styling - Gold & Slate */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 20px;
        padding: 15px !important;
        border: 1px solid rgba(251, 191, 36, 0.3);
        transition: 0.3s;
    }
    div[data-testid="stMetric"]:hover {
        border: 1px solid rgba(251, 191, 36, 0.6);
        background: rgba(255, 255, 255, 0.05);
    }
    div[data-testid="stMetricValue"] { font-size: 1.2rem !important; color: #fbbf24 !important; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem !important; color: #94a3b8 !important; text-transform: uppercase; letter-spacing: 1px; }
    
    /* Container Peta */
    .map-wrapper {
        border-radius: 28px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
    }

    /* Tombol Bergaya Apple/Modern */
    .stButton>button { 
        border-radius: 16px; 
        background: #fbbf24;
        color: #0f172a !important;
        font-weight: 700;
        border: none;
        padding: 0.6rem 1rem;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .stButton>button:hover { 
        transform: translateY(-3px);
        box-shadow: 0 10px 20px rgba(251, 191, 36, 0.3);
    }

    /* Sembunyikan Sidebar */
    [data-testid="stSidebar"] { display: none; }
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

# 3. HEADER & NAVIGASI
st.markdown("<h2>SIGAP PREMIER</h2>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b; margin-top:-15px; margin-bottom:25px;'>Infrastructure Monitoring System • Tegal - Brebes</p>", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    col_m1, col_m2, col_m3 = st.columns([1, 1, 0.7])
    with col_m1:
        mode_peta = st.selectbox("MAP", ["Street", "Satellite", "Dark"], label_visibility="collapsed")
    with col_m2:
        mode_lokasi = st.selectbox("GPS", ["Simulasi", "GPS Live"], label_visibility="collapsed")
    with col_m3:
        if st.button("RESET DATA", use_container_width=True):
            st.session_state['daftar_laporan'] = []
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 4. GPS LOGIC
if mode_lokasi == "Simulasi":
    loc = [-6.9833, 109.1333]
else:
    loc = streamlit_js_eval(js_expressions='new Promise((resolve) => { navigator.geolocation.getCurrentPosition((p) => resolve([p.coords.latitude, p.coords.longitude]), (e) => resolve(e.code), {enableHighAccuracy:true, timeout:5000}); })', key='gps_v6_lux')

# 5. ANALYSIS ENGINE
user_lat, user_lon = (loc[0], loc[1]) if isinstance(loc, list) else (-6.98, 109.13)
display_lat, display_lon, is_snapped, closest_feature, min_dist = user_lat, user_lon, False, None, 0

if isinstance(loc, list) and data_jalan:
    user_point = Point(user_lon, user_lat)
    min_dist_val = float('inf')
    target_f = None
    for f in data_jalan['features']:
        dist = shape(f['geometry']).distance(user_point) * 111.32
        if dist < min_dist_val:
            min_dist_val, target_f = dist, f
    min_dist, closest_feature = min_dist_val, target_f
    if min_dist < 0.2:
        p1, _ = nearest_points(shape(closest_feature['geometry']), user_point)
        display_lat, display_lon, is_snapped = p1.y, p1.x, True

# 6. DASHBOARD METRICS
id_geo = closest_feature['properties'].get('KML_FOLDER', '-') if closest_feature else "-"
atr = DATA_ATRIBUT.get(id_geo, {"nama": id_geo, "no": "-", "km": "-"})

c1, c2 = st.columns(2)
with c1:
    st.metric("ROAD NAME", atr['nama'] if is_snapped else "OFF ROUTE")
with c2:
    st.metric("SECTION INFO", f"ID: {atr['no']} • {atr['km']}")

# 7. MAP SECTION
st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)
tiles = "OpenStreetMap"
if mode_peta == "Satellite":
    tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
elif mode_peta == "Dark":
    tiles = "CartoDB dark_matter"

m = folium.Map(location=[display_lat, display_lon], zoom_start=17 if is_snapped else 12, tiles=tiles, attr="Google" if "Satellite" in mode_peta else None)
if data_jalan:
    folium.GeoJson(data_jalan, style_function=lambda x: {'color': '#fbbf24', 'weight': 6, 'opacity': 0.6}).add_to(m)

# Custom Marker Icon
folium.Marker(
    [display_lat, display_lon], 
    icon=folium.Icon(color='orange' if is_snapped else 'red', icon='circle-dot', prefix='fa')
).add_to(m)

st_folium(m, width="100%", height=420, key=f"map_lux_{id_geo}_{display_lat}")
st.markdown('</div>', unsafe_allow_html=True)

# 8. REPORTING AREA
st.write("")
if is_snapped:
    with st.expander("📝 NEW INCIDENT REPORT", expanded=False):
        with st.form("lapor_lux", clear_on_submit=True):
            tipe = st.selectbox("Issue Type", ["Pothole", "Cracks", "Lighting", "Drainage"])
            foto = st.camera_input("Capture Proof")
            if st.form_submit_button("SUBMIT REPORT"):
                st.session_state.daftar_laporan.append({
                    "Time": datetime.datetime.now().strftime("%H:%M"),
                    "Road": atr['nama'],
                    "Issue": tipe
                })
                st.toast("Data synchronized!", icon="✨")
else:
    st.info("Move closer to a provincial road to enable reporting.")

# 9. LOG (Minimalist)
if st.session_state.daftar_laporan:
    st.dataframe(pd.DataFrame(st.session_state.daftar_laporan), use_container_width=True)