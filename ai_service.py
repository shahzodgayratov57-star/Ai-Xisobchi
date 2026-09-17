import json
from datetime import datetime

from openai import OpenAI

import config

client = OpenAI(api_key=config.OPENAI_API_KEY)


def classify_transaction(text: str) -> list[dict]:
    """Foydalanuvchi matnini (yoki ovozdan yozilgan matnni) tahlil qilib,
    daromad/xarajat sifatida tuzilgan tranzaksiyalar ro'yxatiga aylantiradi.
    Bitta xabarda bir nechta operatsiya (masalan turli valyutada: ham so'm,
    ham dollar) bo'lishi mumkin, shuning uchun har doim ro'yxat qaytariladi."""

    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = f"""
Sen Hisobchi AI — shaxsiy moliyaviy yordamchisan. Foydalanuvchi yuborgan xabarni
o'qib, undagi moliyaviy operatsiya(lar)ni JSON ko'rinishida ajratib ber.

Foydalanuvchilar xabarlarni adabiy tilda emas, balki turli sheva, so'zlashuv uslubi,
qisqartma va imlo xatolari bilan yozishlari mumkin (masalan "sotib oldim" o'rniga
"oldim", "opdim", "sotvoldim"; "so'mga" o'rniga "somga", "so'mlik"; "bugun" o'rniga
"bugi", "bugun" kabi). Bunday holatlarda ham ma'noni to'g'ri tushunib, so'zning qaysi
sheva yoki qisqartmada yozilganidan qat'iy nazar, xuddi adabiy tildagidek aniq tahlil
qil. Raqamlarni so'z bilan yozilgan bo'lsa ham (masalan "o'n ming"), sonli qiymatga
o'gir.

Bitta xabarda bir nechta moliyaviy operatsiya bo'lishi mumkin — masalan bir qismi
so'mda, bir qismi dollarda ("bozorga 50000 so'm va do'kondan 3 dollarlik narsa
oldim" kabi), yoki bir nechta alohida xarid/tushum sanab o'tilgan bo'lishi mumkin.
Bunday hollarda HAR BIR operatsiyani alohida tranzaksiya sifatida ro'yxatga qo'sh —
hech birini yo'qotib qo'ymasdan va hech birini boshqasi bilan qo'shib yubormasdan.

Qoidalar (har bir tranzaksiya uchun):
- "turi" faqat "daromad" yoki "xarajat" bo'lishi kerak.
- Agar xabarda "rasxod" (yoki "расход") so'zi bilan summa yozilgan bo'lsa, bu doim
  "xarajat" (pul chiqimi) hisoblanadi. Agar "prixod" (yoki "приход") so'zi bilan summa
  yozilgan bo'lsa, bu doim "daromad" (pul kirimi) hisoblanadi — bu so'zlar shevada/
  so'zlashuvda tez-tez ishlatiladi va ustuvor qoida hisoblanadi.
- "kategoriya" xarajat uchun quyidagilardan biri bo'lsin: {", ".join(config.EXPENSE_CATEGORIES)}.
- daromad uchun quyidagilardan biri bo'lsin: {", ".join(config.INCOME_CATEGORIES)}.
  Agar mos kategoriya topilmasa, eng yaqinini yoki "Boshqa xarajat"/"Boshqa daromad" ni tanla.
- "summa" faqat son (float), valyuta belgilarisiz.
- "valyuta" ISO kodda: "UZS", "USD", "EUR" va h.k. Agar aniq bo'lmasa "UZS" deb qo'y.
- "sana" YYYY-MM-DD formatida. Agar xabarda sana aytilmagan bo'lsa, bugungi sana: {today}.
- "izoh" - operatsiyaning qisqa mazmuni (masalan: "Bozordan sabzavot sotib olindi").

Agar xabarda umuman moliyaviy operatsiya bo'lmasa (masalan salomlashish yoki savol),
"tranzaksiyalar" ni bo'sh ro'yxat ([]) qilib qo'y.

Faqat quyidagi JSON formatda javob qaytar, boshqa hech narsa yozma:
{{
  "tranzaksiyalar": [
    {{
      "turi": "daromad" | "xarajat",
      "kategoriya": string,
      "summa": number,
      "valyuta": string,
      "sana": string | null,
      "izoh": string | null
    }}
  ]
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
    tranzaksiyalar = data.get("tranzaksiyalar") or []

    for item in tranzaksiyalar:
        if not item.get("sana"):
            item["sana"] = today
        if not item.get("valyuta"):
            item["valyuta"] = "UZS"
        item["valyuta"] = str(item["valyuta"]).strip().upper()

    return tranzaksiyalar


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
