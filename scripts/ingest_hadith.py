"""Ingest the Kutub al-Sittah (6 major hadith collections, ~34k hadiths) into PostgreSQL + Qdrant.

Uses hadithapi.com to fetch hadiths with Arabic text, English translation, and metadata,
then chunks by individual hadith, embeds, and stores.

Usage (from project root):
    python scripts/ingest_hadith.py
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

import httpx

# Configure logging BEFORE app imports (which may configure root logger first)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger(__name__)

# Windows-specific: use SelectorEventLoop for httpx async compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path so we can import app modules
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import settings  # noqa: E402
from app.database import async_session, engine  # noqa: E402
from app.models.db import Base, Book, Chunk, Source  # noqa: E402
from app.services.embedding import embed_texts  # noqa: E402
from app.services.vector_store import upsert_points  # noqa: E402

API_BASE = "https://hadithapi.com/api/hadiths"
PAGE_SIZE = 300

COLLECTIONS = [
    {"slug": "sahih-bukhari", "name": "Sahih Bukhari", "author": "Imam Bukhari"},
    {"slug": "sahih-muslim", "name": "Sahih Muslim", "author": "Imam Muslim"},
    {"slug": "al-tirmidhi", "name": "Jami' Al-Tirmidhi", "author": "Imam Tirmidhi"},
    {"slug": "abu-dawood", "name": "Sunan Abu Dawood", "author": "Imam Abu Dawud"},
    {"slug": "ibn-e-majah", "name": "Sunan Ibn-e-Majah", "author": "Imam Ibn Majah"},
    {"slug": "sunan-nasai", "name": "Sunan An-Nasa'i", "author": "Imam An-Nasa'i"},
]


async def fetch_collection(client: httpx.AsyncClient, book_slug: str) -> list[dict]:
    """Fetch all hadiths for a single collection, paginating through all pages."""
    hadiths = []
    page = 1

    while True:
        params = {
            "apiKey": settings.hadith_api_key,
            "book": book_slug,
            "paginate": PAGE_SIZE,
            "page": page,
        }

        resp = await client.get(API_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

        page_hadiths = data.get("hadiths", {}).get("data", [])
        if not page_hadiths:
            break

        hadiths.extend(page_hadiths)

        last_page = data.get("hadiths", {}).get("last_page", page)
        logger.info(
            "Fetching %s page %d/%d... (%d hadiths so far)",
            book_slug, page, last_page, len(hadiths),
        )

        if page >= last_page:
            break

        page += 1
        await asyncio.sleep(1.0)

    logger.info("Fetched %d hadiths from %s.", len(hadiths), book_slug)
    return hadiths


def build_hadith_chunks(hadiths: list[dict], book_info: dict) -> list[dict]:
    """Build one chunk per hadith from fetched API data."""
    chunks = []

    for h in hadiths:
        arabic = (h.get("hadithArabic") or "").strip()
        english = (h.get("hadithEnglish") or "").strip()
        narrator = (h.get("englishNarrator") or "").strip()

        # Skip hadiths with no text at all
        if not arabic and not english:
            continue

        # Combine narrator with English text (narrator is part of the hadith)
        content_english = f"{narrator} {english}".strip() if narrator else english

        book_data = h.get("book", {}) or {}
        chapter_data = h.get("chapter", {}) or {}

        chunk = {
            "content_arabic": arabic or None,
            "content_english": content_english or None,
            "chunk_type": "hadith",
            "page_number": None,
            "section": f"Chapter: {chapter_data.get('chapterEnglish', '')}",
            "metadata_json": {
                "hadith_number": str(h.get("hadithNumber", "")),
                "book_slug": book_info["slug"],
                "chapter_number": str(chapter_data.get("chapterNumber", "")),
                "chapter_english": chapter_data.get("chapterEnglish", ""),
                "chapter_arabic": chapter_data.get("chapterArabic", ""),
                "volume": str(h.get("volume", "")),
                "status": h.get("status", ""),
                "narrator_english": narrator,
            },
        }
        chunks.append(chunk)

    logger.info("Built %d hadith chunks for %s.", len(chunks), book_info["name"])
    return chunks


async def ingest_chunks(chunks: list[dict], book_info: dict) -> None:
    """Embed all chunks and store in Qdrant + PostgreSQL."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Create the book record
        book = Book(
            title=book_info["name"],
            author=book_info["author"],
            language="both",
            madhab="general",
            category="hadith",
        )
        session.add(book)
        await session.flush()

        # Create a source record
        source = Source(
            book_id=book.id,
            filename=f"hadithapi-{book_info['slug']}",
            file_type="api",
            file_path=f"https://hadithapi.com/api/hadiths?book={book_info['slug']}",
            status="processing",
        )
        session.add(source)
        await session.flush()

        # Embed in batches
        batch_size = 100
        all_point_ids = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            logger.info(
                "[%s] Embedding batch %d/%d (%d chunks)...",
                book_info["name"], batch_num, total_batches, len(batch),
            )

            # Build texts for embedding (Arabic + English combined)
            texts = []
            for c in batch:
                parts = []
                if c["content_arabic"]:
                    parts.append(c["content_arabic"])
                if c["content_english"]:
                    parts.append(c["content_english"])
                texts.append(" ".join(parts))

            embeddings = embed_texts(texts)

            # Build Qdrant payloads
            payloads = []
            for c in batch:
                meta = c["metadata_json"]
                payload = {
                    "content_arabic": c["content_arabic"],
                    "content_english": c["content_english"],
                    "chunk_type": "hadith",
                    "book_title": book_info["name"],
                    "book_author": book_info["author"],
                    "madhab": "general",
                    "category": "hadith",
                    "language": "both",
                    "hadith_number": meta["hadith_number"],
                    "chapter_number": meta["chapter_number"],
                    "chapter_english": meta["chapter_english"],
                    "chapter_arabic": meta["chapter_arabic"],
                    "volume": meta["volume"],
                    "status": meta["status"],
                    "page_number": None,
                    "metadata": {
                        "hadith_number": meta["hadith_number"],
                        "book_slug": meta["book_slug"],
                        "narrator_english": meta["narrator_english"],
                    },
                }
                payloads.append(payload)

            point_ids = await upsert_points(embeddings, payloads)
            all_point_ids.extend(point_ids)

        # Save chunk records to PostgreSQL
        logger.info("Saving %d chunk records to PostgreSQL for %s...", len(chunks), book_info["name"])
        for c, point_id in zip(chunks, all_point_ids):
            db_chunk = Chunk(
                source_id=source.id,
                content_arabic=c["content_arabic"],
                content_english=c["content_english"],
                chunk_type="hadith",
                page_number=None,
                section=c.get("section"),
                metadata_json=c["metadata_json"],
                qdrant_point_id=uuid.UUID(point_id),
            )
            session.add(db_chunk)

        source.status = "completed"
        await session.commit()

    logger.info("Ingestion complete for %s (%d hadiths).", book_info["name"], len(chunks))


async def main():
    logger.info("Starting Kutub al-Sittah hadith ingestion...")

    if not settings.hadith_api_key:
        logger.error("HADITH_API_KEY not set in .env — aborting.")
        sys.exit(1)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for book_info in COLLECTIONS:
            logger.info("=== Processing %s ===", book_info["name"])

            # 1. Fetch from API
            hadiths = await fetch_collection(client, book_info["slug"])

            # 2. Build chunks
            chunks = build_hadith_chunks(hadiths, book_info)

            # 3. Embed and store
            await ingest_chunks(chunks, book_info)

            logger.info("=== Done with %s ===\n", book_info["name"])

    await engine.dispose()
    logger.info("All collections ingested successfully!")


if __name__ == "__main__":
    asyncio.run(main())
