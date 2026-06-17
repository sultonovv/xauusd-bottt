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
import logging

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

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def send_telegram_message(text: str) -> None:
    if not text:
        text = "(bo'sh xabar keldi)"
    if len(text) > 3900:
        text = text[:3900] + "\n...(qisqartirildi)"
    try:
        resp = requests.post(
            TELEGRAM_API_URL,
            data={"chat_id": CHAT_ID, "text": text},
            timeout=10,
        )
        if resp.status_code != 200:
            log.error("Telegram API xatosi: %s - %s", resp.status_code, resp.text)
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
    send_telegram_message(message)

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return "TV -> Telegram webhook server ishlayapti.", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
