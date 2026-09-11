import base64
import os

import pdfplumber
from docx import Document


def extract_text(filepath: str) -> str | None:
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts).strip() or None

    if ext == ".docx":
        doc = Document(filepath)
        return "\n".join(p.text for p in doc.paragraphs).strip() or None

    if ext in (".txt", ".csv"):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip() or None

    return None


def is_image(filepath: str) -> bool:
    return os.path.splitext(filepath)[1].lower() in (".jpg", ".jpeg", ".png", ".webp")


def image_to_base64(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
