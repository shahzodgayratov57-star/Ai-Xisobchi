# Hisobchi AI — Telegram bot

Shaxsiy moliyaviy yordamchi bot: matn/ovozli xabarlarni AI orqali tahlil qilib
daromad/xarajat sifatida Google Sheets'ga yozadi, buyruq bilan Excel hisobot
tayyorlaydi, va yuklangan hujjatlarni professional tahlilchi sifatida chuqur
tahlil qiladi.

## 1. Talablar

- Python 3.11+
- Telegram bot tokeni ([@BotFather](https://t.me/BotFather) orqali)
- OpenAI API kaliti ([platform.openai.com](https://platform.openai.com))
- Google Cloud xizmat hisobi (service account) — Google Sheets uchun

## 2. O'rnatish

```bash
pip install -r requirements.txt
```

## 3. Google Sheets sozlash

1. [Google Cloud Console](https://console.cloud.google.com/)da yangi loyiha oching.
2. **Google Sheets API** va **Google Drive API**ni yoqing.
3. **IAM & Admin → Service Accounts** bo'limida yangi service account yarating.
4. Uning uchun JSON kalit yarating va yuklab oling, loyiha papkasiga
   `credentials.json` nomi bilan saqlang.
5. Google Sheets'da yangi jadval yarating, uni service account emailiga
   (masalan `xxx@yyy.iam.gserviceaccount.com`) **Editor** huquqi bilan ulashing.
6. Jadval URL'idagi ID qismini nusxalab oling:
   `https://docs.google.com/spreadsheets/d/SHEET_ID_SHU_YERDA/edit`

## 4. `.env` faylini sozlash

`.env.example`ni `.env` deb nusxalang va qiymatlarni to'ldiring:

```bash
cp .env.example .env
```

- `TELEGRAM_BOT_TOKEN` — BotFather bergan token
- `OPENAI_API_KEY` — OpenAI API kaliti
- `GOOGLE_SHEETS_CREDENTIALS_FILE` — `credentials.json` fayl yo'li
- `GOOGLE_SHEET_ID` — 3-bosqichdagi jadval ID'si

## 5. Ishga tushirish

```bash
python main.py
```

## 6. Foydalanish

- **Matn yuborish**: "bozordan 50000 so'mga sabzavot oldim" — bot avtomatik
  daromad/xarajat turini, kategoriyasini va summasini aniqlab, Google
  Sheets'ga yozadi.
- **Ovozli xabar**: xuddi shu tarzda, avval Whisper orqali matnga o'giradi,
  keyin xuddi matn kabi tahlil qiladi.
- **Hujjat/rasm yuborish** (PDF, DOCX, TXT, JPG/PNG): AI Maslahatchi rolida
  chuqur tahlil (mazmun, topilmalar, risklar, tavsiyalar) qaytaradi.
- **`/export`, `/hisobot` yoki `/excel`**: barcha yozuvlarni `.xlsx` fayl
  ko'rinishida yuklab beradi (jami bo'yicha xulosa varag'i bilan).

## Loyiha tuzilishi

- `main.py` — Telegram handler'lar va botni ishga tushirish
- `ai_service.py` — OpenAI orqali kategoriyalash, hujjat tahlili, ovozni matnga o'girish
- `sheets_service.py` — Google Sheets bilan o'qish/yozish
- `excel_service.py` — jadvalni `.xlsx` ga eksport qilish
- `document_service.py` — PDF/DOCX/TXT fayllardan matn ajratib olish
- `config.py` — muhit o'zgaruvchilari va sozlamalar
