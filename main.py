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
from PIL import Image
import io

# --------------------------
# KONFIGURASI AWAL
# --------------------------
st.set_page_config(
    layout="wide",
    page_title="SIGAP TEGES",
    page_icon="🛣️",
    initial_sidebar_state="collapsed"
)

conn = st.connection("gsheets", type=GSheetsConnection)
if "halaman_aktif" not in st.session_state:
    st.session_state["halaman_aktif"] = "beranda"
if "daftar_laporan" not in st.session_state:
    st.session_state["daftar_laporan"] = []

# --------------------------
# FUNGSI UTAMA
# --------------------------
def kompresi_foto(file_foto, ukuran_maks=1000):
    """Kompresi foto agar ukuran tidak terlalu besar"""
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
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            res = requests.post(
                url,
                data={"chat_id": chat_id, "text": pesan, "parse_mode": "Markdown"},
                timeout=20
            )
        return res.status_code == 200
    except Exception as e:
        st.error(f"Kesalahan Telegram: {str(e)}")
        return False

def simpan_ke_gsheets(data_baru):
    try:
        df_lama = conn.read(ttl=0)
        df_total = pd.concat([df_lama, pd.DataFrame([data_baru])], ignore_index=True)
        conn.update(data=df_total)
        return True
    except Exception as e:
        st.error(f"Kesalahan Simpan Data: {str(e)}")
        return False

def perbarui_status_laporan(waktu_laporan, status_baru):
    """Fungsi untuk mengubah status laporan yang sudah ada"""
    try:
        df = conn.read(ttl=0)
        # Cari baris yang sesuai dengan waktu laporan
        kondisi = df["Waktu"] == waktu_laporan
        if kondisi.any():
            df.loc[kondisi, "Status"] = status_baru
            df.loc[kondisi, "Terakhir_Diperbarui"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            conn.update(data=df)
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
        st.warning("File data jalan tidak ditemukan, peta akan ditampilkan tanpa batas ruas.")
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
    
    /* Kartu & Navigasi */
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
    
    /* Peta & Data */
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
    
    /* Sembunyikan elemen bawaan */
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

    col1, col2 = st.columns(2)
    with col1: mode_peta = st.selectbox("Jenis Tampilan Peta", ["Jalan", "Satelit", "Gelap"])
    with col2: mode_lokasi = st.selectbox("Sumber Lokasi", ["Mode Simulasi", "GPS Langsung"])

    if mode_lokasi == "Mode Simulasi":
        loc = [-6.9833, 109.1333]
    else:
        loc = streamlit_js_eval(
            js_expressions='new Promise((resolve) => { navigator.geolocation.getCurrentPosition((p) => resolve([p.coords.latitude, p.coords.longitude]), (e) => resolve([-6.98, 109.13]), {enableHighAccuracy:true, timeout:8000}); })',
            key='gps_aktif'
        )

    u_lat, u_lon = (loc[0], loc[1]) if isinstance(loc, list) else (-6.98, 109.13)
    display_lat, display_lon, is_snapped, closest_feature = u_lat, u_lon, False, None

    if isinstance(loc, list) and data_jalan:
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
        with st.form("form_laporan", clear_on_submit=True):
            tipe_masalah = st.selectbox("Jenis Masalah", ["Lubang Jalan", "Jalan Amblas", "Kerusakan Bahu Jalan", "Drainase/Gorong-gorong", "Bencana Alam", "Rambu Hilang/Rusak", "Lainnya"])
            keterangan = st.text_area("Keterangan Tambahan", placeholder="Jelaskan kondisi secara rinci...", max_chars=300)
            foto = st.camera_input("Ambil Foto Kondisi Lokasi")

            kirim, reset = st.columns(2)
            with kirim:
                tombol_kirim = st.form_submit_button("✅ KIRIM LAPORAN", use_container_width=True, type="primary")
            with reset:
                tombol_reset = st.form_submit_button("🔄 BATAL", use_container_width=True)

            if tombol_kirim:
                if not foto:
                    st.warning("⚠️ Harap ambil foto lokasi terlebih dahulu!")
                else:
                    waktu = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    link_maps = f"https://www.google.com/maps?q={u_lat:.6f},{u_lon:.6f}"

                    # Data laporan dengan status awal
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
📍 *Ruas Jalan:* {atr['nama']}
🔢 *Nomor Ruas:* {atr['no']}
⚠️ *Masalah:* {tipe_masalah}
📝 *Keterangan:* {keterangan or "-"}
⏰ *Waktu:* {waktu}
🌍 *Lokasi:* {link_maps}
📊 *Status:* 📥 Baru Dilaporkan
━━━━━━━━━━━━━━━━━━━━━
                    """

                    with st.status("Mengirim laporan...", expanded=True):
                        ok1 = kirim_laporan_lengkap(pesan_telegram, foto)
                        ok2 = simpan_ke_gsheets(data_laporan)

                        if ok1 and ok2:
                            st.session_state["daftar_laporan"].append(data_laporan)
                            st.success("✅ Laporan berhasil dikirim dan tersimpan! Status: Baru Dilaporkan")
                            st.balloons()
                        else:
                            st.error("❌ Gagal mengirim. Periksa koneksi internet atau pengaturan.")
        st.markdown("</div>", unsafe_allow_html=True)

# --------------------------
# HALAMAN RIWAYAT & STATUS
# --------------------------
elif st.session_state["halaman_aktif"] == "riwayat":
    if st.button("⬅️ Kembali ke Beranda"):
        st.session_state["halaman_aktif"] = "beranda"
        st.rerun()

    st.markdown("<h2 style='color:#fbbf24; margin-bottom:1rem;'>📋 RIWAYAT & STATUS LAPORAN</h2>", unsafe_allow_html=True)

    # Filter laporan
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1: filter_status = st.selectbox("Filter Status", ["Semua", "📥 Baru Dilaporkan", "⚙️ Sedang Diproses", "✅ Selesai Ditangani", "❌ Ditunda / Tidak Dapat Ditangani"])
    with col_f2: filter_ruas = st.selectbox("Filter Ruas", ["Semua"] + [v["nama"] for v in DATA_ATRIBUT.values()])
    with col_f3: cari = st.text_input("Cari Kata Kunci", placeholder="Nama jalan / jenis masalah...")

    try:
        df_laporan = conn.read(ttl=0)
        if not df_laporan.empty:
            # Terapkan filter
            if filter_status != "Semua":
                df_laporan = df_laporan[df_laporan["Status"] == filter_status]
            if filter_ruas != "Semua":
                df_laporan = df_laporan[df_laporan["Ruas"] == filter_ruas]
            if cari:
                df_laporan = df_laporan[df_laporan.apply(lambda row: cari.lower() in str(row).lower(), axis=1)]

            if not df_laporan.empty:
                # Tampilkan tabel laporan
                st.dataframe(
                    df_laporan,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Link_Maps": st.column_config.LinkColumn("Lihat Lokasi", display_text="Buka Peta"),
                        "Waktu": st.column_config.TextColumn("Waktu Lapor", width="small"),
                        "Status": st.column_config.TextColumn("Status", width="medium")
                    }
                )

                # Bagian perbarui status (untuk petugas)
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.subheader("🔄 Perbarui Status Laporan")
                daftar_waktu = df_laporan["Waktu"].tolist()
                waktu_pilih = st.selectbox("Pilih Laporan Berdasarkan Waktu", daftar_waktu)
                status_baru = st.selectbox("Ubah Menjadi Status", ["📥 Baru Dilaporkan", "⚙️ Sedang Diproses", "✅ Selesai Ditangani", "❌ Ditunda / Tidak Dapat Ditangani"])
                
                if st.button("💾 Simpan Perubahan Status", use_container_width=True, type="primary"):
                    if perbarui_status_laporan(waktu_pilih, status_baru):
                        st.success("✅ Status laporan berhasil diperbarui!")
                        st.rerun()
                    else:
                        st.error("❌ Gagal memperbarui status.")
                st.markdown("</div>", unsafe_allow_html=True)

                # Tombol unduh data
                csv = df_laporan.to_csv(index=False).encode("utf-8")
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
        st.warning("⚠️ Gagal memuat data dari Google Sheets.")
        if st.session_state["daftar_laporan"]:
            st.dataframe(pd.DataFrame(st.session_state["daftar_laporan"]), use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ Belum ada riwayat laporan.")