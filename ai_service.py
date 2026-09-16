import json
from datetime import datetime

from openai import OpenAI

import config

client = OpenAI(api_key=config.OPENAI_API_KEY)


def classify_transaction(text: str) -> dict:
    """Foydalanuvchi matnini (yoki ovozdan yozilgan matnni) tahlil qilib,
    daromad/xarajat sifatida tuzilgan ma'lumotga aylantiradi."""

    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = f"""
Sen Hisobchi AI — shaxsiy moliyaviy yordamchisan. Foydalanuvchi yuborgan xabarni
o'qib, undagi moliyaviy operatsiyani JSON ko'rinishida ajratib ber.

Foydalanuvchilar xabarlarni adabiy tilda emas, balki turli sheva, so'zlashuv uslubi,
qisqartma va imlo xatolari bilan yozishlari mumkin (masalan "sotib oldim" o'rniga
"oldim", "opdim", "sotvoldim"; "so'mga" o'rniga "somga", "so'mlik"; "bugun" o'rniga
"bugi", "bugun" kabi). Bunday holatlarda ham ma'noni to'g'ri tushunib, so'zning qaysi
sheva yoki qisqartmada yozilganidan qat'iy nazar, xuddi adabiy tildagidek aniq tahlil
qil. Raqamlarni so'z bilan yozilgan bo'lsa ham (masalan "o'n ming"), sonli qiymatga
o'gir.

Qoidalar:
- "turi" faqat "daromad" yoki "xarajat" bo'lishi kerak.
- "kategoriya" xarajat uchun quyidagilardan biri bo'lsin: {", ".join(config.EXPENSE_CATEGORIES)}.
- daromad uchun quyidagilardan biri bo'lsin: {", ".join(config.INCOME_CATEGORIES)}.
  Agar mos kategoriya topilmasa, eng yaqinini yoki "Boshqa xarajat"/"Boshqa daromad" ni tanla.
- "summa" faqat son (float), valyuta belgilarisiz.
- "valyuta" ISO kodda: "UZS", "USD", "EUR" va h.k. Agar aniq bo'lmasa "UZS" deb qo'y.
- "sana" YYYY-MM-DD formatida. Agar xabarda sana aytilmagan bo'lsa, bugungi sana: {today}.
- "izoh" - operatsiyaning qisqa mazmuni (masalan: "Bozordan sabzavot sotib olindi").
- Agar xabar moliyaviy operatsiya bo'lmasa (masalan salomlashish yoki savol), "turi"ni null qilib qo'y.

Faqat quyidagi JSON formatda javob qaytar, boshqa hech narsa yozma:
{{
  "turi": "daromad" | "xarajat" | null,
  "kategoriya": string | null,
  "summa": number | null,
  "valyuta": string | null,
  "sana": string | null,
  "izoh": string | null
}}
"""

    response = client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    data = json.loads(response.choices[0].message.content)

    if not data.get("sana"):
        data["sana"] = today
    if data.get("turi") and not data.get("valyuta"):
        data["valyuta"] = "UZS"

    return data


ANALYST_SYSTEM_PROMPT = """
Sen professional moliyaviy va biznes tahlilchisan (AI Maslahatchi). Senga yuklangan
hujjat matni beriladi. Vazifang - hujjatni chuqur va tanqidiy tahlil qilib, quyidagi
tuzilishda o'zbek tilida hisobot berish:

1. **Qisqacha mazmun** - hujjat nima haqida ekanligi haqida 2-3 gap.
2. **Asosiy topilmalar** - raqamlar, tendensiyalar, muhim faktlar (bullet list).
3. **Kuchli tomonlar**
4. **Xavf va zaif tomonlar** - moliyaviy risklar, nomuvofiqliklar, e'tibor talab qiladigan joylar.
5. **Tavsiyalar** - amaliy, aniq va bajarilishi mumkin bo'lgan tavsiyalar.
6. **Xulosa** - umumiy baho va keyingi qadam bo'yicha tavsiya.

Javobni Markdown formatida, aniq va professional uslubda yoz. Agar hujjat moliyaviy
hisobot bo'lmasa ham, mazmuniga mos ravishda xuddi shu tuzilishda chuqur tahlil ber.
"""


def analyze_document(document_text: str, filename: str = "") -> str:
    user_content = f"Fayl nomi: {filename}\n\nHujjat matni:\n{document_text}"

    response = client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


def analyze_image_document(image_base64: str, filename: str = "") -> str:
    """Rasm/skan qilingan hujjatni (masalan chek yoki skanerlangan sahifa) to'g'ridan-to'g'ri
    ko'rish qobiliyatiga ega model orqali tahlil qiladi."""

    response = client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Fayl nomi: {filename}. Ushbu rasmdagi hujjatni tahlil qil."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ],
            },
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


def transcribe_voice(file_path: str) -> str:
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model=config.OPENAI_TRANSCRIBE_MODEL,
            file=audio_file,
        )
    return transcript.text
