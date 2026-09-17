import os
from datetime import datetime

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config


def _expense_category_breakdown(records: list[dict]) -> dict[str, list[float]]:
    """Xarajatlarni kategoriya bo'yicha, yozilgan tartibida ro'yxatlarga ajratadi.
    Mavjud kategoriya uchun summa o'sha kategoriya ustuniga pastdan qo'shiladi,
    yangi kategoriya esa o'zining alohida ustunini oladi (birinchi uchragan
    tartibda)."""
    per_category: dict[str, list[float]] = {}
    for record in records:
        if str(record.get("Turi", "")).strip().lower() != "xarajat":
            continue
        kategoriya = record.get("Kategoriya") or "Boshqa"
        try:
            summa = float(record.get("Summa") or 0)
        except (TypeError, ValueError):
            summa = 0
        per_category.setdefault(kategoriya, []).append(summa)

    return per_category


def export_to_excel(records: list[dict]) -> str:
    df = pd.DataFrame(records)

    filename = f"hisobchi_ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(config.TEMP_DIR, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tranzaksiyalar")

        if not df.empty and "Turi" in df.columns and "Summa" in df.columns:
            df["Summa"] = pd.to_numeric(df["Summa"], errors="coerce")
            summary = df.groupby("Turi")["Summa"].sum().reset_index()
            summary.to_excel(writer, index=False, sheet_name="Xulosa")

        per_category = _expense_category_breakdown(records)
        if per_category:
            max_len = max(len(values) for values in per_category.values())
            breakdown_df = pd.DataFrame(
                {
                    kategoriya: values + [None] * (max_len - len(values))
                    for kategoriya, values in per_category.items()
                }
            )
            breakdown_df.to_excel(writer, index=False, sheet_name="Xarajatlar kategoriya")

            breakdown_sheet = writer.sheets["Xarajatlar kategoriya"]
            for row in breakdown_sheet.iter_rows(min_row=2, max_row=max_len + 1):
                for cell in row:
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = "#,##0"

            label_row = max_len + 3
            total_row = max_len + 4
            breakdown_sheet.cell(row=label_row, column=1, value="Jami (kategoriya bo'yicha):")
            for col_idx, kategoriya in enumerate(per_category.keys(), start=1):
                total_cell = breakdown_sheet.cell(row=total_row, column=col_idx, value=sum(per_category[kategoriya]))
                total_cell.number_format = "#,##0"

            for column_cells in breakdown_sheet.columns:
                max_length = max(
                    len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells
                )
                breakdown_sheet.column_dimensions[column_cells[0].column_letter].width = max_length + 3

        worksheet = writer.sheets["Tranzaksiyalar"]
        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = max_length + 3

    return filepath


def generate_expense_chart_image(totals: list[tuple[str, float]]) -> str | None:
    """Xarajatlarni kategoriya bo'yicha doiraviy diagramma (PNG rasm) sifatida
    chizib, chatda yuborish uchun fayl yo'lini qaytaradi. Xarajat bo'lmasa None."""

    if not totals:
        return None

    labels = [kategoriya for kategoriya, _ in totals]
    values = [summa for _, summa in totals]

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.set_title("Xarajatlar (kategoriya bo'yicha)")
    ax.axis("equal")

    filename = f"xarajatlar_grafigi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(config.TEMP_DIR, filename)
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)

    return filepath
