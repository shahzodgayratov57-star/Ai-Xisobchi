import json
from datetime import datetime

from openai import OpenAI

import config

client = OpenAI(api_key=config.OPENAI_API_KEY)


def _normalize_transactions(tranzaksiyalar: list[dict], today: str) -> list[dict]:
    for item in tranzaksiyalar:
        if not item.get("sana"):
            item["sana"] = today
        if not item.get("valyuta"):
            item["valyuta"] = "UZS"
        item["valyuta"] = str(item["valyuta"]).strip().upper()
    return tranzaksiyalar


def classify_transaction(text: str) -> list[dict]:
    """Foydalanuvchi matnini (yoki ovozdan yozilgan matnni) tahlil qilib,
    daromad/xarajat sifatida tuzilgan tranzaksiyalar ro'yxatiga aylantiradi.
    Bitta xabarda bir nechta operatsiya (masalan turli valyutada: ham so'm,
    ham dollar) bo'lishi mumkin, shuning uchun har doim ro'yxat qaytariladi."""

    today = datetime.now(config.TASHKENT_TZ).strftime("%Y-%m-%d")
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

Foydalanuvchilar ko'pincha buxgalteriya-uslubidagi qisqa xabarlar yozadi, unda bir
nechta summa ketma-ket, ba'zan "+" va "-" belgilari bilan, turli valyutada yozilgan
bo'ladi. Bunday xabarlarda HAR BIR valyutali summa — belgisidan (+ yoki -) qat'iy
nazar — o'sha xabarning umumiy ma'nosiga mos "turi"da (masalan "oldim"/"berdim"/
"to'ladim" — xarajat; "keldi"/"tushdi" — daromad) alohida tranzaksiya bo'lib yoziladi.
Faqat valyuta belgisi yoki nomi (so'm, $, dollar, euro va h.k.) bilan bog'liq
raqamlarni summa deb hisobla — "4 ta", "1.500 ta" kabi miqdor/dona ko'rsatuvchi
raqamlar summa EMAS, ularni e'tiborsiz qoldir (izohda qoldirish mumkin).

Misollar (faqat tuzilishni tushunish uchun, xabar matnini so'zma-so'z takrorlama):
- "-100$+850.000 caddyga 4 ta balon olindi" — bu YAGONA xarid (balon sotib olindi),
  to'lov ikki valyutada qilingan: 2 ta xarajat tranzaksiyasi qaytarilishi kerak —
  biri summa=100, valyuta=USD; ikkinchisi summa=850000, valyuta=UZS. "4 ta" — miqdor,
  summa emas.
- "-60.000.000+1.200$ avaz pulcbiga berdim" — 2 ta xarajat tranzaksiyasi: summa=60000000
  valyuta=UZS va summa=1200 valyuta=USD (ikkalasi ham "berdim" — xarajat).
- "-6.000$ toirakamga berdik 1.500 ta termostatga ost 27.934.000" — 2 ta xarajat
  tranzaksiyasi: summa=6000 valyuta=USD va summa=27934000 valyuta=UZS. "1.500 ta" —
  miqdor, summa emas, uchinchi tranzaksiya yaratilmaydi.

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

    return _normalize_transactions(tranzaksiyalar, today)


IMAGE_TRANSACTION_SYSTEM_PROMPT_TEMPLATE = """
Sen Hisobchi AI — moliyaviy yordamchisan. Senga yuborilgan RASMni diqqat bilan
o'qib chiq — bu qo'lda yozilgan hisob-kitob varag'i, buxgalteriya jadvali yoki
shunga o'xshash yozuv bo'lishi mumkin, unda summalar "prixod"/"приход" (kirim)
va "rasxod"/"расход" (chiqim) deb ikki toifaga ajratilgan bo'ladi.

Rasmda "prixod"/"приход" (yoki "kirim", "tushum") deb belgilangan har bir summa —
"daromad" turidagi alohida tranzaksiya. "rasxod"/"расход" (yoki "chiqim") deb
belgilangan har bir summa — "xarajat" turidagi alohida tranzaksiya. Rasmdagi
HAR BIR aniq summani shu tarzda alohida tranzaksiya sifatida ro'yxatga qo'sh.
Agar biror summaning turi (prixod yoki rasxod ekanligi) rasmdan aniq bo'lmasa,
uni ro'yxatga QO'SHMA — noaniq summani hech qachon taxmin qilib yozma.

Qoidalar (har bir tranzaksiya uchun):
- "turi" faqat "daromad" yoki "xarajat" bo'lishi kerak.
- "kategoriya" xarajat uchun quyidagilardan biri bo'lsin: {expense_categories}.
- daromad uchun quyidagilardan biri bo'lsin: {income_categories}.
  Agar mos kategoriya topilmasa yoki rasmda ko'rsatilmagan bo'lsa, "Boshqa xarajat"/
  "Boshqa daromad" ni tanla.
- "summa" faqat son (float), valyuta belgilarisiz.
- "valyuta" ISO kodda: "UZS", "USD", "EUR" va h.k. Agar aniq bo'lmasa "UZS" deb qo'y.
- "sana" YYYY-MM-DD formatida. Agar rasmda sana ko'rsatilmagan bo'lsa, bugungi sana: {today}.
- "izoh" - rasmdagi shu yozuvning qisqa mazmuni (masalan qatorda yozilgan izoh matni).

Agar rasmda umuman moliyaviy yozuv (prixod/rasxod summasi) bo'lmasa, "tranzaksiyalar"
ni bo'sh ro'yxat ([]) qilib qo'y.

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


def classify_transactions_from_image(image_base64: str, filename: str = "") -> list[dict]:
    """Rasmdagi (masalan qo'lda yozilgan kunlik hisob-kitob varag'i) prixod/rasxod
    yozuvlarini o'qib, tranzaksiyalar ro'yxatiga aylantiradi."""

    today = datetime.now(config.TASHKENT_TZ).strftime("%Y-%m-%d")
    system_prompt = IMAGE_TRANSACTION_SYSTEM_PROMPT_TEMPLATE.format(
        expense_categories=", ".join(config.EXPENSE_CATEGORIES),
        income_categories=", ".join(config.INCOME_CATEGORIES),
        today=today,
    )

    response = client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Fayl nomi: {filename}. Ushbu rasmdagi prixod/rasxod yozuvlarini ajratib ber.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    data = json.loads(response.choices[0].message.content)
    tranzaksiyalar = data.get("tranzaksiyalar") or []

    return _normalize_transactions(tranzaksiyalar, today)


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
