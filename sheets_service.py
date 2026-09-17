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
_spreadsheet = None
_chart_worksheet = None

CHART_WORKSHEET_TITLE = "List 2"


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

    if worksheet.row_count == 0 or not worksheet.row_values(1):
        worksheet.append_row(config.SHEET_HEADERS)

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
        worksheet = spreadsheet.add_worksheet(title=CHART_WORKSHEET_TITLE, rows=200, cols=10)

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
        ]
    )

    if row.get("turi") == "xarajat":
        update_expense_chart()


def get_all_records() -> list[dict]:
    worksheet = _get_worksheet()
    return worksheet.get_all_records()


def expense_totals_by_category() -> list[tuple[str, float]]:
    """Barcha xarajatlarni kategoriya bo'yicha jamlab, kamayish tartibida qaytaradi."""
    totals: dict[str, float] = {}
    for record in get_all_records():
        if str(record.get("Turi", "")).strip().lower() != "xarajat":
            continue
        kategoriya = record.get("Kategoriya") or "Boshqa"
        try:
            summa = float(record.get("Summa") or 0)
        except (TypeError, ValueError):
            summa = 0
        totals[kategoriya] = totals.get(kategoriya, 0) + summa

    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def update_expense_chart() -> None:
    """'List 2' varag'iga xarajatlar jadvalini yozib, uni doiraviy diagramma
    (pie chart) sifatida ham chizadi, shunda Google Sheetsda grafik ko'rinishida
    ko'rinadi."""

    totals = expense_totals_by_category()

    worksheet = _get_chart_worksheet()
    worksheet.clear()

    rows = [["Kategoriya", "Summa"]] + [[kategoriya, summa] for kategoriya, summa in totals]
    worksheet.update("A1", rows)

    _upsert_expense_pie_chart(worksheet, data_row_count=len(rows))


def _upsert_expense_pie_chart(worksheet, data_row_count: int) -> None:
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

    if data_row_count > 1:
        requests.append(
            {
                "addChart": {
                    "chart": {
                        "spec": {
                            "title": "Xarajatlar (kategoriya bo'yicha)",
                            "pieChart": {
                                "legendPosition": "RIGHT_LEGEND",
                                "domain": {
                                    "sourceRange": {
                                        "sources": [
                                            {
                                                "sheetId": sheet_id,
                                                "startRowIndex": 1,
                                                "endRowIndex": data_row_count,
                                                "startColumnIndex": 0,
                                                "endColumnIndex": 1,
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
                                                "startColumnIndex": 1,
                                                "endColumnIndex": 2,
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
                                    "columnIndex": 3,
                                },
                                "widthPixels": 600,
                                "heightPixels": 400,
                            }
                        },
                    }
                }
            }
        )

    if requests:
        spreadsheet.batch_update({"requests": requests})
