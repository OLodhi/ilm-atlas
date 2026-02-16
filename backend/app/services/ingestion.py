import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Book, Chunk, Source
from app.services.chunking import chunk_by_type
from app.services.embedding import embed_texts
from app.services.ocr import ocr_image, ocr_pdf
from app.services.text_extract import (
    extract_text_from_file,
    extract_text_from_pdf,
    has_extractable_text,
)
from app.services.vector_store import upsert_points

logger = logging.getLogger(__name__)


def _detect_file_type(filename: str) -> str:
    """Detect file type from extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
        return "image"
    if ext in (".txt", ".md"):
        return "text"
    raise ValueError(f"Unsupported file type: {ext}")


async def run_ingestion(
    session: AsyncSession,
    source: Source,
    book: Book,
    chunk_type: str,
) -> None:
    """Full ingestion pipeline: extract → chunk → embed → store.

    Updates the Source status to 'completed' or 'failed'.
    """
    try:
        source.status = "processing"
        await session.commit()

        file_path = source.file_path
        file_type = source.file_type

        # 1. Extract text
        logger.info("Extracting text from %s (%s)", source.filename, file_type)
        if file_type == "pdf":
            if has_extractable_text(file_path):
                pages = await extract_text_from_pdf(file_path)
            else:
                languages = _get_ocr_languages(book.language)
                pages = await ocr_pdf(file_path, languages)
        elif file_type == "image":
            languages = _get_ocr_languages(book.language)
            pages = await ocr_image(file_path, languages)
        elif file_type == "text":
            pages = await extract_text_from_file(file_path)
        else:
            raise ValueError(f"Unknown file type: {file_type}")

        if not pages:
            source.status = "failed"
            source.error_message = "No text could be extracted from the file."
            await session.commit()
            return

        # 2. Chunk
        logger.info("Chunking %d pages with strategy: %s", len(pages), chunk_type)
        chunks = chunk_by_type(pages, chunk_type)

        if not chunks:
            source.status = "failed"
            source.error_message = "Chunking produced no chunks."
            await session.commit()
            return

        # 3. Embed
        logger.info("Generating embeddings for %d chunks", len(chunks))
        texts_to_embed = []
        for c in chunks:
            # Combine Arabic and English for embedding
            parts = []
            if c.get("content_arabic"):
                parts.append(c["content_arabic"])
            if c.get("content_english"):
                parts.append(c["content_english"])
            texts_to_embed.append(" ".join(parts))

        embeddings = embed_texts(texts_to_embed)

        # 4. Build Qdrant payloads
        payloads = []
        for c in chunks:
            payload = {
                "content_arabic": c.get("content_arabic") or "",
                "content_english": c.get("content_english") or "",
                "chunk_type": c["chunk_type"],
                "book_title": book.title,
                "book_author": book.author,
                "madhab": book.madhab,
                "category": book.category,
                "language": book.language,
                "page_number": c.get("page_number"),
                "section": c.get("section"),
            }
            if c.get("metadata_json"):
                payload["metadata"] = c["metadata_json"]
            payloads.append(payload)

        # 5. Upsert to Qdrant
        logger.info("Upserting %d points to Qdrant", len(embeddings))
        point_ids = await upsert_points(embeddings, payloads)

        # 6. Save chunks to PostgreSQL
        logger.info("Saving %d chunk records to PostgreSQL", len(chunks))
        for c, point_id in zip(chunks, point_ids):
            db_chunk = Chunk(
                source_id=source.id,
                content_arabic=c.get("content_arabic"),
                content_english=c.get("content_english"),
                chunk_type=c["chunk_type"],
                page_number=c.get("page_number"),
                section=c.get("section"),
                metadata_json=c.get("metadata_json"),
                qdrant_point_id=uuid.UUID(point_id),
            )
            session.add(db_chunk)

        source.status = "completed"
        await session.commit()
        logger.info("Ingestion complete for source %s", source.id)

    except Exception as e:
        logger.exception("Ingestion failed for source %s", source.id)
        source.status = "failed"
        source.error_message = str(e)
        await session.commit()


def _get_ocr_languages(language: str) -> list[str]:
    """Map book language setting to Surya language codes."""
    if language == "arabic":
        return ["ar"]
    if language == "english":
        return ["en"]
    return ["ar", "en"]
