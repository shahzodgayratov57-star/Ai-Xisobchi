import base64
import json

import gspread
from google.oauth2.service_account import Credentials

import config

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_worksheet = None


def _get_worksheet():
    global _worksheet
    if _worksheet is not None:
        return _worksheet

    if config.GOOGLE_SHEETS_CREDENTIALS_JSON_B64:
        raw = base64.b64decode(config.GOOGLE_SHEETS_CREDENTIALS_JSON_B64)
        info = json.loads(raw)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    elif config.GOOGLE_SHEETS_CREDENTIALS_JSON:
        info = json.loads(config.GOOGLE_SHEETS_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=_SCOPES
        )
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(config.GOOGLE_SHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(config.GOOGLE_SHEET_WORKSHEET)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=config.GOOGLE_SHEET_WORKSHEET, rows=1000, cols=len(config.SHEET_HEADERS)
        )

    if worksheet.row_count == 0 or not worksheet.row_values(1):
        worksheet.append_row(config.SHEET_HEADERS)

    _worksheet = worksheet
    return _worksheet


def append_transaction(row: dict) -> None:
    worksheet = _get_worksheet()
    worksheet.append_row(
        [
            row.get("sana", ""),
            row.get("vaqt", ""),
            row.get("foydalanuvchi", ""),
            row.get("turi", ""),
            row.get("kategoriya", ""),
            row.get("summa", ""),
            row.get("valyuta", ""),
            row.get("izoh", ""),
            row.get("original_xabar", ""),
        ]
    )


def get_all_records() -> list[dict]:
    worksheet = _get_worksheet()
    return worksheet.get_all_records()
