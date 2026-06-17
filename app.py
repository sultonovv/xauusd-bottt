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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
