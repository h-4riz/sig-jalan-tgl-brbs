import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import datetime
from shapely.geometry import shape, Point
from shapely.ops import nearest_points
from streamlit_js_eval import streamlit_js_eval

# 1. TEMA & KONFIGURASI
st.set_page_config(layout="wide", page_title="SigapTeges", page_icon="logo.jpg")

# Custom CSS: Perpaduan Kanvas Biru Terang & Metrik Premium Glow
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap');

    /* Pastikan tidak ada teks di luar tag style ini */
    
    .stApp {
        background: linear-gradient(135deg, #0077b6 0%, #00b4d8 100%) !important;
        background-attachment: fixed;
    <style>
    /* 1. KANVAS UTAMA: BIRU TERANG VIBRANT */
    .stApp {
        background: linear-gradient(135deg, #0077b6 0%, #00b4d8 100%) !important;
        background-attachment: fixed;
    }

    /* 2. TYPOGRAPHY GLOBAL */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #ffffff;
    }

    /* 3. PROTEKSI SCROLLING & MARGIN (Sisi kanan lebih luas untuk jempol) */
    .block-container { 
        padding-left: 5% !important; 
        padding-right: 15% !important; 
        padding-top: 1.5rem !important; 
    }
    
    /* 4. NAVIGASI (MENU) ATAS */
    .nav-container {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 18px;
        border-radius: 24px;
        margin-bottom: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    /* 5. JUDUL UTAMA EMAS */
    h2 { 
        font-weight: 1200 !important; 
        color: #fbbf24 !important;
        text-shadow: 2px 2px 8px rgba(0,0,0,0.2);
        letter-spacing: -1px;
    }
    
    /* 6. STYLE METRIK: PERSIS SEPERTI GAMBAR (GOLD GLOW) */
    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.3) !important; 
        border-radius: 18px;
        padding: 20px !important;
        border: 2px solid #fbbf24 !important; /* Border Emas Menyala */
        box-shadow: 0 0 20px rgba(251, 191, 36, 0.4); /* Efek Glow */
    }

    /* Judul Kolom (NAMA RUAS / INFORMASI RUAS) */
    div[data-testid="stMetricLabel"] p {
        font-size: 1.0rem !important;
        color: #ffffff !important; 
        font-weight: 900 !important;
        letter-spacing: 1px !important;
        text-transform: uppercase;
    }

    /* Isi Kolom (Isi Data) - PUTIH BERSIH & RAKSASA */
    div[data-testid="stMetricValue"] {
        font-size: 0.8rem !important; 
        color: #ffffff !important;   
        font-weight: 900 !important;
        line-height: 1.1;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    /* 7. BINGKAI PETA */
    .map-wrapper {
        border-radius: 30px;
        overflow: hidden;
        border: 3px solid rgba(255, 255, 255, 0.5);
        box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    }

    /* 8. TABEL DATA (DATAFRAME) */
    [data-testid="stDataFrame"] {
        background: white;
        border-radius: 20px;
        padding: 10px;
    }
    /* Menghilangkan padding putih di paling atas dan menu dekoratif */
    header {visibility: hidden;}
    .main .block-container {padding-top: 1rem !important;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    }
    /* Sembunyikan Sidebar */
    [data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA ATRIBUT (Kamus Manual)
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
if 'daftar_laporan' not in st.session_state:
    st.session_state['daftar_laporan'] = []

# 3. HEADER
st.markdown("<h2>SIGAP TEGES</h2>", unsafe_allow_html=True)
st.markdown("<p style='color: #e0f2fe; margin-top:-15px; margin-bottom:25px; font-weight:600;'>Sistem Informasi Geografis Jalan Provinsi (Ruas Kab. Tegal - Kab. Brebes)</p>", unsafe_allow_html=True)

# 4. MENU NAVIGASI
with st.container():
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    col_m1, col_m2, col_m3 = st.columns([1, 1, 0.7])
    with col_m1:
        mode_peta = st.selectbox("TAMPILAN", ["Jalan", "Satelit", "Gelap"], label_visibility="collapsed")
    with col_m2:
        mode_lokasi = st.selectbox("SENSOR", ["Mode Simulasi", "GPS Langsung"], label_visibility="collapsed")
    with col_m3:
        if st.button("HAPUS DATA", use_container_width=True):
            st.session_state['daftar_laporan'] = []
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 5. LOGIKA GPS
if mode_lokasi == "Mode Simulasi":
    loc = [-6.9833, 109.1333]
else:
    loc = streamlit_js_eval(js_expressions='new Promise((resolve) => { navigator.geolocation.getCurrentPosition((p) => resolve([p.coords.latitude, p.coords.longitude]), (e) => resolve(e.code), {enableHighAccuracy:true, timeout:5000}); })', key='gps_vfinal')

# 6. ANALISIS POSISI
user_lat, user_lon = (loc[0], loc[1]) if isinstance(loc, list) else (-6.98, 109.13)
display_lat, display_lon, is_snapped, closest_feature = user_lat, user_lon, False, None

if isinstance(loc, list) and data_jalan:
    user_point = Point(user_lon, user_lat)
    min_dist_val = float('inf')
    target_f = None
    for f in data_jalan['features']:
        dist = shape(f['geometry']).distance(user_point) * 111.32
        if dist < min_dist_val:
            min_dist_val, target_f = dist, f
    if min_dist_val < 0.2:
        p1, _ = nearest_points(shape(target_f['geometry']), user_point)
        display_lat, display_lon, is_snapped, closest_feature = p1.y, p1.x, True, target_f

# 7. DASHBOARD INFO (PREMIUM METRICS)
id_geo = closest_feature['properties'].get('KML_FOLDER', '-') if closest_feature else "-"
atr = DATA_ATRIBUT.get(id_geo, {"nama": "DI LUAR JANGKAUAN", "no": "-", "km": "-"})

c1, c2 = st.columns(2)
with c1:
    st.metric("NAMA RUAS", atr['nama'] if is_snapped else "CARI JALAN...")
with c2:
    st.metric("INFORMASI RUAS", f"ID: {atr['no']} • {atr['km']}")

# 8. PETA
st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)
tiles = "OpenStreetMap"
if mode_peta == "Satelit":
    tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
elif mode_peta == "Gelap":
    tiles = "CartoDB dark_matter"

m = folium.Map(location=[display_lat, display_lon], zoom_start=17 if is_snapped else 12, tiles=tiles, attr="Google" if "Satelit" in mode_peta else None)
if data_jalan:
    folium.GeoJson(data_jalan, style_function=lambda x: {'color': '#fbbf24', 'weight': 7, 'opacity': 0.8}).add_to(m)
folium.Marker([display_lat, display_lon], icon=folium.Icon(color='orange' if is_snapped else 'red', icon='circle-dot', prefix='fa')).add_to(m)

st_folium(m, width="100%", height=450, key=f"map_final_{id_geo}_{display_lat}")
st.markdown('</div>', unsafe_allow_html=True)

# 9. FORM LAPORAN & RIWAYAT
st.write("")
if is_snapped:
    with st.expander("📝 BUAT LAPORAN KONDISI", expanded=False):
        with st.form("lapor_final", clear_on_submit=True):
            tipe = st.selectbox("Jenis Masalah", ["Lubang Jalan", "Jalan Retak", "Jalan Amblas", "Masalah Drainase", "Bencana Alam"])
            ket = st.text_input("Keterangan Tambahan", placeholder="Contoh: Kedalaman lubang ±10cm", max_chars=100)
            st.camera_input("Ambil Foto")
            if st.form_submit_button("KIRIM DATA"):
                st.session_state.daftar_laporan.append({"Waktu": datetime.datetime.now().strftime("%H:%M"), "Ruas": atr['nama'], "Masalah": tipe})
                st.toast("Tersimpan!")

if st.session_state.daftar_laporan:
    st.write("### 📋 Log Aktivitas")
    st.dataframe(pd.DataFrame(st.session_state.daftar_laporan), use_container_width=True)