import os
from datetime import datetime

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config


def export_to_excel(records: list[dict]) -> str:
    df = pd.DataFrame(records)

    filename = f"hisobchi_ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(config.TEMP_DIR, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tranzaksiyalar")

        worksheet = writer.sheets["Tranzaksiyalar"]
        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = max_length + 3

    return filepath


def generate_expense_chart_image(totals: list[tuple[str, float]], valyuta: str = "UZS") -> str | None:
    """Xarajatlarni (bitta valyuta uchun) kategoriya bo'yicha doiraviy diagramma
    (PNG rasm) sifatida chizib, chatda yuborish uchun fayl yo'lini qaytaradi.
    Xarajat bo'lmasa None."""

    if not totals:
        return None

    labels = [kategoriya for kategoriya, _ in totals]
    values = [summa for _, summa in totals]

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.set_title(f"Xarajatlar ({valyuta})")
    ax.axis("equal")

    filename = f"xarajatlar_grafigi_{valyuta}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(config.TEMP_DIR, filename)
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)

    return filepath
