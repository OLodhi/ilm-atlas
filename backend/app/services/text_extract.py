import logging
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


async def extract_text_from_pdf(file_path: str) -> list[dict]:
    """Extract text from a PDF using pdfplumber.

    Returns a list of dicts with 'page_number' and 'text' keys.
    If the PDF has no extractable text (scanned), returns empty list.
    """
    pages = []
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append({"page_number": i, "text": text})

    if not pages:
        logger.info("No extractable text in %s — may need OCR", file_path)

    return pages


async def extract_text_from_file(file_path: str) -> list[dict]:
    """Extract text from a plain text file.

    Returns a list with a single dict containing the full text.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    return [{"page_number": 1, "text": text}]


def has_extractable_text(file_path: str) -> bool:
    """Check if a PDF has extractable text (not just scanned images)."""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages[:3]:  # Check first 3 pages
            text = page.extract_text() or ""
            if text.strip():
                return True
    return False
