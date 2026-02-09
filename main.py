import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import datetime
from shapely.geometry import shape, Point
from shapely.ops import nearest_points
from streamlit_js_eval import streamlit_js_eval
import requests
from streamlit_gsheets import GSheetsConnection
conn = st.connection("gsheets", type=GSheetsConnection)
# ==========================================
# 0. FUNGSI KIRIM (VERSI STABIL)
# ==========================================
def kirim_laporan_lengkap(pesan, file_foto=None):
    token = st.secrets["TELEGRAM_TOKEN"]
    chat_id = str(st.secrets["TELEGRAM_CHAT_ID"]).strip() # Membersihkan spasi gaib
    
    try:
        if file_foto:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            res = requests.post(url, data={"chat_id": chat_id, "caption": pesan}, files={'photo': file_foto.getvalue()}, timeout=30)
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            res = requests.post(url, data={"chat_id": chat_id, "text": pesan}, timeout=20)
        
        if res.status_code == 200:
            return True
        else:
            st.error(f"Telegram Error: {res.json().get('description')}")
            return False
    except Exception as e:
        st.error(f"Masalah Koneksi: {e}")
        return False
    
def simpan_ke_gsheets(data_baru):
    try:
        # 1. Baca data yang sudah ada (tanpa cache agar cepat & akurat)
        df_lama = conn.read(ttl=0)
        
        # 2. Gabungkan langsung dengan data baru
        df_total = pd.concat([df_lama, pd.DataFrame([data_baru])], ignore_index=True)
        
        # 3. Kirim balik ke Sheets
        conn.update(data=df_total)
        return True
    except Exception:
        return False
# ==========================================
# 1. TEMA & KONFIGURASI
# ==========================================
st.set_page_config(layout="wide", page_title="SigapTeges", page_icon="logo.jpg")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap');
    .stApp { background: linear-gradient(135deg, #0077b6 0%, #00b4d8 100%) !important; background-attachment: fixed; }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #ffffff; }
    .block-container { padding: 1.5rem 5% !important; }
    .nav-container { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.2); padding: 18px; border-radius: 24px; margin-bottom: 25px; }
    h2 { font-weight: 1200 !important; color: #fbbf24 !important; text-shadow: 2px 2px 8px rgba(0,0,0,0.2); }
    div[data-testid="stMetric"] { background: rgba(15, 23, 42, 0.3) !important; border-radius: 18px; padding: 10px !important; border: 2px solid #fbbf24 !important; box-shadow: 0 0 20px rgba(251, 191, 36, 0.4); }
    div[data-testid="stMetricLabel"] p { font-size: 0.9rem !important; color: #ffffff !important; font-weight: 900 !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 1rem !important; color: #ffffff !important; font-weight: 900 !important; }
    .map-wrapper { border-radius: 30px; overflow: hidden; border: 3px solid rgba(255, 255, 255, 0.5); }
    [data-testid="stDataFrame"] { background: white; border-radius: 20px; padding: 10px; }
    header, #MainMenu, footer {visibility: hidden;}
    [data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. DATA ATRIBUT & GEOJSON
# ==========================================
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

# ==========================================
# 3. HEADER & NAVIGASI
# ==========================================
st.markdown("<h2>SIGAP TEGES</h2>", unsafe_allow_html=True)
st.markdown("<p style='color: #e0f2fe; margin-top:-15px; margin-bottom:25px; font-weight:600;'>Sistem Informasi Geografis Jalan Provinsi</p>", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    c_m1, c_m2 = st.columns(2)
    with c_m1: mode_peta = st.selectbox("TAMPILAN", ["Jalan", "Satelit", "Gelap"], label_visibility="collapsed")
    with c_m2: mode_lokasi = st.selectbox("SENSOR", ["Mode Simulasi", "GPS Langsung"], label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 4. LOGIKA GPS & SNAPPING
# ==========================================
if mode_lokasi == "Mode Simulasi":
    loc = [-6.9833, 109.1333]
else:
    loc = streamlit_js_eval(js_expressions='new Promise((resolve) => { navigator.geolocation.getCurrentPosition((p) => resolve([p.coords.latitude, p.coords.longitude]), (e) => resolve(e.code), {enableHighAccuracy:true, timeout:5000}); })', key='gps_vfinal')

u_lat, u_lon = (loc[0], loc[1]) if isinstance(loc, list) else (-6.98, 109.13)
display_lat, display_lon, is_snapped, closest_feature = u_lat, u_lon, False, None

if isinstance(loc, list) and data_jalan:
    user_point = Point(u_lon, u_lat)
    min_dist = float('inf')
    target_f = None
    for f in data_jalan['features']:
        dist = shape(f['geometry']).distance(user_point) * 111.32
        if dist < min_dist:
            min_dist, target_f = dist, f
    if min_dist < 0.3: # Snapping 300 meter
        p1, _ = nearest_points(shape(target_f['geometry']), user_point)
        display_lat, display_lon, is_snapped, closest_feature = p1.y, p1.x, True, target_f

# ==========================================
# 5. DASHBOARD INFORMASI
# ==========================================
id_geo = closest_feature['properties'].get('KML_FOLDER', '-') if closest_feature else "-"
data_oto = DATA_ATRIBUT.get(id_geo, {"nama": "DI LUAR JANGKAUAN", "no": "-", "km": "-"})

st.markdown("<p style='color: #fbbf24; font-weight: bold; margin-bottom: 5px;'>📍 KONFIRMASI LOKASI RUAS:</p>", unsafe_allow_html=True)
daftar_nama = [v['nama'] for v in DATA_ATRIBUT.values()]
try: idx_def = daftar_nama.index(data_oto['nama'])
except: idx_def = 0

ruas_final = st.selectbox("Pilih Ruas", options=daftar_nama, index=idx_def, label_visibility="collapsed")
id_final = next((k for k, v in DATA_ATRIBUT.items() if v["nama"] == ruas_final), "Jalan Provinsi_1")
atr = DATA_ATRIBUT.get(id_final)

col1, col2 = st.columns(2)
with col1: st.metric("NAMA RUAS", atr['nama'])
with col2: st.metric("INFORMASI RUAS", f"ID: {atr['no']} • {atr['km']}")

# ==========================================
# 6. PETA
# ==========================================
st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)
tiles = "OpenStreetMap"
if mode_peta == "Satelit": tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
elif mode_peta == "Gelap": tiles = "CartoDB dark_matter"

m = folium.Map(location=[display_lat, display_lon], zoom_start=17 if is_snapped else 14, tiles=tiles, attr="Google")
if data_jalan:
    folium.GeoJson(data_jalan, style_function=lambda x: {'color': '#fbbf24', 'weight': 5, 'opacity': 0.8}).add_to(m)
folium.Marker([display_lat, display_lon], icon=folium.Icon(color='orange' if is_snapped else 'red', icon='circle-dot', prefix='fa')).add_to(m)
st_folium(m, width="100%", height=400, key=f"map_{display_lat}")
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 7. FORM LAPORAN
# ==========================================
st.write("")
with st.expander("📝 BUAT LAPORAN KONDISI", expanded=True):
    with st.form("lapor_final", clear_on_submit=True):
        tipe = st.selectbox("Jenis Masalah", ["Lubang Jalan", "Jalan Amblas", "Drainase/Gorong-gorong", "Bencana Alam", "Lainnya"])
        ket = st.text_input("Keterangan Tambahan", placeholder="Contoh: Lubang dalam ±10cm")
        foto = st.camera_input("Ambil Foto Kerusakan")
        
        c_t1, c_t2 = st.columns(2)
        with c_t1: submit = st.form_submit_button("KIRIM DATA", use_container_width=True)
        with c_t2: reset = st.form_submit_button("HAPUS ISIAN", use_container_width=True)

        if submit:
            if not foto:
                st.warning("Silakan ambil foto terlebih dahulu!")
            else:
                # 1. Tentukan variabel dasar
                waktu_skrg = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                link_map = f"https://www.google.com/maps?q={u_lat},{u_lon}"
                
                # 2. BUAT DATA UNTUK GSHEETS (Variabel ini harus ada di sini)
                data_laporan = {
                    "Waktu": waktu_skrg,
                    "Ruas": atr['nama'],
                    "No_ruas": str(atr['no']),
                    "KM": str(atr['km']),
                    "Masalah": tipe,
                    "Keterangan": ket if ket else "-",
                    "Status": "⏳ Terkirim",
                    "Link_maps": link_map
                }

                # 3. BUAT PESAN UNTUK TELEGRAM
                pesan_bot = (
                    f"🚨 *LAPORAN BARU*\n"
                    f"Ruas: {atr['nama']}\n"
                    f"No Ruas: {atr['no']}\n"
                    f"Masalah: {tipe}\n"
                    f"Keterangan: {ket if ket else '-'}\n"
                    f"Waktu: {waktu_skrg}\n"
                    f"Maps: {link_map}"
                )

                # 4. PROSES PENGIRIMAN
        if submit:
            # Buat indikator loading kecil di pojok, bukan spinner besar yang berat
            with st.status("Mengirim data...", expanded=False) as status:
                
                # ... (bagian penyiapan data_laporan & pesan_bot tetap sama) ...

                # Kirim data secara berurutan
                ok_tele = kirim_laporan_lengkap(pesan_bot, foto)
                ok_sheet = simpan_ke_gsheets(data_laporan)

                if ok_tele and ok_sheet:
                    status.update(label="✅ Laporan Terkirim!", state="complete")
                    st.balloons() # Muncul HANYA saat semua sudah sukses
                    st.success("Berhasil!")
                else:
                    status.update(label="❌ Gagal Terkirim", state="error")
                    st.error("Periksa koneksi internet.")
# ==========================================
# 8. LOG AKTIVITAS
# ==========================================
if st.session_state.daftar_laporan:
    st.write("### 📋 Log Aktivitas")
    st.dataframe(pd.DataFrame(st.session_state.daftar_laporan), use_container_width=True, hide_index=True)