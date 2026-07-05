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
from PIL import Image
import io
import gspread
from google.oauth2.service_account import Credentials
import threading
import time

# --------------------------
# KONFIGURASI AWAL + PWA
# --------------------------
st.set_page_config(
    layout="wide",
    page_title="SIGAP TEGES",
    page_icon="🛣️",
    initial_sidebar_state="collapsed"
)

# Meta tag untuk PWA
st.markdown("""
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#023e8a">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="SIGAP TEGES">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/1047/1047785.png">
    <link rel="manifest" href="/manifest.json">
</head>
""", unsafe_allow_html=True)

# --------------------------
# KONEKSI GOOGLE SHEETS
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

sheet = init_gsheets()

# Inisialisasi sesi
if "halaman_aktif" not in st.session_state:
    st.session_state["halaman_aktif"] = "beranda"
if "daftar_laporan" not in st.session_state:
    st.session_state["daftar_laporan"] = []

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
        no_urut = len(semua_data) + 1

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
            foto_url or ""
        ]
        sheet.append_row(row)
        data_baru["No_Urut"] = no_urut
        return True
    except Exception as e:
        st.error(f"Gagal menyimpan ke Google Sheets: {str(e)}")
        st.session_state["daftar_laporan"].append(data_baru)
        return False

def perbarui_status_laporan(no_urut, status_baru):
    if not sheet:
        st.error("❌ Tidak terhubung ke Google Sheets.")
        return False
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            return False
        idx = df.index[df["No Urut"].astype(str).str.strip() == str(no_urut).strip()].tolist()
        if idx:
            row_num = idx[0] + 2
            sheet.update_cell(row_num, 8, status_baru)
            sheet.update_cell(row_num, 9, datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            return True
        return False
    except Exception as e:
        st.error(f"Gagal memperbarui status: {e}")
        return False

@st.cache_data(show_spinner="Memuat data peta...")
def load_data_jalan():
    try:
        with open('jalan_tegal_brebes.geojson', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        st.warning("⚠️ File data jalan tidak ditemukan, peta akan ditampilkan tanpa batas ruas.")
        return None

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
# TAMPILAN & GAYA
# --------------------------
st.markdown("""
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
    .btn-besar {
        width: 100%;
        padding: 2.5rem;
        font-size: 1.4rem;
        font-weight: 700;
        border-radius: 20px;
        border: none;
        background: linear-gradient(135deg, #fbbf24, #f59e0b);
        color: #0f172a;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 6px 20px rgba(251, 191, 36, 0.4);
    }
    .btn-besar:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 28px rgba(251, 191, 36, 0.55);
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
    
    header, #MainMenu, footer, [data-testid="stSidebar"] { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

# --------------------------
# HALAMAN BERANDA
# --------------------------
if st.session_state["halaman_aktif"] == "beranda":
    st.markdown("<h1 class='judul-utama'>🛣️ SIGAP TEGES</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-judul'>Sistem Informasi Geografis & Pelaporan Kondisi Jalan Provinsi</p>", unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        if st.button("📝 BUAT LAPORAN BARU", key="tombol_lapor", use_container_width=True):
            st.session_state["halaman_aktif"] = "lapor"
            st.rerun()
    with col2:
        if st.button("📋 RIWAYAT & STATUS LAPORAN", key="tombol_riwayat", use_container_width=True):
            st.session_state["halaman_aktif"] = "riwayat"
            st.rerun()
# --------------------------
# HALAMAN LAPORAN
# --------------------------
elif st.session_state["halaman_aktif"] == "lapor":
    if st.button("⬅️ Kembali ke Beranda"):
        st.session_state["halaman_aktif"] = "beranda"
        st.rerun()

    st.markdown("<h2 style='color:#fbbf24; margin-bottom:1rem;'>📝 LAPORAN KONDISI JALAN</h2>", unsafe_allow_html=True)

    data_jalan = load_data_jalan()

    # Mode lokasi
    mode_kerja = st.selectbox(
        "Pilih Cara Pengisian Lokasi",
        options=["📍 Gunakan GPS Otomatis", "✍️ Masukkan Koordinat Secara Manual"]
    )

    col1, col2 = st.columns(2)
    with col1: mode_peta = st.selectbox("Jenis Tampilan Peta", ["Jalan", "Satelit", "Gelap"])

    # Ambil koordinat
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

    if data_jalan:
        user_point = Point(u_lon, u_lat)
        min_dist = float('inf')
        target_f = None
        for f in data_jalan['features']:
            jarak = shape(f['geometry']).distance(user_point) * 111.32
            if jarak < min_dist:
                min_dist, target_f = jarak, f
        if min_dist < 0.3:
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
    if data_jalan:
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

        # --------------------------
        # ✅ BAGIAN KAMERA: DIPINDAH KELUAR DARI FORM
        # --------------------------
        if "kamera_aktif" not in st.session_state:
            st.session_state["kamera_aktif"] = False

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

        # --------------------------
        # ✅ FORMULIR UTAMA
        # --------------------------
        with st.form("form_laporan", clear_on_submit=True):
            tipe_masalah = st.selectbox(
                "Jenis Masalah",
                [
                    "Lubang Jalan",
                    "Jalan Amblas",
                    "Kerusakan Bahu Jalan",
                    "Drainase/Gorong-gorong Rusak",
                    "Bencana Alam",
                    "Rambu Lalu Lintas Hilang/Rusak",
                    "Pagar Pengaman Rusak",
                    "Tanah Longsor",
                    "Genangan Air",
                    "Lainnya"
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
                    waktu = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
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
        st.session_state["halaman_aktif"] = "beranda"
        st.rerun()

    st.markdown("<h2 style='color:#fbbf24; margin-bottom:1rem;'>📋 RIWAYAT & STATUS LAPORAN</h2>", unsafe_allow_html=True)

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1: filter_status = st.selectbox("Filter Status", ["Semua", "📥 Baru Dilaporkan", "⚙️ Sedang Dalam Proses Penanganan", "✅ Sesuai Kondisi Penanganan", "❌ Ditunda / Masuk Dalam Rencana Penanganan"])
    with col_f2: filter_ruas = st.selectbox("Filter Ruas", ["Semua"] + [v["nama"] for v in DATA_ATRIBUT.values()])
    with col_f3: cari = st.text_input("Cari Kata Kunci", placeholder="Nomor / Nama jalan / jenis masalah...")

    try:
        if sheet:
            data = sheet.get_all_records()
            df_laporan = pd.DataFrame(data)
        else:
            df_laporan = pd.DataFrame(st.session_state["daftar_laporan"])

        if not df_laporan.empty:
            # ✅ Perbaiki konversi No Urut: hilangkan nilai kosong/tidak valid
            if "No Urut" in df_laporan.columns:
                # Ubah ke angka, ganti yang tidak valid jadi NaN
                df_laporan["No Urut"] = pd.to_numeric(df_laporan["No Urut"], errors="coerce")
                # Hapus baris yang No Urut-nya kosong
                df_laporan = df_laporan.dropna(subset=["No Urut"])
                # Konversi ke bilangan bulat
                df_laporan["No Urut"] = df_laporan["No Urut"].astype("Int64")
                # Urutkan dari terbaru ke terlama
                df_laporan = df_laporan.sort_values(by="No Urut", ascending=False).reset_index(drop=True)

            # Pilih kolom yang akan ditampilkan
            kolom_tampil = [
                "No Urut", "Waktu", "Ruas", "No_Ruas", "KM", 
                "Jenis_Masalah", "Keterangan", "Status", 
                "Terakhir_Diperbarui", "Link_Maps", "Foto_URL"
            ]
            kolom_tersedia = [k for k in kolom_tampil if k in df_laporan.columns]
            df_laporan = df_laporan[kolom_tersedia]

            # Filter data
            if filter_status != "Semua":
                df_laporan = df_laporan[df_laporan["Status"] == filter_status]
            if filter_ruas != "Semua":
                df_laporan = df_laporan[df_laporan["Ruas"] == filter_ruas]
            if cari:
                df_laporan = df_laporan[df_laporan.apply(lambda row: cari.lower() in str(row).lower(), axis=1)]

            if not df_laporan.empty:
                st.dataframe(
                    df_laporan.drop(columns=["Foto_URL"], errors="ignore"),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "No Urut": st.column_config.NumberColumn("No Laporan", width="small"),
                        "Waktu": st.column_config.TextColumn("Waktu Lapor", width="medium"),
                        "Ruas": st.column_config.TextColumn("Nama Ruas", width="large"),
                        "No_Ruas": st.column_config.TextColumn("No Ruas", width="small"),
                        "KM": st.column_config.TextColumn("Titik KM", width="small"),
                        "Jenis_Masalah": st.column_config.TextColumn("Jenis Masalah", width="medium"),
                        "Keterangan": st.column_config.TextColumn("Keterangan", width="large"),
                        "Status": st.column_config.TextColumn("Status Penanganan", width="medium"),
                        "Terakhir_Diperbarui": st.column_config.TextColumn("Diperbarui Pada", width="medium"),
                        "Link_Maps": st.column_config.LinkColumn("Lihat Lokasi", display_text="Buka Peta", width="medium")
                    }
                )

                # ✅ Bagian Tampilan Foto
                st.markdown("---")
                st.subheader("🖼️ Tampilan Foto Laporan")

                daftar_no = ["Pilih nomor laporan..."] + df_laporan["No Urut"].astype(str).tolist()
                pilihan_no = st.selectbox("Pilih nomor laporan untuk melihat fotonya:", options=daftar_no)

                if pilihan_no != "Pilih nomor laporan...":
                    baris_pilih = df_laporan[df_laporan["No Urut"].astype(str) == pilihan_no]
                    if not baris_pilih.empty:
                        foto_url = baris_pilih.iloc[0].get("Foto_URL", "").strip()
                        if foto_url and foto_url.startswith("https://"):
                            st.image(foto_url, caption=f"Foto Laporan No {pilihan_no}", use_column_width=True)
                        else:
                            st.info("ℹ️ Foto belum tersedia untuk laporan ini.")

                csv = df_laporan.drop(columns=["Foto_URL"], errors="ignore").to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Unduh Data Laporan (CSV)",
                    data=csv,
                    file_name=f"laporan_jalan_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("ℹ️ Tidak ada laporan yang sesuai dengan filter.")
        else:
            st.info("ℹ️ Belum ada laporan yang dikirim.")
    except Exception as e:
        st.error(f"⚠️ Gagal memuat data: {str(e)}")
        if st.session_state["daftar_laporan"]:
            st.dataframe(pd.DataFrame(st.session_state["daftar_laporan"]), use_container_width=True, hide_index=True)
# --------------------------
# 🤖 BOT UPDATE STATUS TELEGRAM (VERSI TUNTAS)
# --------------------------
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
GSHEETS_URL = st.secrets["gsheets_url"]
IZIN_CHAT_ID = ["-1003492896109"]  # Pastikan ID grup sesuai
DAFTAR_STATUS = [
    "📥 Baru Dilaporkan",
    "⚙️ Sedang Dalam Proses Penanganan",
    "✅ Sesuai Kondisi Penanganan",
    "❌ Ditunda / Masuk Dalam Rencana Penanganan"
]
URL_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Koneksi ke Google Sheet
def koneksi_sheet_bot():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds).open_by_url(GSHEETS_URL).sheet1

sheet_bot = koneksi_sheet_bot()

# Update status di Sheet
def update_status_bot(no_urut: str, status_baru: str) -> bool:
    try:
        data = sheet_bot.get_all_records()
        if not data:
            return False
        for idx, row in enumerate(data, start=2):
            if str(row.get("No Urut", "")).strip() == str(no_urut).strip():
                sheet_bot.update_cell(idx, 8, status_baru)
                sheet_bot.update_cell(idx, 9, datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                return True
        return False
    except Exception as e:
        print("Update error:", e)
        return False

# Kirim pesan baru
def kirim_pesan_bot(chat_id: str, teks: str, tombol=None):
    try:
        data = {
            "chat_id": chat_id,
            "text": teks,
            "parse_mode": "Markdown"
        }
        if tombol:
            data["reply_markup"] = json.dumps(tombol)
        res = requests.post(f"{URL_API}/sendMessage", data=data, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print("Kirim pesan error:", e)
        return False

# Edit pesan yang sudah ada
def edit_pesan_bot(chat_id: str, pesan_id: int, teks_baru: str):
    try:
        requests.post(
            f"{URL_API}/editMessageText",
            data={
                "chat_id": chat_id,
                "message_id": pesan_id,
                "text": teks_baru,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
    except Exception as e:
        print("Edit pesan error:", e)

# ✅ Tambahan penting: Konfirmasi tombol diklik
def jawab_callback(query_id: str, teks: str = ""):
    try:
        requests.post(
            f"{URL_API}/answerCallbackQuery",
            data={
                "callback_query_id": query_id,
                "text": teks,
                "show_alert": False
            },
            timeout=5
        )
    except Exception as e:
        print("Jawab callback error:", e)

# Proses perintah masuk
def proses_pesan_bot(update):
    pesan = update.get("message", {})
    chat_id = str(pesan.get("chat", {}).get("id", ""))
    teks = pesan.get("text", "").strip()

    if chat_id not in IZIN_CHAT_ID:
        return

    if teks == "/status":
        kirim_pesan_bot(chat_id, """📋 *Cara Update Status Laporan:*

Ketik:
`/update <nomor_laporan>`

Contoh:
`/update 12`

Nanti akan muncul tombol untuk pilih status.
""")

    elif teks.startswith("/update "):
        nomor = teks.replace("/update ", "").strip()
        if not nomor.isdigit():
            kirim_pesan_bot(chat_id, "⚠️ *Format salah!*\nContoh yang benar: `/update 5`")
            return
        tombol = {"inline_keyboard": [[{"text": s, "callback_data": f"set|{nomor}|{s}"}] for s in DAFTAR_STATUS]}
        kirim_pesan_bot(chat_id, f"🔧 *Pilih Status untuk Laporan No: {nomor}*", tombol)

# Proses saat tombol diklik
def proses_callback_bot(update):
    data = update.get("callback_query", {})
    query_id = data.get("id", "")
    chat_id = str(data.get("message", {}).get("chat", {}).get("id", ""))
    pesan_id = data.get("message", {}).get("message_id")
    data_aksi = data.get("data", "")

    if chat_id not in IZIN_CHAT_ID or not data_aksi.startswith("set|"):
        jawab_callback(query_id)
        return

    _, nomor, status = data_aksi.split("|", 2)
    berhasil = update_status_bot(nomor, status)

    if berhasil:
        teks_hasil = f"✅ *Status Berhasil Diperbarui*\n📌 No Laporan: {nomor}\n📊 Status: {status}"
    else:
        teks_hasil = f"❌ *Gagal Memperbarui*\nNomor laporan `{nomor}` tidak ditemukan di daftar."

    # Perbarui tampilan pesan
    edit_pesan_bot(chat_id, pesan_id, teks_hasil)
    # Beri tahu Telegram bahwa tombol sudah diproses
    jawab_callback(query_id, "Status sudah diperbarui ✅" if berhasil else "Nomor laporan tidak ada ❌")

# 🚀 Logika baca pesan tanpa pengulangan
def jalankan_bot():
    offset = 0
    while True:
        try:
            res = requests.get(
                f"{URL_API}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 10,
                    "allowed_updates": ["message", "callback_query"]
                },
                timeout=15
            ).json()

            if res.get("ok") and res.get("result"):
                for upd in res["result"]:
                    # Geser offset agar pesan ini tidak dibaca lagi
                    offset = upd["update_id"] + 1

                    if "message" in upd:
                        proses_pesan_bot(upd)
                    elif "callback_query" in upd:
                        proses_callback_bot(upd)

            # Jeda cukup agar tidak membebani server
            time.sleep(2)

        except Exception as e:
            print("Bot loop error:", e)
            time.sleep(5)

# Jalankan bot
thread_bot = threading.Thread(target=jalankan_bot, daemon=True)
thread_bot.start()