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

# --------------------------
# KONFIGURASI AWAL & PWA
# --------------------------
st.set_page_config(
    layout="wide",
    page_title="SIGAP TEGES",
    page_icon="🛣️",
    initial_sidebar_state="collapsed"
)

# Meta tag untuk PWA & Kustomisasi CSS Utama
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
    
    header, #MainMenu, footer, [data-testid="stSidebar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

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
# Cek query parameter di URL saat pertama kali load / refresh
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
        no_urut = len(semua_data) + 1
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
            st.session_state["kamera_aktif"] = False
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

    # =========================================================
    # 🖼️ 1. DEFINISI MODAL DIALOG MENGAMBANG / POP-UP NATIVE
    # =========================================================
   # =========================================================
                # 🖼️ 1. POP-UP DIALOG MENGAMBANG (ST.DIALOG NATIVE)
                # =========================================================
                @st.dialog("📷 Detail Foto Laporan")
                def popup_foto_dialog(no_id, foto_url, ruas_name):
                    st.write(f"**Nomor Laporan:** #{no_id}")
                    st.write(f"**Ruas Jalan:** {ruas_name}")
                    st.divider()
                    if foto_url and foto_url.startswith("https://"):
                        st.image(foto_url, caption=f"Dokumentasi Laporan #{no_id}", use_container_width=True)
                        st.markdown(f"[🔗 Buka Ukuran Penuh di Tab Baru]({foto_url})")
                    else:
                        st.warning("⚠️ Tidak ada foto lampiran untuk laporan ini.")

                # =========================================================
                # 📊 2. TABEL INTERAKTIF NATIVE DENGAN SELECTION EVENT
                # =========================================================
                # Tambahkan kolom indikator status foto pada dataframe
                df_tampil["Status Foto"] = df_tampil["Foto_URL"].apply(
                    lambda x: "🖼️ Ada Foto" if (isinstance(x, str) and x.startswith("https://")) else "—"
                )

                # Siapkan dataframe visual tanpa menampilkan URL mentah
                df_visual = df_tampil[["No", "Waktu Lapor", "Nama Ruas", "Status Laporan", "Status Foto"]]

                st.caption("💡 *Klik / Sorot baris laporan pada tabel di bawah untuk membuka pop-up foto langsung:*")

                # Render tabel native dengan seleksi single-row
                event = st.dataframe(
                    df_visual,
                    use_container_width=True,
                    hide_index=True,
                    selection_mode="single-row",
                    on_select="rerun", # Trigger rerun instan tanpa reload browser
                    column_config={
                        "No": st.column_config.NumberColumn("No", width="small"),
                        "Waktu Lapor": st.column_config.TextColumn("Waktu Lapor"),
                        "Nama Ruas": st.column_config.TextColumn("Nama Ruas"),
                        "Status Laporan": st.column_config.TextColumn("Status Laporan"),
                        "Status Foto": st.column_config.TextColumn("Lihat Foto", width="small")
                    }
                )

                # =========================================================
                # 🔍 3. DETEKSI SELEKSI BARIS & TAMPILKAN POP-UP MENGAMBANG
                # =========================================================
                selected_rows = event.selection.rows
                if selected_rows:
                    row_idx = selected_rows[0]
                    data_terpilih = df_tampil.iloc[row_idx]
                    no_id = data_terpilih["No"]
                    foto_url = data_terpilih["Foto_URL"]
                    ruas_name = data_terpilih["Nama Ruas"]

                    # Panggil dialog modal mengambang
                    popup_foto_dialog(no_id, foto_url, ruas_name)