import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

_allowed_user_id = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
ALLOWED_TELEGRAM_USER_ID = int(_allowed_user_id) if _allowed_user_id else None

_allowed_group_chat_id = os.getenv("ALLOWED_GROUP_CHAT_ID", "").strip()
ALLOWED_GROUP_CHAT_ID = int(_allowed_group_chat_id) if _allowed_group_chat_id else None

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")

GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "credentials.json")
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "").strip()
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_SHEET_WORKSHEET = os.getenv("GOOGLE_SHEET_WORKSHEET", "Tranzaksiyalar")

SHEET_HEADERS = [
    "Sana",
    "Vaqt",
    "Foydalanuvchi",
    "Turi",
    "Kategoriya",
    "Summa",
    "Valyuta",
    "Izoh",
    "Original xabar",
]

EXPENSE_CATEGORIES = [
    "Oziq-ovqat",
    "Transport",
    "Kommunal to'lovlar",
    "Ijara",
    "Kiyim-kechak",
    "Sog'liqni saqlash",
    "Ta'lim",
    "Ko'ngilochar/dam olish",
    "Aloqa/Internet",
    "Boshqa xarajat",
]

INCOME_CATEGORIES = [
    "Ish haqi",
    "Biznes daromadi",
    "Frilans/qo'shimcha ish",
    "Sovg'a/yordam",
    "Boshqa daromad",
]

TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)
