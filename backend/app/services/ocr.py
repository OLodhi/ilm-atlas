import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded to avoid slow import at startup
_det_predictor = None
_rec_predictor = None


def _load_models():
    global _det_predictor, _rec_predictor
    if _rec_predictor is not None:
        return

    logger.info("Loading Surya OCR models (first call only)...")
    from surya.detection import DetectionPredictor
    from surya.recognition import RecognitionPredictor

    _det_predictor = DetectionPredictor()
    _rec_predictor = RecognitionPredictor()
    logger.info("Surya OCR models loaded.")


async def ocr_pdf(file_path: str, languages: list[str] | None = None) -> list[dict]:
    """Run OCR on a scanned PDF using Surya.

    Returns a list of dicts with 'page_number' and 'text' keys.
    """
    if languages is None:
        languages = ["ar", "en"]

    _load_models()

    from PIL import Image
    import pypdfium2 as pdfium

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    pdf = pdfium.PdfDocument(str(path))
    pages = []

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        bitmap = page.render(scale=300 / 72)  # 300 DPI
        img = bitmap.to_pil()

        predictions = _rec_predictor([img], det_predictor=_det_predictor)

        page_text_lines = []
        for pred in predictions:
            for line in pred.text_lines:
                page_text_lines.append(line.text)

        text = "\n".join(page_text_lines).strip()
        if text:
            pages.append({"page_number": page_num + 1, "text": text})

    pdf.close()
    return pages


async def ocr_image(file_path: str, languages: list[str] | None = None) -> list[dict]:
    """Run OCR on a single image file using Surya.

    Returns a list with a single dict containing the extracted text.
    """
    if languages is None:
        languages = ["ar", "en"]

    _load_models()

    from PIL import Image

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    img = Image.open(path).convert("RGB")

    predictions = _rec_predictor([img], det_predictor=_det_predictor)

    lines = []
    for pred in predictions:
        for line in pred.text_lines:
            lines.append(line.text)

    text = "\n".join(lines).strip()
    if not text:
        return []

    return [{"page_number": 1, "text": text}]
