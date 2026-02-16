import logging
import re

logger = logging.getLogger(__name__)


def chunk_paragraphs(
    pages: list[dict],
    max_words: int = 400,
    overlap_words: int = 50,
) -> list[dict]:
    """Chunk extracted pages into paragraph-level chunks with overlap.

    Each chunk gets ~300-500 words. Adjacent chunks share `overlap_words`
    words for context continuity.
    """
    chunks = []

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        # Split into paragraphs first
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

        # Accumulate paragraphs into chunks of target size
        current_words: list[str] = []

        for para in paragraphs:
            para_words = para.split()

            if len(current_words) + len(para_words) > max_words and current_words:
                # Emit current chunk
                chunk_text = " ".join(current_words)
                chunks.append({
                    "content_english": chunk_text,
                    "content_arabic": None,
                    "chunk_type": "paragraph",
                    "page_number": page_number,
                    "section": None,
                    "metadata_json": {},
                })

                # Keep overlap
                current_words = current_words[-overlap_words:] if overlap_words else []

            current_words.extend(para_words)

        # Emit remaining
        if current_words:
            chunk_text = " ".join(current_words)
            chunks.append({
                "content_english": chunk_text,
                "content_arabic": None,
                "chunk_type": "paragraph",
                "page_number": page_number,
                "section": None,
                "metadata_json": {},
            })

    return chunks


def chunk_hadith(pages: list[dict]) -> list[dict]:
    """Chunk text that contains Hadith narrations.

    Attempts to split on common Hadith delimiters (numbered hadiths,
    narrator chain patterns). Falls back to paragraph chunking.
    """
    full_text = "\n\n".join(p["text"] for p in pages)

    # Try splitting on numbered hadith patterns like "Hadith 1:", "#1", "1."
    parts = re.split(r"(?:^|\n)(?:Hadith\s+)?#?\d+[.):]\s*", full_text)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) < 2:
        # Fallback to paragraph chunking
        return chunk_paragraphs(pages)

    chunks = []
    for i, part in enumerate(parts, start=1):
        chunks.append({
            "content_english": part,
            "content_arabic": None,
            "chunk_type": "hadith",
            "page_number": None,
            "section": None,
            "metadata_json": {"hadith_number": i},
        })

    return chunks


def chunk_by_type(pages: list[dict], chunk_type: str) -> list[dict]:
    """Route to the appropriate chunking strategy."""
    if chunk_type == "hadith":
        return chunk_hadith(pages)
    # paragraph is the default for fiqh, aqeedah, general
    return chunk_paragraphs(pages)
