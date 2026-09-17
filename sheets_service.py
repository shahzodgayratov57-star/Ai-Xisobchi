import base64
import json

import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

import config

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_worksheet = None
_spreadsheet = None
_chart_worksheet = None

CHART_WORKSHEET_TITLE = "List 2"

SUMMA_NUMBER_FORMAT = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}


def _get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet

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
    _spreadsheet = gc.open_by_key(config.GOOGLE_SHEET_ID)
    return _spreadsheet


def _get_worksheet():
    global _worksheet
    if _worksheet is not None:
        return _worksheet

    spreadsheet = _get_spreadsheet()

    try:
        worksheet = spreadsheet.worksheet(config.GOOGLE_SHEET_WORKSHEET)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=config.GOOGLE_SHEET_WORKSHEET, rows=1000, cols=len(config.SHEET_HEADERS)
        )

    header_row = worksheet.row_values(1)
    if not header_row:
        worksheet.append_row(config.SHEET_HEADERS)
    elif len(header_row) < len(config.SHEET_HEADERS):
        # Eski jadvalga keyinroq qo'shilgan ustunlar (masalan "Manba") uchun
        # sarlavha qatorini to'ldirib qo'yamiz, mavjud ma'lumotlarga tegmasdan.
        worksheet.update("A1", [config.SHEET_HEADERS])

    # "Summa" ustuni (F) minglik ajratgich bilan o'qilishi oson bo'lsin (masalan 1,000,000).
    worksheet.format("F2:F10000", SUMMA_NUMBER_FORMAT)

    _worksheet = worksheet
    return _worksheet


def _get_chart_worksheet():
    global _chart_worksheet
    if _chart_worksheet is not None:
        return _chart_worksheet

    spreadsheet = _get_spreadsheet()

    try:
        worksheet = spreadsheet.worksheet(CHART_WORKSHEET_TITLE)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=CHART_WORKSHEET_TITLE, rows=1000, cols=100)

    # Eski (avvalroq kichikroq o'lchamda yaratilgan) varaq bo'lsa, bir nechta
    # valyuta blokini sig'dirish uchun kattalashtiramiz.
    if worksheet.row_count < 1000 or worksheet.col_count < 100:
        worksheet.resize(rows=max(worksheet.row_count, 1000), cols=max(worksheet.col_count, 100))

    # Har bir valyuta o'z ustun blokida (jami summalar va kategoriya bo'yicha
    # batafsil jadval) - hammasi son formatida ko'rinishi uchun keng maydonni
    # oldindan formatlab qo'yamiz.
    end_col_letters = "".join(ch for ch in rowcol_to_a1(1, 100) if ch.isalpha())
    worksheet.format(f"A2:{end_col_letters}1000", SUMMA_NUMBER_FORMAT)

    _chart_worksheet = worksheet
    return _chart_worksheet


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
            row.get("manba", ""),
        ]
    )

    if row.get("turi") == "xarajat":
        update_expense_chart()


def get_all_records(manba: str | None = None) -> list[dict]:
    """Barcha yozuvlarni qaytaradi. `manba` berilsa ("Guruh" yoki "Shaxsiy"),
    faqat o'sha manbadan kelgan qatorlar qaytariladi — guruhda yozilgan
    xarajat/daromadlar shaxsiy chatda (va aksincha) ko'rsatilmasligi uchun.
    Eski (Manba ustuni bo'lmagan) yozuvlar "Shaxsiy" deb hisoblanadi."""
    worksheet = _get_worksheet()
    records = worksheet.get_all_records()
    if manba is None:
        return records
    return [r for r in records if (r.get("Manba") or "Shaxsiy") == manba]


def _sorted_currencies(currencies) -> list[str]:
    """UZS har doim birinchi, qolganlari alifbo tartibida."""
    ordered = sorted(currencies)
    if "UZS" in ordered:
        ordered.remove("UZS")
        ordered.insert(0, "UZS")
    return ordered


def expense_totals_by_category() -> dict[str, list[tuple[str, float]]]:
    """Barcha xarajatlarni valyuta, so'ng kategoriya bo'yicha jamlab qaytaradi
    (har bir valyuta alohida hisoblanadi — so'm va dollar qo'shib yuborilmaydi)."""
    totals: dict[str, dict[str, float]] = {}
    for record in get_all_records():
        if str(record.get("Turi", "")).strip().lower() != "xarajat":
            continue
        valyuta = str(record.get("Valyuta") or "UZS").strip().upper()
        kategoriya = record.get("Kategoriya") or "Boshqa"
        try:
            summa = float(record.get("Summa") or 0)
        except (TypeError, ValueError):
            summa = 0
        totals.setdefault(valyuta, {})
        totals[valyuta][kategoriya] = totals[valyuta].get(kategoriya, 0) + summa

    return {
        valyuta: sorted(kategoriya_totals.items(), key=lambda item: item[1], reverse=True)
        for valyuta, kategoriya_totals in totals.items()
    }


BREAKDOWN_START_ROW = 30
CURRENCY_BLOCK_WIDTH = 14


def expense_breakdown_by_category() -> dict[str, dict[str, list[float]]]:
    """Xarajatlarni valyuta, so'ng kategoriya bo'yicha, yozilgan tartibida
    ro'yxatlarga ajratadi. Mavjud kategoriya uchun summa o'sha kategoriya
    ustuniga pastdan qo'shiladi, yangi kategoriya esa o'zining alohida
    ustunini oladi (birinchi uchragan tartibda)."""
    per_currency: dict[str, dict[str, list[float]]] = {}
    for record in get_all_records():
        if str(record.get("Turi", "")).strip().lower() != "xarajat":
            continue
        valyuta = str(record.get("Valyuta") or "UZS").strip().upper()
        kategoriya = record.get("Kategoriya") or "Boshqa"
        try:
            summa = float(record.get("Summa") or 0)
        except (TypeError, ValueError):
            summa = 0
        per_currency.setdefault(valyuta, {}).setdefault(kategoriya, []).append(summa)

    return per_currency


def update_expense_chart() -> None:
    """'List 2' varag'iga xarajatlar jadvalini yozadi. Har bir valyuta (so'm,
    dollar va h.k.) o'zining alohida ustun blokida, o'z jami/kategoriya
    jadvali va o'z doiraviy diagrammasi bilan ko'rsatiladi — valyutalar
    hech qachon bir-biriga qo'shib hisoblanmaydi."""

    totals_by_currency = expense_totals_by_category()
    breakdown_by_currency = expense_breakdown_by_category()
    currencies = _sorted_currencies(set(totals_by_currency) | set(breakdown_by_currency))

    worksheet = _get_chart_worksheet()
    worksheet.clear()

    chart_blocks = []
    for i, valyuta in enumerate(currencies):
        col_offset = i * CURRENCY_BLOCK_WIDTH

        totals = totals_by_currency.get(valyuta, [])
        rows = [[f"Kategoriya ({valyuta})", "Summa"]] + [[kategoriya, summa] for kategoriya, summa in totals]
        worksheet.update(rowcol_to_a1(1, col_offset + 1), rows)

        per_category = breakdown_by_currency.get(valyuta, {})
        if per_category:
            categories = list(per_category.keys())
            max_len = max(len(values) for values in per_category.values())
            breakdown_rows = [categories]
            for row_i in range(max_len):
                breakdown_rows.append(
                    [
                        per_category[kategoriya][row_i] if row_i < len(per_category[kategoriya]) else ""
                        for kategoriya in categories
                    ]
                )
            worksheet.update(rowcol_to_a1(BREAKDOWN_START_ROW, col_offset + 1), breakdown_rows)

        chart_blocks.append((valyuta, col_offset, len(rows)))

    _upsert_expense_pie_charts(worksheet, chart_blocks)


def _upsert_expense_pie_charts(worksheet, blocks: list[tuple[str, int, int]]) -> None:
    spreadsheet = worksheet.spreadsheet
    sheet_id = worksheet.id

    metadata = spreadsheet.fetch_sheet_metadata(
        params={"fields": "sheets(properties(sheetId),charts(chartId))"}
    )
    requests = []
    for sheet in metadata.get("sheets", []):
        if sheet["properties"]["sheetId"] != sheet_id:
            continue
        for chart in sheet.get("charts", []):
            requests.append({"deleteEmbeddedObject": {"objectId": chart["chartId"]}})

    for valyuta, col_offset, data_row_count in blocks:
        if data_row_count <= 1:
            continue
        requests.append(
            {
                "addChart": {
                    "chart": {
                        "spec": {
                            "title": f"Xarajatlar ({valyuta})",
                            "pieChart": {
                                "legendPosition": "RIGHT_LEGEND",
                                "domain": {
                                    "sourceRange": {
                                        "sources": [
                                            {
                                                "sheetId": sheet_id,
                                                "startRowIndex": 1,
                                                "endRowIndex": data_row_count,
                                                "startColumnIndex": col_offset,
                                                "endColumnIndex": col_offset + 1,
                                            }
                                        ]
                                    }
                                },
                                "series": {
                                    "sourceRange": {
                                        "sources": [
                                            {
                                                "sheetId": sheet_id,
                                                "startRowIndex": 1,
                                                "endRowIndex": data_row_count,
                                                "startColumnIndex": col_offset + 1,
                                                "endColumnIndex": col_offset + 2,
                                            }
                                        ]
                                    }
                                },
                            },
                        },
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {
                                    "sheetId": sheet_id,
                                    "rowIndex": 0,
                                    "columnIndex": col_offset + 3,
                                },
                                "widthPixels": 500,
                                "heightPixels": 350,
                            }
                        },
                    }
                }
            }
        )

    if requests:
        spreadsheet.batch_update({"requests": requests})
