# TradingView (Premium) → Telegram Webhook Bot

Premium reja webhooklarni qo'llab-quvvatlaydi, shuning uchun bu eng
tez va ishonchli yo'l: TradingView alert shartingiz bajarilgan
zahoti to'g'ridan-to'g'ri serveringizga so'rov yuboradi, server esa
buni darhol Telegramga forward qiladi (kechikish odatda 1 soniyadan
kam).

## 1-qadam: Telegram bot yaratish

1. Telegram'da **@BotFather**'ga `/newbot` yuboring.
2. Bot nomi va username so'raydi (username "bot" bilan tugashi
   kerak, masalan `XauusdAlertBot`).
3. Sizga token beriladi — saqlab qo'ying.

## 2-qadam: Chat ID olish

1. Botingizga Telegram'da bironta xabar yozing.
2. Brauzerda: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Javobdagi `"chat":{"id":123456789,...}` — shu raqam
   `TELEGRAM_CHAT_ID`.

## 3-qadam: TradingView account'da 2FA yoqish

TradingView webhook alertlari faqat **2 bosqichli tasdiqlash (2FA)**
yoqilgan bo'lsa ishlaydi. Profil sozlamalaridan yoqib qo'ying, aks
holda webhook maydoni bo'sh/o'chiq ko'rinadi.

## 4-qadam: Serverga joylashtirish (Railway tavsiya etiladi)

Bu safar server doimiy ishlab, tashqi internetdan kira oladigan
ochiq URL'ga ega bo'lishi kerak (TradingView shu URL'ga so'rov
yuboradi).

1. https://railway.app — GitHub orqali ro'yxatdan o'ting.
2. Bu loyihani GitHub repo qilib yuklang, Railway'da
   "New Project" → "Deploy from GitHub repo".
3. "Variables" bo'limida `.env.example` dagi qiymatlarni real
   ma'lumotlar bilan kiriting. `WEBHOOK_SECRET` o'rniga o'zingiz
   uzun, tasodifiy so'z/raqam to'plamini yozing (masalan parol
   generatori bilan yaratilgan satr) — bu hech kim taxmin qila
   olmaydigan maxfiy kalit bo'lishi kerak, aks holda boshqalar
   ham botingizga soxta xabar yuborib qoladi.
4. Deploy tugagach, Railway sizga ochiq domen beradi, masalan:
   `https://tv-webhook-bot.up.railway.app`
5. Sizning to'liq webhook manzilingiz quyidagicha bo'ladi:
   `https://tv-webhook-bot.up.railway.app/webhook/<WEBHOOK_SECRET>`

## 5-qadam: TradingView'da alert sozlash

1. Grafikda indikatorni qo'ying, qo'ng'iroq belgisi (Create Alert)
   tugmasini bosing.
2. **Condition**: indikatordagi shartlardan birini tanlang — bu
   kodda allaqachon tayyor `alertcondition()` lar mavjud, masalan:
   - "ENTRY LAOL BEAR in SCALP/INTRA"
   - "ENTRY LAOL BULL in SCALP/INTRA"
   - "SCALP LAOL BEAR in INTRA"
   - "SCALP LAOL BULL in INTRA"
   Bulardan tashqari kodda `alert()` orqali ham xabarlar bor
   (masalan "BULL CONFIRMED", "FINAL ENTRY BEAR") — bular uchun
   alert turi "Any alert() function call" qilib tanlanadi.
3. **Notifications** bo'limida **"Webhook URL"**ni yoqing va
   4-qadamdagi to'liq manzilni kiriting.
4. **Message** maydonini bo'sh qoldirsangiz, indikatordagi
   `alert()` chaqiruvida yozilgan matn (masalan
   "BULL CONFIRMED | SL=... | Entry=...") avtomatik yuboriladi.
5. Saqlang.

Shu bilan tugadi — shart bajarilgan zahoti Telegramingizga xabar
keladi.

## 6-qadam: Tekshirish (test)

Deploy qilingandan keyin, brauzerda serveringiz manzilini ochib
ko'ring (masalan `https://tv-webhook-bot.up.railway.app/`) — "TV ->
Telegram webhook server ishlayapti." degan matn chiqishi kerak.
Bu server ishlab turganini bildiradi.

Haqiqiy testni TradingView'da "Test alert" funksiyasi orqali yoki
indikator shartini real grafikda kutib qilishingiz mumkin.

## Xavfsizlik haqida eslatma

- `WEBHOOK_SECRET`ni hech kimga bermang va GitHub repo'ni **public**
  qilsangiz, uni kodga yozib qo'ymang — faqat Railway "Variables"
  bo'limida saqlang (`.env` fayl ham repo'ga tushib qolmasligi
  kerak, `.gitignore`ga qo'shing).
- Agar kerak bo'lsa, kelajakda IP-whitelist yoki imzo tekshirish
  qo'shib xavfsizlikni kuchaytirish mumkin.
