import requests
import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# ======================================
# 📋 SESUAIKAN DENGAN DATA YANG SUDAH ADA
# ======================================
# Token bot yang sudah kamu pakai
TELEGRAM_TOKEN = st.secrets["8016748185:AAF6ynm16h2ea1-674Q1EfBQtRnArlZSP_U"]  # atau tempel langsung: "123456:ABC..."

# URL Google Sheets yang sama
GSHEETS_URL = st.secrets["https://docs.google.com/spreadsheets/d/1HYg8Fh2b3jMCWvnT4BCWfEfDfUd0_Iqnk5qmttujegQ/edit"]

# JSON kredensial (format aman tanpa error PEM)
GSHEETS_JSON = '''
{
}type = "service_account"
project_id = "our-metric-486916-j2"
private_key_id = "67f3a33978e1e0eb8df323fb148b8fa263b724b4"
private_key = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDb+LJkXtoGkBBp
YN//T/f54huMc4p5lGmbv3wM8/93HhzToDS5rG+MITd0egJwElCD/+wnYJx5cEJM
qZ5wyWF10qT4po8iqNUIKh3CGBkolE/l1oP5GQamwDzfA+3FzYgHpZw6e18C7+Td
Z2ozPGnJ7aMNRGz1Nrs/vArh2dmA3dNKmgPfhfW0d9lgwivrizwHarWXwuNsB7ZD
2LtEv6dsH6H9nnfXpwtp68h353PCkH3cv8Cf4d0caioFSLUBniCRsFzVkhMYSdTq
S9cqa1jEtEhALuaq0SfLWLKfGGIACJftnFrm2+S4S3u8mjOIZ115eZ8EcE5Cn+fJ
yP5CJholAgMBAAECggEAERA26F3KPFmXCFGdNp0hr4bYW7oHuxwl4BDHwup3feo+
UrU5+dA0O/LErjqbr01gZQjobPqL0MjCP9elhHq+nmjnZqlm74mYsuAvfEOpyfHN
S9cq2BsWnr9JSYRwwJgLrgos9wVkbqIkxv7zaEOOsj0Gmawd5pynBE/mKTRgsKP/
lAXsER1DQUDLMJz1L8P4hcj/t9oW4BXf5AO0yVtLo+lqpikoHfLpAtjl/cV15h6W
JOx0x8x8qVpl2uek8NPy72fHAzt0APK3t8vzawZEYp2lsYc4hi3Qo9WI0NHr9vzK
OUFkpW6ZLMZzAoHIWnWcqLbYq8ZU4OtU+pNsdeKLsQKBgQD7aYI23D9KvvKPKQqL
tPG6ajCPfW3VyFETOiAIx41fyHLsaI/wUg6iN/XVA7a1obkPGGq3kSOnWhJS+QzT
dasUmmpNkTxu1uYRHkQWRNpR6zzakRSh6cTsL29cwabRkCxT18gfwWdxdom0WG6c
iSjqpiNDvWiAiYK6SWzGNPoY1QKBgQDf/E+HRGVHULbBZ1WkYbJn20Pq93UbOhpr
ZkwM6eMICozX2JHIQy+yT/2Jq+McCgff/jl65p7ddFZ+vrXG2+8Ht9bDZEmYMzQE
uyPHV/ebiHQtbs04bzOLlIz2HpFc03pcu4V0BS03LOC/EnO7iy+9DBa/28iV+ndV
aeGGABqkEQKBgCZwRzxkCDlBYIyK1dXuYFcEDVCi+LwK2Hp8FJHDENZoK0oB4p/3
q80ZiTh8TN8QTt8D+K0AP9dCajLNaSybfQC1azNY1UiNCrfrTLWq6UZFFRTFwcXP
nBAQYJJp+TtpM53ODAbu5wXt/bfZHXBJeDwIErQ0rVmZrKcWus7DIsnRAoGAR51K
aDtsDmM2K5w4e7ho7F/k1UmNfckUDWbFxhM57aZB5flukxM4OtDshYoZsStb3ThR
dIQsIy5BQYEEabKEOHmFBzAXf7xPU3vqMqBjoKz+SFB2+SZE2soCT+byHzXWl7O1
NaU6Ebwdl7n0mvAjsVQeKfXBqoJMiVizLL73xaECgYEA7YVj04fNBb1OWHWc2Ofo
v7YHYiXMmoBy8wpT7ACu/0zJ/KiI6BNGGzrLP7czoJAx3eUNwzGv+50brVW9KHa5
j1gcggtiXrQP+vS9IVjjFSEmgWupwXm06HAfTfI3seOWNkRPNHb903/HVYN6XCFr
EqNY1TtW+ByXiqN0dCkRLl8=
-----END PRIVATE KEY-----
"""
client_email = "sigapteges-bot@our-metric-486916-j2.iam.gserviceaccount.com"
client_id = "117156630123368504351"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/sigapteges-bot@our-metric-486916-j2.iam.gserviceaccount.com"
} 
'''
# ✅ ID Grup Telegram yang SUDAH ADA
IZIN_CHAT_ID = ["-1003492896109"]  # GANTI dengan ID grup kamu
# Cara dapat ID: buka https://api.telegram.org/bot<TOKEN>/getUpdates
# Cari "chat":{"id":-100xxxxxxxxx}

# Daftar status sesuai aplikasi
DAFTAR_STATUS = [
    "📥 Baru Dilaporkan",
    "⚙️ Sedang Diproses",
    "✅ Sesuai Kondisi Penanganan",
    "❌ Ditunda / Tidak Dapat Ditangani"
]

URL_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ======================================
# 🔌 KONEKSI GOOGLE SHEETS
# ======================================
def koneksi_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    info = json.loads(GSHEETS_JSON)
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_url(GSHEETS_URL).sheet1

sheet = koneksi_sheet()

# ======================================
# 🛠️ FUNGSI UPDATE STATUS DI SHEET
# ======================================
def update_status(waktu_laporan: str, status_baru: str) -> bool:
    try:
        data = sheet.get_all_records()
        for baris, isi in enumerate(data, start=2):  # Baris 1 = header
            if str(isi.get("Waktu", "")).strip() == waktu_laporan.strip():
                sheet.update_cell(baris, 7, status_baru)
                sheet.update_cell(baris, 8, datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                return True
        return False
    except Exception as e:
        print(f"❌ Gagal update: {e}")
        return False

# ======================================
# 📤 KIRIM & PROSES PESAN DI GRUP
# ======================================
def kirim_pesan(chat_id: str, teks: str, tombol=None):
    requests.post(
        f"{URL_API}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": teks,
            "parse_mode": "Markdown",
            "reply_markup": json.dumps(tombol) if tombol else ""
        },
        timeout=15
    )

def proses_perintah(update):
    pesan = update.get("message", {})
    chat_id = str(pesan.get("chat", {}).get("id", ""))
    teks = pesan.get("text", "").strip()

    # Hanya tanggapi di grup yang diizinkan
    if chat_id not in IZIN_CHAT_ID:
        return

    # Perintah bantuan
    if teks == "/status":
        kirim_pesan(
            chat_id,
            "📋 *Cara Update Status Laporan:*\n\n"
            "Ketik:\n`/update [WAKTU_LAPORAN]`\n\n"
            "Contoh:\n`/update 30/06/2026 20:15:00`\n\n"
            "Waktu sama persis seperti di kolom *Waktu* laporan."
        )

    # Perintah panggil menu status
    elif teks.startswith("/update "):
        waktu = teks.replace("/update ", "").strip()
        if not waktu:
            kirim_pesan(chat_id, "⚠️ Format salah! Contoh:\n`/update 30/06/2026 20:15:00`")
            return

        # Tampilkan tombol pilihan status
        tombol = {"inline_keyboard": [[{"text": s, "callback_data": f"set|{waktu}|{s}"}] for s in DAFTAR_STATUS]}
        kirim_pesan(chat_id, f"🔧 Pilih status untuk:\n`{waktu}`", tombol)

def proses_tombol(update):
    data = update.get("callback_query", {})
    chat_id = str(data.get("message.chat.id", ""))
    pesan_id = data.get("message.message_id")
    data_aksi = data.get("data", "")

    if chat_id not in IZIN_CHAT_ID or not data_aksi.startswith("set|"):
        return

    _, waktu, status = data_aksi.split("|", 2)
    berhasil = update_status(waktu, status)

    teks_hasil = (
        f"✅ *Status Diperbarui*\n⏰ {waktu}\n📊 {status}"
        if berhasil else
        f"❌ Laporan tidak ditemukan:\n`{waktu}`"
    )

    requests.post(
        f"{URL_API}/editMessageText",
        data={"chat_id": chat_id, "message_id": pesan_id, "text": teks_hasil, "parse_mode": "Markdown"}
    )

# ======================================
# 🚀 JALANKAN BOT
# ======================================
def jalankan_bot():
    print("🤖 Bot Update Status Aktif di Grup...")
    offset = 0
    while True:
        try:
            res = requests.get(f"{URL_API}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35).json()
            if res["ok"]:
                for upd in res["result"]:
                    offset = upd["update_id"] + 1
                    if "message" in upd:
                        proses_perintah(upd)
                    elif "callback_query" in upd:
                        proses_tombol(upd)
        except Exception as e:
            print(f"⚠️ Bot error: {e} — lanjutkan...")

if __name__ == "__main__":
    jalankan_bot()