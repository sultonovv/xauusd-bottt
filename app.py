"""
TradingView Webhook -> Telegram forwarder

Ishlash mantig'i:
1. TradingView'da alert yaratasiz, "Webhook URL" qismiga
   https://<sizning-domeningiz>/webhook/<SECRET>
   manzilini yozasiz.
2. Alert shart bajarilganda TradingView shu manzilga POST so'rov
   (alert matnini) yuboradi.
3. Bu server so'rovni qabul qilib, ichidagi maxfiy kalitni (SECRET)
   tekshiradi va xabarni Telegram botingizga forward qiladi.

Kerakli environment variable'lar:
    TELEGRAM_BOT_TOKEN   - @BotFather bergan token
    TELEGRAM_CHAT_ID     - xabar yuboriladigan chat ID
    WEBHOOK_SECRET       - o'zingiz tanlagan maxfiy so'z/raqam
                            (URL ichida ishlatiladi, taxmin qilib
                            bo'lmaydigan uzun va tasodifiy bo'lsin)
    PORT                 - hosting platforma o'zi belgilaydi (ixtiyoriy)
"""

import os
import re
import html
import logging
from datetime import datetime, timezone, timedelta

from flask import Flask, request, jsonify
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("tv-webhook-bot")

app = Flask(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

# Xabarda ko'rsatiladigan savdo instrumenti nomi (xohlasangiz o'zgartiring)
ALERT_SYMBOL = os.environ.get("ALERT_SYMBOL", "XAUUSD")
# Vaqtni shu zonada ko'rsatamiz (Toshkent = UTC+5)
LOCAL_TZ = timezone(timedelta(hours=5))

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
BOT_START_TIME = datetime.now(LOCAL_TZ)


def format_alert_message(raw_text: str) -> str:
    """
    Indikatordan kelgan xom matnni (masalan
    'BULL CONFIRMED | SL=4250.12 | Entry=4255.30') chiroyli,
    o'qish oson Telegram xabariga aylantiradi.
    """
    text = (raw_text or "").strip()
    if not text:
        return "ℹ️ <b>Bo'sh xabar keldi</b>"

    upper = text.upper()

    if "BULL" in upper or "BUY" in upper:
        emoji = "🟢"
        direction_label = "BUY / BULL"
    elif "BEAR" in upper or "SELL" in upper:
        emoji = "🔴"
        direction_label = "SELL / BEAR"
    else:
        emoji = "ℹ️"
        direction_label = None

    # "SL=..." va "Entry=..." qiymatlarini ajratib olamiz (mavjud bo'lsa)
    sl_match = re.search(r"SL\s*=\s*([\d.]+)", text, re.IGNORECASE)
    entry_match = re.search(r"Entry\s*=\s*([\d.]+)", text, re.IGNORECASE)

    # "|" belgisigacha bo'lgan qism - signal nomi/sarlavhasi
    title = text.split("|")[0].strip()
    title_safe = html.escape(title)

    now_str = datetime.now(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")

    if direction_label:
        header = f"{emoji} <b>{direction_label}</b> — {title_safe}"
    else:
        header = f"{emoji} <b>{title_safe}</b>"

    lines = [header, f"📊 Symbol: <b>{ALERT_SYMBOL}</b>"]
    if entry_match:
        lines.append(f"🎯 Entry: <b>{entry_match.group(1)}</b>")
    if sl_match:
        lines.append(f"🛑 SL: <b>{sl_match.group(1)}</b>")
    lines.append(f"🕐 Vaqt: {now_str} (Toshkent)")

    return "\n".join(lines)


def send_telegram_message(text: str) -> None:
    if not text:
        text = "(bo'sh xabar keldi)"
    if len(text) > 3900:
        text = text[:3900] + "\n...(qisqartirildi)"
    try:
        resp = requests.post(
            TELEGRAM_API_URL,
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code != 200:
            log.error("Telegram API xatosi: %s - %s", resp.status_code, resp.text)
            # HTML formatlashda xato bo'lsa (masalan teglar noto'g'ri yopilgan),
            # formatlamasdan oddiy matn sifatida qayta yuborib ko'ramiz.
            plain = re.sub(r"<[^>]+>", "", text)
            requests.post(
                TELEGRAM_API_URL,
                data={"chat_id": CHAT_ID, "text": plain},
                timeout=10,
            )
        else:
            log.info("Telegramga yuborildi: %s", text[:80].replace("\n", " "))
    except requests.RequestException as e:
        log.error("Telegramga yuborishda tarmoq xatosi: %s", e)


@app.route("/webhook/<secret>", methods=["POST"])
def webhook(secret):
    if secret != WEBHOOK_SECRET:
        log.warning("Noto'g'ri secret bilan urinish: %s", secret)
        return jsonify({"error": "unauthorized"}), 403

    # TradingView xabarni oddiy matn yoki JSON sifatida yuborishi mumkin —
    # ikkisini ham qo'llab-quvvatlaymiz.
    if request.is_json:
        data = request.get_json(silent=True) or {}
        message = data.get("message") or data.get("text") or str(data)
    else:
        message = request.get_data(as_text=True)

    log.info("Webhook qabul qilindi: %s", message[:200].replace("\n", " "))
    formatted = format_alert_message(message)
    send_telegram_message(formatted)

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return "TV -> Telegram webhook server ishlayapti.", 200


@app.route("/telegram/<secret>", methods=["POST"])
def telegram_webhook(secret):
    """
    Telegram foydalanuvchi botga xabar/komanda yozganda shu manzilga
    so'rov yuboradi (setWebhook orqali ulanadi - /admin/setup ga qarang).
    """
    if secret != WEBHOOK_SECRET:
        log.warning("Telegram webhook'da noto'g'ri secret: %s", secret)
        return jsonify({"error": "unauthorized"}), 403

    update = request.get_json(silent=True) or {}
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    incoming_chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not incoming_chat_id or not text:
        return jsonify({"status": "ignored"}), 200

    command = text.split()[0].lower()

    if command == "/start":
        reply = (
            f"👋 Salom! Men {ALERT_SYMBOL} savdo signal botiman.\n\n"
            "TradingView indikatoridan signal kelganda, sizga avtomatik "
            "xabar yuboraman. Hech narsa qilishingiz shart emas.\n\n"
            "Buyruqlar:\n"
            "/help — yordam va qo'llanma\n"
            "/status — bot holatini tekshirish"
        )
    elif command == "/help":
        reply = (
            "ℹ️ <b>Qo'llanma</b>\n\n"
            f"Bu bot TradingView'dagi {ALERT_SYMBOL} indikatoridan kelgan "
            "savdo signallarini avtomatik sizga yuboradi.\n\n"
            "🟢 — BUY/BULL signal\n"
            "🔴 — SELL/BEAR signal\n\n"
            "Buyruqlar:\n"
            "/start — botni qayta ishga tushirish\n"
            "/status — bot ishlab turganini tekshirish"
        )
    elif command == "/status":
        uptime = datetime.now(LOCAL_TZ) - BOT_START_TIME
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        reply = (
            "✅ Bot ishlab turibdi.\n"
            f"⏱ Ishlagan vaqti: {hours} soat {minutes} daqiqa\n"
            f"📊 Symbol: <b>{ALERT_SYMBOL}</b>"
        )
    else:
        reply = "Noma'lum buyruq. /help yozib ko'ring."

    try:
        requests.post(
            TELEGRAM_API_URL,
            data={"chat_id": incoming_chat_id, "text": reply, "parse_mode": "HTML"},
            timeout=10,
        )
    except requests.RequestException as e:
        log.error("Komandaga javob yuborishda xato: %s", e)

    return jsonify({"status": "ok"}), 200


@app.route("/admin/setup/<secret>", methods=["GET"])
def admin_setup(secret):
    """
    Bir martalik sozlash: bot buyruqlar menyusini o'rnatadi va Telegram
    webhook'ni ulaydi. Deploy qilingandan keyin shu manzilni brauzerda
    bir marta ochish kifoya:
        https://<domen>/admin/setup/<WEBHOOK_SECRET>
    """
    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 403

    base_url = request.url_root.rstrip("/")
    telegram_webhook_url = f"{base_url}/telegram/{WEBHOOK_SECRET}"

    results = {}

    commands = [
        {"command": "start", "description": "Botni ishga tushirish"},
        {"command": "help", "description": "Yordam va qo'llanma"},
        {"command": "status", "description": "Bot holatini tekshirish"},
    ]
    resp1 = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands",
        json={"commands": commands},
        timeout=10,
    )
    results["setMyCommands"] = resp1.json()

    resp2 = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        data={"url": telegram_webhook_url},
        timeout=10,
    )
    results["setWebhook"] = resp2.json()

    return jsonify(results), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
