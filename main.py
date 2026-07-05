# --------------------------
# 🤖 BOT UPDATE STATUS TELEGRAM (VERSI FINAL ANTI-ULANG & STABIL)
# --------------------------
TELEGRAM_TOKEN = st.secrets["8016748185:AAF6ynm16h2ea1-674Q1EfBQtRnArlZSP_U"]
GSHEETS_URL = st.secrets["gsheets_url"]
IZIN_CHAT_ID = ["-1003492896109"]  # ID Grup
DAFTAR_STATUS = [
    "📥 Baru Dilaporkan",
    "⚙️ Sedang Dalam Proses Penanganan",
    "✅ Sesuai Kondisi Penanganan",
    "❌ Ditunda / Masuk Dalam Rencana Penanganan"
]
URL_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Simpan status agar tidak hilang saat halaman dimuat ulang
if "bot_offset" not in st.session_state:
    st.session_state["bot_offset"] = 0
if "bot_sudah_diproses" not in st.session_state:
    st.session_state["bot_sudah_diproses"] = set()
if "bot_berjalan" not in st.session_state:
    st.session_state["bot_berjalan"] = False

# Koneksi ke Sheet
def koneksi_sheet_bot():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds).open_by_url(GSHEETS_URL).sheet1

sheet_bot = koneksi_sheet_bot()

# Update status
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

# Kirim pesan
def kirim_pesan_bot(chat_id: str, teks: str, tombol=None):
    try:
        data = {
            "chat_id": chat_id,
            "text": teks,
            "parse_mode": "Markdown"
        }
        if tombol:
            data["reply_markup"] = json.dumps(tombol)
        res = requests.post(f"{URL_API}/sendMessage", data=data, timeout=6)
        return res.status_code == 200
    except Exception as e:
        print("Kirim pesan error:", e)
        return False

# Edit pesan
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
            timeout=6
        )
    except Exception as e:
        print("Edit pesan error:", e)

# ✅ Wajib ada agar tombol tidak terlihat "macet"
def jawab_callback(query_id: str, teks: str = "", alert: bool = False):
    try:
        requests.post(
            f"{URL_API}/answerCallbackQuery",
            data={
                "callback_query_id": query_id,
                "text": teks[:200],
                "show_alert": alert
            },
            timeout=5
        )
    except Exception as e:
        print("Jawab callback error:", e)

# Proses perintah teks
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
`/update 24`

Akan muncul tombol pilihan status.
""")

    elif teks.startswith("/update "):
        nomor = teks.replace("/update ", "").strip()
        if not nomor.isdigit():
            kirim_pesan_bot(chat_id, "⚠️ *Format salah!*\nContoh: `/update 5`")
            return
        tombol = {"inline_keyboard": [[{"text": s, "callback_data": f"set|{nomor}|{s}"}] for s in DAFTAR_STATUS]}
        kirim_pesan_bot(chat_id, f"🔧 *Pilih Status untuk Laporan No: {nomor}*", tombol)

# Proses klik tombol
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

    teks_hasil = f"✅ *Status Berhasil Diperbarui*\n📌 No Laporan: `{nomor}`\n📊 Status: `{status}`" if berhasil else f"❌ *Laporan Tidak Ditemukan*\nNomor `{nomor}` tidak ada di daftar."

    edit_pesan_bot(chat_id, pesan_id, teks_hasil)
    jawab_callback(query_id, "✅ Selesai" if berhasil else "❌ Tidak ditemukan")

# 🚀 Logika utama: Gunakan st.session_state agar tidak hilang saat refresh
def jalankan_bot():
    while True:
        try:
            offset = st.session_state["bot_offset"]
            sudah_diproses = st.session_state["bot_sudah_diproses"]

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
                    update_id = upd["update_id"]

                    if update_id in sudah_diproses:
                        st.session_state["bot_offset"] = update_id + 1
                        continue

                    sudah_diproses.add(update_id)
                    st.session_state["bot_offset"] = update_id + 1
                    st.session_state["bot_sudah_diproses"] = sudah_diproses

                    if "message" in upd:
                        proses_pesan_bot(upd)
                    elif "callback_query" in upd:
                        proses_callback_bot(upd)

                if len(sudah_diproses) > 500:
                    st.session_state["bot_sudah_diproses"] = set(list(sudah_diproses)[-200:])

            time.sleep(2.5)

        except Exception as e:
            print("Bot error:", e)
            time.sleep(4)

# ✅ Cegah bot berjalan ganda
if not st.session_state["bot_berjalan"]:
    thread_bot = threading.Thread(target=jalankan_bot, daemon=True)
    thread_bot.start()
    st.session_state["bot_berjalan"] = True