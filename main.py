import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
from shapely.geometry import shape, Point
from shapely.ops import nearest_points
from streamlit_js_eval import streamlit_js_eval
import requests
from PIL import Image
import io
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone

# Definisikan Zona Waktu Indonesia Barat (WIB = UTC+7)
WIB = timezone(timedelta(hours=7), name="WIB")
# --------------------------
# ✅ KONFIGURASI AWAL — SALIN UTUH DARI SINI
# --------------------------
st.set_page_config(
    page_title="SIGAP TEGES",
    page_icon="https://cdn-icons-png.flaticon.com/512/1047/1047785.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ⚠️ SEMUA kode HTML HARUS DI DALAM blok ini — JANGAN DIPISAH!
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#023e8a">
<meta name="background-color" content="#023e8a">
<meta name="application-name" content="SIGAP TEGES">
<meta name="apple-mobile-web-app-title" content="SIGAP TEGES">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">

<link rel="icon" href="https://cdn-icons-png.flaticon.com/512/1047/1047785.png">
<link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/1047/1047785.png">
<link rel="manifest" href="/manifest.json">

<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    .stApp { 
        background: linear-gradient(135deg, #023e8a 0%, #0096c7 50%, #90e0ef 100%) !important; 
        background-attachment: fixed;
        font-family: 'Inter', sans-serif;
    }
    
    html, body, .stMarkdown, .stText { color: #ffffff !important; }
    .block-container { padding: 2rem 5% !important; max-width: 1200px; margin: auto; }
    
    .card {
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(18px);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 24px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
    }

    .judul-utama {
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        color: #fbbf24;
        text-shadow: 2px 2px 12px rgba(0,0,0,0.25);
        margin-bottom: 0.8rem;
    }

    .sub-judul {
        font-size: 1.2rem;
        text-align: center;
        color: #e0f7ff;
        margin-bottom: 3rem;
    }
    
    .map-wrapper {
        border-radius: 24px;
        overflow: hidden;
        border: 3px solid rgba(255, 255, 255, 0.4);
        box-shadow: 0 6px 24px rgba(0,0,0,0.18);
        margin-bottom: 1.5rem;
    }

    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.35) !important;
        border-radius: 16px;
        padding: 1rem !important;
        border-left: 5px solid #fbbf24 !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    }
    div[data-testid="stMetricLabel"] p { font-size: 1rem !important; font-weight: 600 !important; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem !important; font-weight: 700 !important; }
    
    header, #MainMenu, footer, .stAppToolbar, [data-testid="stToolbar"] { 
        display: none !important; 
    }
    <!-- Daftar Service Worker agar PWA terdeteksi browser -->
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(() => console.log('✅ Service Worker terdaftar'))
      .catch(() => console.log('⚠️ Tidak bisa daftar Service Worker'));
  });
}
</script>
    

</style>
""", unsafe_allow_html=True)
# ⚠️ JANGAN PERNAH menulis <link> atau <meta> DI LUAR blok di atas!
# --------------------------
# ✅ AKHIR BLOK KONFIGURASI
# --------------------------
# --------------------------
# KONEKSI GOOGLE SHEETS & DATA GEOJSON
# --------------------------
@st.cache_resource(show_spinner="Menghubungkan ke Google Sheets...")
def init_gsheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        service_account_info = dict(st.secrets["connections"]["gsheets"])
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(st.secrets["gsheets_url"]).sheet1
        return sheet
    except KeyError as e:
        st.error(f"❌ Kunci rahasia tidak ditemukan: `{e}`. Periksa secrets.toml!")
        return None
    except Exception as e:
        st.error(f"❌ Gagal terhubung ke Google Sheets: {str(e)}")
        return None

@st.cache_data(show_spinner=False)
def load_data_jalan():
    """Membaca file GeoJSON spasial ruas jalan."""
    try:
        with open("data_jalan.geojson", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"type": "FeatureCollection", "features": []}

sheet = init_gsheets()

# --------------------------
# KONTROL NAVIGATION & QUERY PARAMS
# --------------------------
params = st.query_params

if "page" in params:
    st.session_state["halaman_aktif"] = params["page"]
elif "halaman_aktif" not in st.session_state:
    st.session_state["halaman_aktif"] = "beranda"

if "daftar_laporan" not in st.session_state:
    st.session_state["daftar_laporan"] = []
if "kamera_aktif" not in st.session_state:
    st.session_state["kamera_aktif"] = False

# --------------------------
# DATA ATRIBUT JALAN
# --------------------------
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

# --------------------------
# FUNGSI: PERBARUI STATUS LAPORAN
# --------------------------
def perbarui_status_laporan(no_laporan, status_baru):
    """Mencari laporan berdasarkan Nomor Urut & memperbarui statusnya"""
    if not sheet:
        return False, "⚠️ Tidak terhubung ke Google Sheets"
    
    try:
        semua_data = sheet.get_all_records()
        if not semua_data:
            return False, "⚠️ Belum ada data laporan di Google Sheets"
        
        nomor_baris = None
        
        # Cari baris yang nomor urutnya sesuai
        for indeks, baris in enumerate(semua_data, start=2):
            no_dari_sheet = str(baris.get("No Urut", "")).strip()
            no_cari = str(no_laporan).strip()
            if no_dari_sheet == no_cari:
                nomor_baris = indeks
                break
        
        if not nomor_baris:
            return False, f"⚠️ Laporan nomor **{no_laporan}** tidak ditemukan"
        
        DAFTAR_STATUS_VALID = [
            "📥 Baru Dilaporkan",
            "⚙️ Sedang Dalam Proses Penanganan",
            "✅ Sesuai Kondisi Penanganan",
            "❌ Ditunda / Masuk Dalam Rencana Penanganan"
        ]
        
        if status_baru not in DAFTAR_STATUS_VALID:
            return False, f"⚠️ Status tidak dikenali!"
        
        # Cari posisi kolom
        kolom_status = None
        kolom_waktu = None
        if semua_data:
            daftar_judul = semua_data[0].keys()
            for nomor_kolom, nama_kolom in enumerate(daftar_judul, start=1):
                nama = str(nama_kolom).strip().lower()
                if nama == "status":
                    kolom_status = nomor_kolom
                if nama in ["terakhir diperbarui", "terakhir_diperbarui"]:
                    kolom_waktu = nomor_kolom
        
        if not kolom_status:
            return False, "⚠️ Kolom 'Status' tidak ditemukan"
        
        waktu_sekarang = datetime.now(WIB).strftime("%d/%m/%Y %H:%M:%S")
        sheet.update_cell(nomor_baris, kolom_status, status_baru)
        
        if kolom_waktu:
            sheet.update_cell(nomor_baris, kolom_waktu, waktu_sekarang)
        
        # Hapus cache agar halaman Riwayat langsung segar
        if "data_sheet_cache" in st.session_state:
            del st.session_state["data_sheet_cache"]
        if "waktu_muat_data" in st.session_state:
            del st.session_state["waktu_muat_data"]
        
        return True, f"""✅ **Laporan #{no_laporan} DIPERBARUI!**

Status baru:
{status_baru}

⏰ Diperbarui: {waktu_sekarang}"""
    
    except Exception as e:
        return False, f"⚠️ Kesalahan: {str(e)}"

# --------------------------
# FUNGSI UTAMA APLIKASI
# --------------------------
def kompresi_foto(file_foto, ukuran_maks=1000):
    try:
        img = Image.open(file_foto)
        lebar, tinggi = img.size
        if lebar > ukuran_maks or tinggi > ukuran_maks:
            rasio = min(ukuran_maks / lebar, ukuran_maks / tinggi)
            lebar_baru = int(lebar * rasio)
            tinggi_baru = int(tinggi * rasio)
            img = img.resize((lebar_baru, tinggi_baru), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=75, optimize=True)
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.warning(f"Tidak dapat mengompresi foto: {e}")
        return file_foto

def kirim_laporan_lengkap(pesan, file_foto=None):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = str(st.secrets["TELEGRAM_CHAT_ID"]).strip()
        if file_foto:
            foto_terkompres = kompresi_foto(file_foto)
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            res = requests.post(
                url,
                data={"chat_id": chat_id, "caption": pesan, "parse_mode": "Markdown"},
                files={'photo': foto_terkompres},
                timeout=30
            )
            if res.status_code == 200:
                hasil = res.json()
                foto_file_id = hasil["result"]["photo"][-1]["file_id"]
                info_file = requests.get(f"https://api.telegram.org/bot{token}/getFile?file_id={foto_file_id}").json()
                foto_url = f"https://api.telegram.org/file/bot{token}/{info_file['result']['file_path']}"
                return True, foto_url
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            res = requests.post(
                url,
                data={"chat_id": chat_id, "text": pesan, "parse_mode": "Markdown"},
                timeout=20
            )
            return res.status_code == 200, None
        return False, None
    except Exception as e:
        st.error(f"Kesalahan Telegram: {str(e)}")
        return False, None

def simpan_ke_gsheets(data_baru, foto_url=None):
    if not sheet:
        st.warning("⚠️ Tidak terhubung ke Google Sheets, data disimpan sementara di aplikasi.")
        st.session_state["daftar_laporan"].append(data_baru)
        return False
    try:
        semua_data = sheet.get_all_records()
        no_urut = len(semua_data) + 1 if semua_data else 1
        url_simpan = f"'{foto_url}" if foto_url else ""

        row = [
            no_urut,
            data_baru["Waktu"],
            data_baru["Ruas"],
            data_baru["No_Ruas"],
            data_baru["KM"],
            data_baru["Jenis_Masalah"],
            data_baru["Keterangan"],
            data_baru["Status"],
            data_baru["Terakhir_Diperbarui"],
            data_baru["Koordinat"],
            data_baru["Link_Maps"],
            url_simpan
        ]

        sheet.append_row(row, value_input_option="USER_ENTERED")
        data_baru["No_Urut"] = no_urut
        return True
    except Exception as e:
        st.error(f"Gagal menyimpan ke Google Sheets: {str(e)}")
        st.session_state["daftar_laporan"].append(data_baru)
        return False

# ==================================================
# ✅ SISTEM PALING SEDERHANA: KETIK LANGSUNG DI TELEGRAM
# ==================================================
if st.query_params.get("proses_perintah") == "ya":
    st.title("🔄 Memproses Perintah...")
    
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        
        # Ambil perintah dari Telegram
        res = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": -1, "limit": 10, "timeout": 0},
            timeout=15
        )
        
        if res.status_code != 200:
            st.error("❌ Gagal ambil perintah")
            st.stop()
        
        data = res.json()
        if not data.get("ok"):
            st.error("❌ Balasan tidak valid")
            st.stop()
        
        updates = data.get("result", [])
        perintah_diproses = False
        pesan_balasan = ""
        
        for upd in updates:
            uid = upd.get("update_id")
            
            if "message" in upd and "text" in upd["message"]:
                teks = upd["message"]["text"].strip()
                chat_id = upd["message"]["chat"]["id"]
                
                # ======================================
                # ✅ FORMAT: /update NoLaporan Status
                # ======================================
                # Contoh: /update 52 Sesuai Kondisi
                # ======================================
                if teks.startswith("/update"):
                    bagian = teks.split(maxsplit=2)
                    
                    if len(bagian) >= 3:
                        no_laporan = bagian[1].strip()
                        teks_status = bagian[2].strip()
                        
                        # Cocokkan teks yang diketik dengan daftar status
                        DAFTAR_STATUS = {
                            "baru": "📥 Baru Dilaporkan",
                            "baru dilaporkan": "📥 Baru Dilaporkan",
                            "proses": "⚙️ Sedang Dalam Proses Penanganan",
                            "sedang proses": "⚙️ Sedang Dalam Proses Penanganan",
                            "penanganan": "⚙️ Sedang Dalam Proses Penanganan",
                            "sesuai": "✅ Sesuai Kondisi Penanganan",
                            "selesai": "✅ Sesuai Kondisi Penanganan",
                            "sesuai kondisi": "✅ Sesuai Kondisi Penanganan",
                            "ditunda": "❌ Ditunda / Masuk Dalam Rencana Penanganan",
                            "rencana": "❌ Ditunda / Masuk Dalam Rencana Penanganan"
                        }
                        
                        status_dipilih = None
                        for kata_kunci, status_lengkap in DAFTAR_STATUS.items():
                            if kata_kunci in teks_status.lower():
                                status_dipilih = status_lengkap
                                break
                        
                        if status_dipilih:
                            berhasil, pesan_hasil = perbarui_status_laporan(no_laporan, status_dipilih)
                            
                            # Kirim balasan ke Telegram
                            requests.post(
                                f"https://api.telegram.org/bot{token}/sendMessage",
                                data={
                                    "chat_id": chat_id,
                                    "text": pesan_hasil,
                                    "parse_mode": "Markdown"
                                }
                            )
                            pesan_balasan = pesan_hasil
                            perintah_diproses = True
                            requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": uid + 1})
                        
                        else:
                            pesan_balasan = """⚠️ Format status tidak dikenali!

Gunakan kata kunci berikut:
→ `baru` = Baru Dilaporkan
→ `proses` = Sedang Dalam Proses Penanganan
→ `sesuai` = Sesuai Kondisi Penanganan
→ `ditunda` = Ditunda / Masuk Rencana

Contoh: `/update 52 sesuai`"""
                            requests.post(
                                f"https://api.telegram.org/bot{token}/sendMessage",
                                data={
                                    "chat_id": chat_id,
                                    "text": pesan_balasan,
                                    "parse_mode": "Markdown"
                                }
                            )
                            perintah_diproses = True
                            requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": uid + 1})
                    
                    else:
                        pesan_balasan = """📋 **Gunakan format:**
`/update [Nomor] [Status]`

Contoh:
`/update 52 baru`
`/update 52 proses`
`/update 52 sesuai`
`/update 52 ditunda`"""
                        requests.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            data={
                                "chat_id": chat_id,
                                "text": pesan_balasan,
                                "parse_mode": "Markdown"
                            }
                        )
                        perintah_diproses = True
                        requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": uid + 1})
        
        if perintah_diproses:
            st.success("✅ Selesai! Cek balasan di Telegram...")
            st.info(pesan_balasan)
        else:
            st.info("ℹ️ Ketik perintah di Telegram, lalu klik tombol ini sekali.")
            
    except Exception as e:
        st.error(f"⚠️ Kesalahan: {str(e)}")
    
    st.markdown("---")
    if st.button("⬅️ Kembali ke Beranda", type="primary"):
        st.query_params.clear()
        st.rerun()
    
    st.stop()
# --------------------------
# HALAMAN BERANDA
# --------------------------
if st.session_state["halaman_aktif"] == "beranda":
    st.markdown("<h1 class='judul-utama'>SIGAP TEGES</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-judul'>Sistem Informasi Geografis & Pelaporan Kondisi Jalan Provinsi di Wilayah Kab. Tegal dan Kab. Brebes</p>", unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        if st.button("📝 BUAT LAPORAN BARU", key="tombol_lapor", use_container_width=True):
            st.session_state["halaman_aktif"] = "lapor"
            st.session_state["kamera_aktif"] = False
            st.rerun()
    with col2:
        if st.button("📋 RIWAYAT & STATUS LAPORAN", key="tombol_riwayat", use_container_width=True):
            st.session_state["halaman_aktif"] = "riwayat"
            st.rerun()

    st.markdown("---")
    if st.button("🔄 PROSES PERINTAH DARI TELEGRAM", type="primary", use_container_width=True):
        st.query_params["proses_perintah"] = "ya"
        st.rerun()

# --------------------------
# HALAMAN LAPORAN
# --------------------------
elif st.session_state["halaman_aktif"] == "lapor":
    if st.button("⬅️ Kembali ke Beranda"):
        st.session_state["halaman_aktif"] = "beranda"
        st.session_state["kamera_aktif"] = False
        st.rerun()

    st.markdown("<h2 style='color:#fbbf24; margin-bottom:1rem;'>📝 LAPORAN KONDISI JALAN</h2>", unsafe_allow_html=True)

    data_jalan = load_data_jalan()

    mode_kerja = st.selectbox(
        "Pilih Cara Pengisian Lokasi",
        options=["📍 Gunakan GPS Otomatis", "✍️ Masukkan Koordinat Secara Manual"]
    )

    col1, col2 = st.columns(2)
    with col1: mode_peta = st.selectbox("Jenis Tampilan Peta", ["Jalan", "Satelit", "Gelap"])

    if mode_kerja == "📍 Gunakan GPS Otomatis":
        loc = streamlit_js_eval(
            js_expressions='new Promise((resolve) => { navigator.geolocation.getCurrentPosition((p) => resolve([p.coords.latitude, p.coords.longitude]), (e) => resolve([-6.98, 109.13]), {enableHighAccuracy:true, timeout:8000}); })',
            key='gps_aktif'
        )
        u_lat, u_lon = (loc[0], loc[1]) if isinstance(loc, list) else (-6.98, 109.13)
    else:
        u_lat = st.number_input("Garis Lintang (Latitude)", value=-6.98, format="%.6f")
        u_lon = st.number_input("Garis Bujur (Longitude)", value=109.13, format="%.6f")

    display_lat, display_lon, is_snapped, closest_feature = u_lat, u_lon, False, None

    if data_jalan and data_jalan.get("features"):
        user_point = Point(u_lon, u_lat)
        min_dist = float('inf')
        target_f = None
        for f in data_jalan['features']:
            jarak = shape(f['geometry']).distance(user_point) * 111.32
            if jarak < min_dist:
                min_dist, target_f = jarak, f
        if min_dist < 0.3 and target_f:
            p1, _ = nearest_points(shape(target_f['geometry']), user_point)
            display_lat, display_lon, is_snapped, closest_feature = p1.y, p1.x, True, target_f

    id_geo = closest_feature['properties'].get('KML_FOLDER', '-') if closest_feature else "-"
    data_oto = DATA_ATRIBUT.get(id_geo, {"nama": "DI LUAR JANGKAUAN", "no": "-", "km": "-"})

    daftar_nama = [v['nama'] for v in DATA_ATRIBUT.values()]
    idx_def = daftar_nama.index(data_oto['nama']) if data_oto['nama'] in daftar_nama else 0
    ruas_pilih = st.selectbox("Konfirmasi / Pilih Ruas Jalan", options=daftar_nama, index=idx_def)
    id_final = next((k for k, v in DATA_ATRIBUT.items() if v["nama"] == ruas_pilih), "Jalan Provinsi_1")
    atr = DATA_ATRIBUT[id_final]

    col_m1, col_m2 = st.columns(2)
    with col_m1: st.metric("Nama Ruas", atr['nama'])
    with col_m2: st.metric("Nomor & KM", f"ID {atr['no']} | {atr['km']}")

    st.markdown("<div class='map-wrapper'>", unsafe_allow_html=True)
    tiles = "OpenStreetMap"
    if mode_peta == "Satelit":
        tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
        attr = "Google Maps"
    elif mode_peta == "Gelap":
        tiles = "CartoDB dark_matter"
        attr = "CartoDB"
    else:
        attr = "OpenStreetMap"

    m = folium.Map(location=[display_lat, display_lon], zoom_start=17 if is_snapped else 14, tiles=tiles, attr=attr)
    if data_jalan and data_jalan.get("features"):
        folium.GeoJson(data_jalan, style_function=lambda x: {'color': '#fbbf24', 'weight': 5, 'opacity': 0.8}).add_to(m)
    folium.Marker(
        [display_lat, display_lon],
        popup=f"Lokasi: {display_lat:.6f}, {display_lon:.6f}",
        icon=folium.Icon(color='orange' if is_snapped else 'red', icon='road', prefix='fa')
    ).add_to(m)
    st_folium(m, width="100%", height=420, key="peta_utama")
    st.markdown("</div>", unsafe_allow_html=True)

    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📝 Isi Laporan Kerusakan")

        foto = None
        if not st.session_state["kamera_aktif"]:
            if st.button("📸 Ambil Foto Lokasi", use_container_width=True, type="primary"):
                st.session_state["kamera_aktif"] = True
                st.rerun()
        else:
            foto = st.camera_input("🔍 Ambil foto kondisi lokasi", key="input_foto_laporan")
            if foto:
                st.success("✅ Foto sudah diambil dan siap dikirim")
            if st.button("❌ Tutup Kamera", use_container_width=True):
                st.session_state["kamera_aktif"] = False
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("form_laporan", clear_on_submit=True):
            tipe_masalah = st.selectbox(
                "Jenis Masalah",
                [
                    "Lubang Jalan", "Jalan Amblas", "Kerusakan Bahu Jalan",
                    "Drainase/Gorong-gorong Rusak", "Bencana Alam",
                    "Rambu Lalu Lintas Hilang/Rusak", "Pagar Pengaman Rusak",
                    "Tanah Longsor", "Genangan Air", "Lainnya"
                ]
            )
            keterangan = st.text_area(
                "Keterangan Tambahan",
                placeholder="Jelaskan kondisi kerusakan, ukuran, atau hal lain yang perlu diketahui...",
                max_chars=300
            )

            st.markdown("<br>", unsafe_allow_html=True)

            kirim, reset = st.columns(2)
            with kirim:
                tombol_kirim = st.form_submit_button("✅ KIRIM LAPORAN", use_container_width=True, type="primary")
            with reset:
                tombol_reset = st.form_submit_button("🔄 BATAL", use_container_width=True)

            if tombol_kirim:
                if not foto:
                    st.warning("⚠️ Harap ambil foto lokasi terlebih dahulu dengan menekan tombol 'Ambil Foto Lokasi' di atas!")
                else:
                    waktu = datetime.now(WIB).strftime("%d/%m/%Y %H:%M:%S")
                    link_maps = f"https://www.google.com/maps?q={u_lat:.6f},{u_lon:.6f}"

                    data_laporan = {
                        "Waktu": waktu,
                        "Ruas": atr['nama'],
                        "No_Ruas": atr['no'],
                        "KM": atr['km'],
                        "Jenis_Masalah": tipe_masalah,
                        "Keterangan": keterangan or "-",
                        "Status": "📥 Baru Dilaporkan",
                        "Terakhir_Diperbarui": waktu,
                        "Koordinat": f"{u_lat:.6f}, {u_lon:.6f}",
                        "Link_Maps": link_maps
                    }

                    pesan_telegram = f"""
🚨 *LAPORAN KERUSAKAN JALAN*
━━━━━━━━━━━━━━━━━━━━━
🔢 *No Laporan:* {len(sheet.get_all_records()) + 1 if sheet else "-"}
📍 *Ruas Jalan:* {atr['nama']}
🔢 *Nomor Ruas:* {atr['no']}
⚠️ *Jenis Masalah:* {tipe_masalah}
📝 *Keterangan:* {keterangan or "-"}
⏰ *Waktu Lapor:* {waktu}
🌍 *Lokasi:* {link_maps}
📊 *Status:* 📥 Baru Dilaporkan
━━━━━━━━━━━━━━━━━━━━━
                    """

                    with st.status("Mengirim laporan...", expanded=True):
                        ok1, foto_url = kirim_laporan_lengkap(pesan_telegram, foto)
                        ok2 = simpan_ke_gsheets(data_laporan, foto_url)
                        no_urut = data_laporan.get("No_Urut", "-")

                        if ok1 and ok2:
                            st.success(f"✅ Laporan berhasil dikirim! Nomor laporan Anda: **{no_urut}**")
                            st.balloons()
                            st.session_state["kamera_aktif"] = False
                        else:
                            st.warning("⚠️ Laporan terkirim, tersimpan sementara. Akan disinkronkan nanti.")

            if tombol_reset:
                st.session_state["kamera_aktif"] = False
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

# --------------------------
# HALAMAN RIWAYAT & STATUS
# --------------------------
elif st.session_state["halaman_aktif"] == "riwayat":
    if st.button("⬅️ Kembali ke Beranda"):
        st.query_params.clear()
        st.session_state["halaman_aktif"] = "beranda"
        st.rerun()

    st.markdown("<h2 style='color:#fbbf24; margin-bottom:1rem;'>📋 RIWAYAT & STATUS LAPORAN</h2>", unsafe_allow_html=True)

    @st.dialog("📷 Detail Foto Laporan")
    def popup_foto_dialog(no_id, foto_url, ruas_name):
        st.write(f"**Nomor Laporan:** #{no_id}")
        st.write(f"**Ruas Jalan:** {ruas_name}")
        st.divider()
        if foto_url and foto_url.startswith("https://"):
            st.image(foto_url, caption=f"Foto Laporan #{no_id}", use_container_width=True)
            st.markdown(f"[🔗 Buka Ukuran Penuh]({foto_url})")
        else:
            st.warning("⚠️ Tidak ada foto lampiran untuk laporan ini.")
        
        st.write("")
        if st.button("✕ Tutup ", type="primary", use_container_width=True):
            st.query_params["page"] = "riwayat"
            if "foto_no" in st.query_params:
                del st.query_params["foto_no"]
            st.rerun()

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1: filter_status = st.selectbox("Filter Status", ["Semua", "📥 Baru Dilaporkan", "⚙️ Sedang Dalam Proses Penanganan", "✅ Sesuai Kondisi Penanganan", "❌ Ditunda / Masuk Dalam Rencana Penanganan"])
    with col_f2: filter_ruas = st.selectbox("Filter Ruas", ["Semua"] + [v["nama"] for v in DATA_ATRIBUT.values()])
    with col_f3: cari = st.text_input("Cari Kata Kunci", placeholder="Nomor / Nama jalan / jenis masalah...")

    CACHE_DALAM_DETIK = 5

    df_laporan = pd.DataFrame()

    try:
        if sheet:
            waktu_sekarang = datetime.now(WIB)
            perlu_muat_ulang = True

            if ("data_sheet_cache" in st.session_state and "waktu_muat_data" in st.session_state):
                selisih = (waktu_sekarang - st.session_state["waktu_muat_data"]).total_seconds()
                if selisih < CACHE_DALAM_DETIK:
                    perlu_muat_ulang = False

            if perlu_muat_ulang:
                try:
                    data = sheet.get_all_records()
                    st.session_state["data_sheet_cache"] = data
                    st.session_state["waktu_muat_data"] = waktu_sekarang
                except Exception as api_err:
                    data = st.session_state.get("data_sheet_cache", [])
            else:
                data = st.session_state["data_sheet_cache"]

            df_laporan = pd.DataFrame(data)
        else:
            df_laporan = pd.DataFrame(st.session_state.get("daftar_laporan", []))

        if not df_laporan.empty:
            if "No Urut" in df_laporan.columns:
                df_laporan["No Urut"] = pd.to_numeric(df_laporan["No Urut"], errors="coerce")
                df_laporan = df_laporan.dropna(subset=["No Urut"])
                df_laporan["No Urut"] = df_laporan["No Urut"].astype("Int64")
                df_laporan = df_laporan.sort_values(by="No Urut", ascending=False).reset_index(drop=True)

            if filter_status != "Semua" and "Status" in df_laporan.columns:
                df_laporan = df_laporan[df_laporan["Status"] == filter_status]
            if filter_ruas != "Semua" and "Ruas" in df_laporan.columns:
                df_laporan = df_laporan[df_laporan["Ruas"] == filter_ruas]
            if cari:
                df_laporan = df_laporan[df_laporan.apply(lambda row: cari.lower() in str(row).lower(), axis=1)]

            if not df_laporan.empty:
                foto_map = {}
                ruas_map = {}
                data_tabel = []
                for _, row in df_laporan.iterrows():
                    no_urut = row.get("No Urut", "-")
                    foto_url = str(row.get("Foto_URL", "")).strip().lstrip("'")
                    
                    foto_map[str(no_urut)] = foto_url
                    ruas_map[str(no_urut)] = row.get("Ruas", "-")
                    
                    data_tabel.append({
                        "No": no_urut,
                        "Waktu Lapor": row.get("Waktu", "-"),
                        "Nama Ruas": row.get("Ruas", "-"),
                        "Status Laporan": row.get("Status", "-"),
                        "📷 Foto": "Ada Foto" if (foto_url and foto_url.startswith("https://")) else "—"
                    })

                df_tampil = pd.DataFrame(data_tabel)

                css_tabel = """<style>
.tabel-sigap-container {
    width: 100%;
    overflow-x: auto;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    background: #ffffff;
    margin-bottom: 1rem;
}
.tabel-sigap {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Inter', sans-serif;
    font-size: 0.95rem;
    color: #1e293b;
}
.tabel-sigap th {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 700;
    padding: 14px 16px;
    text-align: left;
    border-bottom: 2px solid #e2e8f0;
}
.tabel-sigap td {
    padding: 12px 16px;
    border-bottom: 1px solid #f1f5f9;
    transition: all 0.2s ease-in-out;
}
.tabel-sigap tbody tr td:nth-child(1):hover { background-color: #fef08a !important; color: #854d0e !important; font-weight: bold; }
.tabel-sigap tbody tr td:nth-child(2):hover { background-color: #bfdbfe !important; color: #1e40af !important; font-weight: bold; }
.tabel-sigap tbody tr td:nth-child(3):hover { background-color: #bbf7d0 !important; color: #166534 !important; font-weight: bold; }
.tabel-sigap tbody tr td:nth-child(4):hover { background-color: #e9d5ff !important; color: #6b21a8 !important; font-weight: bold; }
.tabel-sigap tbody tr td:nth-child(5):hover { background-color: #fbcfe8 !important; color: #9d174d !important; font-weight: bold; }
.tabel-sigap tbody tr:hover { background-color: #f8fafc; }
.btn-foto-tabel {
    background: #22c55e;
    color: white !important;
    padding: 6px 12px;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
    transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.btn-foto-tabel:hover {
    background: #16a34a;
    transform: translateY(-1px);
}
</style>"""

                html_rows = ""
                for idx, row in df_tampil.iterrows():
                    no_val = row["No"]
                    waktu_val = row["Waktu Lapor"]
                    ruas_val = row["Nama Ruas"]
                    status_val = row["Status Laporan"]
                    foto_url = foto_map.get(str(no_val), "")

                    if foto_url and foto_url.startswith("https://"):
                        tombol_foto = f'<a href="?page=riwayat&foto_no={no_val}" target="_self" class="btn-foto-tabel">🖼️ Ada Foto</a>'
                    else:
                        tombol_foto = '<span style="color:#94a3b8;">—</span>'

                    html_rows += f'<tr><td style="text-align: center; font-weight: 600;">{no_val}</td><td>{waktu_val}</td><td>{ruas_val}</td><td>{status_val}</td><td style="text-align: center;">{tombol_foto}</td></tr>'

                tabel_html = f'{css_tabel}<div class="tabel-sigap-container"><table class="tabel-sigap"><thead><tr><th style="text-align: center; width: 60px;">No</th><th>Waktu Lapor</th><th>Nama Ruas</th><th>Status Laporan</th><th style="text-align: center; width: 130px;">Lihat Foto</th></tr></thead><tbody>{html_rows}</tbody></table></div>'

                st.markdown(tabel_html, unsafe_allow_html=True)

                params = st.query_params
                if "foto_no" in params:
                    no_terpilih = str(params["foto_no"])
                    url_terpilih = foto_map.get(no_terpilih, "")
                    ruas_terpilih = ruas_map.get(no_terpilih, "-")
                    popup_foto_dialog(no_terpilih, url_terpilih, ruas_terpilih)

                st.markdown("<br>", unsafe_allow_html=True)

                csv = df_laporan.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Unduh Data Laporan (CSV)",
                    data=csv,
                    file_name=f"laporan_jalan_{datetime.now(WIB).strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("ℹ️ Tidak ada laporan yang sesuai dengan filter.")
        else:
            st.info("ℹ️ Belum ada laporan yang dikirim.")

    except Exception as e:
        st.error(f"⚠️ Terjadi kesalahan: {str(e)}")