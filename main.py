import functools
import logging
import os
from datetime import datetime

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import ai_service
import config
import document_service
import excel_service
import sheets_service

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def _is_allowed(update: Update) -> bool:
    if config.ALLOWED_TELEGRAM_USER_ID is None and config.ALLOWED_GROUP_CHAT_ID is None:
        return True

    if (
        config.ALLOWED_TELEGRAM_USER_ID is not None
        and update.effective_user
        and update.effective_user.id == config.ALLOWED_TELEGRAM_USER_ID
    ):
        return True

    if (
        config.ALLOWED_GROUP_CHAT_ID is not None
        and update.effective_chat
        and update.effective_chat.id == config.ALLOWED_GROUP_CHAT_ID
    ):
        return True

    return False


def restricted(handler):
    """Botni faqat egasining shaxsiy chatiga va/yoki ruxsat etilgan guruhga cheklaydi."""

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not _is_allowed(update):
            logger.warning(
                "Ruxsatsiz urinish: user=%s chat=%s",
                update.effective_user.id if update.effective_user else None,
                update.effective_chat.id if update.effective_chat else None,
            )
            await update.message.reply_text("Kechirasiz, bu bot faqat egasi/ruxsat etilgan guruh uchun mo'ljallangan.")
            return
        return await handler(update, context)

    return wrapper

WELCOME_TEXT = (
    "\U0001F4B0 *Hisobchi AI*ga xush kelibsiz!\n\n"
    "Men sizning shaxsiy moliyaviy yordamchingizman. Menga:\n\n"
    "1️⃣ *Matn* yoki *ovozli xabar* yuboring — masalan: "
    "\"bozordan 50000 so'mga sabzavot oldim\" yoki \"maoshim 3 million tushdi\". "
    "Men uni avtomatik tahlil qilib, kerakli bo'limga (daromad/xarajat) joylashtiraman "
    "va Google Sheets jadvalingizga yozib qo'yaman.\n\n"
    "2️⃣ *Hujjat yoki rasm* yuboring (PDF, Word, matn fayl yoki skan/chek rasmi) — "
    "men professional tahlilchi sifatida uni chuqur tahlil qilib beraman.\n\n"
    "Buyruqlar:\n"
    "/export — barcha yozuvlarni Excel fayl ko'rinishida olish\n"
    "/help — yordam"
)


@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")


@restricted
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")


def _user_label(update: Update) -> str:
    user = update.effective_user
    return f"@{user.username}" if user.username else user.full_name


def _is_group_chat(update: Update) -> bool:
    return bool(
        config.ALLOWED_GROUP_CHAT_ID is not None
        and update.effective_chat
        and update.effective_chat.id == config.ALLOWED_GROUP_CHAT_ID
    )


async def _save_transactions(
    update: Update, transactions: list[dict], source_text: str, share_izoh: bool = True
) -> bool:
    """Aniqlangan tranzaksiyalar ro'yxatini jadvalga yozadi. Guruhda hech qanday
    javob yozilmaydi (jim saqlanadi), shaxsiy chatda esa har biri uchun tasdiq
    xabari yuboriladi. Kamida bitta tranzaksiya bo'lsa True qaytaradi."""

    if not transactions:
        return False

    now = datetime.now(config.TASHKENT_TZ)
    saved_rows = []
    has_xarajat = False
    # Bitta xabarda bir nechta tranzaksiya bo'lsa (masalan 2 xil valyutada),
    # ularning hammasi bir manbadan kelganini bilish uchun "izoh" ustuniga ham
    # "original xabar"dagi bilan bir xil matn yoziladi. Rasmdan chiqarilgan
    # ro'yxatda esa har bir qatorning o'z izohi saqlanadi (share_izoh=False).
    shared_izoh = source_text if (share_izoh and len(transactions) > 1) else None
    manba = "Guruh" if _is_group_chat(update) else "Shaxsiy"
    for data in transactions:
        row = {
            "sana": data.get("sana") or now.strftime("%Y-%m-%d"),
            "vaqt": now.strftime("%H:%M:%S"),
            "foydalanuvchi": _user_label(update),
            "turi": data["turi"],
            "kategoriya": data.get("kategoriya") or "Boshqa",
            "summa": data.get("summa") or 0,
            "valyuta": data.get("valyuta") or "UZS",
            "izoh": shared_izoh if shared_izoh is not None else (data.get("izoh") or ""),
            "original_xabar": source_text,
            "manba": manba,
        }
        sheets_service.append_transaction(row)
        saved_rows.append(row)
        if row["turi"] == "xarajat":
            has_xarajat = True

    if has_xarajat:
        sheets_service.update_expense_chart()

    if not _is_group_chat(update):
        for row in saved_rows:
            emoji = "\U0001F4B5" if row["turi"] == "daromad" else "\U0001F4B8"
            await update.message.reply_text(
                f"{emoji} *{row['turi'].capitalize()}* saqlandi!\n"
                f"Kategoriya: {row['kategoriya']}\n"
                f"Summa: {row['summa']:,} {row['valyuta']}\n"
                f"Izoh: {row['izoh']}\n"
                f"Sana: {row['sana']}",
                parse_mode="Markdown",
            )
    return True


async def _save_and_reply_transaction(update: Update, text: str) -> bool:
    """Matnni tahlil qilib, undagi moliyaviy operatsiya(lar)ni jadvalga yozadi.
    Bitta xabarda bir nechta operatsiya (masalan turli valyutada) bo'lishi
    mumkin — har biri alohida qator sifatida saqlanadi. Kamida bitta operatsiya
    aniqlangan bo'lsa True qaytaradi."""

    transactions = ai_service.classify_transaction(text)
    return await _save_transactions(update, transactions, text)


@restricted
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        handled = await _save_and_reply_transaction(update, text)
        if not handled and not _is_group_chat(update):
            await update.message.reply_text(
                "Bu xabarni moliyaviy operatsiya sifatida aniqlay olmadim. "
                "Masalan: \"taksiga 25000 so'm sarfladim\" kabi yozib ko'ring, "
                "yoki tahlil uchun hujjat/rasm yuboring."
            )
    except Exception:
        logger.exception("Matnni qayta ishlashda xatolik")
        await update.message.reply_text("Kechirasiz, xabarni qayta ishlashda xatolik yuz berdi.")


@restricted
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(ChatAction.TYPING)
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)

    local_path = os.path.join(config.TEMP_DIR, f"voice_{voice.file_unique_id}.ogg")
    await tg_file.download_to_drive(local_path)

    try:
        text = ai_service.transcribe_voice(local_path)
        await update.message.reply_text(f"\U0001F3A4 Eshitdim: _{text}_", parse_mode="Markdown")

        handled = await _save_and_reply_transaction(update, text)
        if not handled:
            await update.message.reply_text(
                "Bu ovozli xabarni moliyaviy operatsiya sifatida aniqlay olmadim."
            )
    except Exception:
        logger.exception("Ovozli xabarni qayta ishlashda xatolik")
        await update.message.reply_text("Kechirasiz, ovozli xabarni qayta ishlashda xatolik yuz berdi.")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


@restricted
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(ChatAction.TYPING)
    document = update.message.document
    tg_file = await context.bot.get_file(document.file_id)

    local_path = os.path.join(config.TEMP_DIR, document.file_name)
    await tg_file.download_to_drive(local_path)

    await update.message.reply_text("\U0001F50D Hujjat qabul qilindi, chuqur tahlil qilinmoqda...")

    try:
        if document_service.is_image(local_path):
            image_b64 = document_service.image_to_base64(local_path)
            analysis = ai_service.analyze_image_document(image_b64, document.file_name)
        else:
            text = document_service.extract_text(local_path)
            if not text:
                await update.message.reply_text(
                    "Kechirasiz, ushbu fayl formatidan matn ajratib ololmadim "
                    "(PDF, DOCX yoki TXT formatlarini qo'llab-quvvatlayman)."
                )
                return
            analysis = ai_service.analyze_document(text, document.file_name)

        await _send_long_message(update, analysis)
    except Exception:
        logger.exception("Hujjatni tahlil qilishda xatolik")
        await update.message.reply_text("Kechirasiz, hujjatni tahlil qilishda xatolik yuz berdi.")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


@restricted
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_group = _is_group_chat(update)

    await update.message.chat.send_action(ChatAction.TYPING)
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)

    local_path = os.path.join(config.TEMP_DIR, f"photo_{photo.file_unique_id}.jpg")
    await tg_file.download_to_drive(local_path)

    try:
        image_b64 = document_service.image_to_base64(local_path)

        try:
            transactions = ai_service.classify_transactions_from_image(image_b64, "rasm")
        except Exception:
            logger.exception("Rasmdan prixod/rasxod ajratishda xatolik")
            transactions = []

        handled = await _save_transactions(
            update, transactions, "[Rasm orqali yuborilgan hisobot]", share_izoh=False
        )
        if handled:
            return

        if is_group:
            # Guruhda har kuni yuboriladigan kunlik hisobot rasmlariga (prixod/
            # rasxod topilmasa ham) izoh yozilmaydi.
            return

        await update.message.reply_text("\U0001F50D Rasm qabul qilindi, tahlil qilinmoqda...")
        analysis = ai_service.analyze_image_document(image_b64, "rasm")
        await _send_long_message(update, analysis)
    except Exception:
        logger.exception("Rasmni tahlil qilishda xatolik")
        if not is_group:
            await update.message.reply_text("Kechirasiz, rasmni tahlil qilishda xatolik yuz berdi.")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


async def _send_long_message(update: Update, text: str) -> None:
    limit = 4000
    for i in range(0, len(text), limit):
        await update.message.reply_text(text[i : i + limit], parse_mode="Markdown")


@restricted
async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("\U0001F4CA Ma'lumotlar tayyorlanmoqda...")

    filepath = None
    try:
        # Guruhda yozilgan xarajat/daromadlar faqat guruhda, shaxsiy chatdagilar
        # esa faqat shaxsiy chatda ko'rinadi - ikkalasi bir-biriga aralashmaydi.
        manba = "Guruh" if _is_group_chat(update) else "Shaxsiy"
        records = sheets_service.get_all_records(manba=manba)
        if not records:
            await update.message.reply_text("Hozircha hech qanday yozuv mavjud emas.")
            return

        filepath = excel_service.export_to_excel(records)
        with open(filepath, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(filepath),
                caption=f"✅ Jami {len(records)} ta yozuv eksport qilindi.",
            )
    except Exception:
        logger.exception("Excel eksport qilishda xatolik")
        await update.message.reply_text("Kechirasiz, ma'lumotlarni eksport qilishda xatolik yuz berdi.")
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)


async def hourly_health_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Soatlik texnik nazorat: faqat serverga log yozadi, guruhga xabar yubormaydi."""
    try:
        records = sheets_service.get_all_records()
        logger.info("Soatlik tekshiruv: bot ishlayapti, jadvalda jami %d ta yozuv.", len(records))
    except Exception:
        logger.exception("Soatlik tekshiruvda xatolik")


def main() -> None:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("yordam", help_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("hisobot", export_cmd))
    app.add_handler(CommandHandler("excel", export_cmd))

    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.job_queue.run_repeating(hourly_health_check, interval=3600, first=3600)

    logger.info("Hisobchi AI ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
