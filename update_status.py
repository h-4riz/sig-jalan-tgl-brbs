import requests
import datetime
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import streamlit as st

# --------------------------
# KONFIGURASI (SAMA DENGAN UTAMA)
# --------------------------
# Ambil kredensial dari secrets yang sama
TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID_IZIN = str(st.secrets.get("TELEGRAM_CHAT_ID", "")).strip()
URL_API = f"https://api.telegram.org/bot{TOKEN}"

# Status yang tersedia
DAFTAR_STATUS = [
    "📥 Baru Dilaporkan",
    "⚙️ Sedang Diproses",
    "✅ Sesuai Kondisi Penanganan",
    "❌ Ditunda / Tidak Dapat Ditangani"
]

# --------------------------
# FUNGSI UPDATE KE GOOGLE SHEETS
# --------------------------
def perbarui_status_laporan_gsheets(waktu_laporan: str, status_baru: str) -> bool:
    """Update status laporan di Google Sheets"""
    try:
        conn = GSheetsConnection("gsheets")
        df = conn.read(ttl=0)
        if df.empty:
            return False

        # Cari baris yang cocok berdasarkan waktu lapor
        kondisi = df["Waktu"].astype(str).str.strip() == waktu_laporan.strip()
        if kondisi.any():
            df.loc[kondisi, "Status"] = status_baru
            df.loc[kondisi, "Terakhir_Diperbarui"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            conn.update(data=df)
            return True
        return False
    except Exception as e:
        print(f"❌ Gagal update: {e}")
        return False

# --------------------------
# FUNGSI KIRIM BALASAN KE TELEGRAM
# --------------------------
def kirim_pesan(chat_id: str, teks: str, reply_markup=None):
    requests.post(
        f"{URL_API}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": teks,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup or {}
        },
        timeout=15
    )

# --------------------------
# PROSES PERINTAH DAN TOMBOL
# --------------------------
def proses_pesan(update):
    pesan = update.get("message", {})
    chat_id = str(pesan.get("chat", {}).get("id", ""))
    teks = pesan.get("text", "").strip()

    # Hanya izinkan admin/chat tertentu
    if chat_id != CHAT_ID_IZIN:
        kirim_pesan(chat_id, "❌ Tidak memiliki izin akses.")
        return

    # Perintah mulai
    if teks == "/status":
        kirim_pesan(
            chat_id,
            "📝 *Cara Update Status:*\nKetik:\n`/update [WAKTU_LAPORAN]`\nContoh:\n`/update 30/06/2026 20:15:00`"
        )

    # Perintah update
    elif teks.startswith("/update "):
        waktu_cari = teks.replace("/update ", "").strip()
        if not waktu_cari:
            kirim_pesan(chat_id, "⚠️ Masukkan waktu laporan.\nContoh: `/update 30/06/2026 20:15:00`")
            return

        # Tampilkan tombol pilihan status
        tombol = {
            "inline_keyboard": [
                [{"text": s, "callback_data": f"set|{waktu_cari}|{s}"}] for s in DAFTAR_STATUS
            ]
        }
        kirim_pesan(chat_id, f"🔧 Pilih status baru untuk:\n`{waktu_cari}`", reply_markup=tombol)

def proses_callback(update):
    data = update.get("callback_query", {})
    chat_id = str(data.get("message", {}).get("chat", {}).get("id", ""))
    callback_data = data.get("data", "")
    pesan_id = data.get("message", {}).get("message_id")

    if chat_id != CHAT_ID_IZIN:
        return

    if callback_data.startswith("set|"):
        _, waktu_lapor, status_baru = callback_data.split("|", 2)
        berhasil = perbarui_status_laporan_gsheets(waktu_lapor, status_baru)

        if berhasil:
            teks_hasil = f"✅ *Status Berhasil Diperbarui*\n⏰ Waktu: `{waktu_lapor}`\n📊 Status: {status_baru}"
        else:
            teks_hasil = f"❌ Laporan tidak ditemukan: `{waktu_lapor}`"

        requests.post(
            f"{URL_API}/editMessageText",
            data={
                "chat_id": chat_id,
                "message_id": pesan_id,
                "text": teks_hasil,
                "parse_mode": "Markdown"
            }
        )

# --------------------------
# JALANKAN BOT (POLLING)
# --------------------------
def jalankan_bot():
    print("🤖 Bot update status berjalan...")
    offset = 0
    while True:
        try:
            res = requests.get(f"{URL_API}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35).json()
            if res.get("ok"):
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update:
                        proses_pesan(update)
                    elif "callback_query" in update:
                        proses_callback(update)
        except Exception as e:
            print(f"⚠️ Bot error: {e}, lanjutkan...")
            continue

if __name__ == "__main__":
    jalankan_bot()