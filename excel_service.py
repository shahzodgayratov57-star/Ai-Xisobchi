import os
from datetime import datetime

import pandas as pd

import config


def export_to_excel(records: list[dict]) -> str:
    df = pd.DataFrame(records)

    filename = f"hisobchi_ai_{datetime.now(config.TASHKENT_TZ).strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(config.TEMP_DIR, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tranzaksiyalar")

        worksheet = writer.sheets["Tranzaksiyalar"]
        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = max_length + 3

    return filepath
