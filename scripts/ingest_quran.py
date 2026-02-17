"""Ingest the full Quran (6,236 Ayahs) into PostgreSQL + Qdrant.

Uses the alquran.cloud API to fetch Arabic (Uthmani) and English (Sahih International)
for each Surah, then chunks by Ayah, embeds, and stores.

Usage (from project root):
    python scripts/ingest_quran.py
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

import httpx

# Add backend to path so we can import app modules
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.database import async_session, engine
from app.models.db import Base, Book, Chunk, Source
from app.services.embedding import embed_texts
from app.services.vector_store import upsert_points

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

API_BASE = "https://api.alquran.cloud/v1"
ARABIC_EDITION = "quran-uthmani"
ENGLISH_EDITION = "en.sahih"
TOTAL_SURAHS = 114


async def fetch_surah(client: httpx.AsyncClient, surah_number: int) -> dict:
    """Fetch a single surah in both Arabic and English editions."""
    url = f"{API_BASE}/surah/{surah_number}/editions/{ARABIC_EDITION},{ENGLISH_EDITION}"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()

    if data["code"] != 200:
        raise RuntimeError(f"API error for surah {surah_number}: {data}")

    arabic_data = data["data"][0]
    english_data = data["data"][1]

    return {
        "surah_number": surah_number,
        "surah_name_arabic": arabic_data["name"],
        "surah_name_english": arabic_data["englishName"],
        "revelation_type": arabic_data["revelationType"],
        "ayahs_arabic": arabic_data["ayahs"],
        "ayahs_english": english_data["ayahs"],
    }


async def fetch_all_surahs() -> list[dict]:
    """Fetch all 114 surahs from the API."""
    surahs = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch in batches to be respectful to the API
        batch_size = 5
        for i in range(1, TOTAL_SURAHS + 1, batch_size):
            batch_end = min(i + batch_size, TOTAL_SURAHS + 1)
            logger.info("Fetching surahs %d-%d...", i, batch_end - 1)

            tasks = [fetch_surah(client, n) for n in range(i, batch_end)]
            results = await asyncio.gather(*tasks)
            surahs.extend(results)

            # Small delay between batches
            if batch_end <= TOTAL_SURAHS:
                await asyncio.sleep(1.0)

    logger.info("Fetched all %d surahs.", len(surahs))
    return surahs


def build_ayah_chunks(surahs: list[dict]) -> list[dict]:
    """Build one chunk per Ayah from fetched surah data."""
    chunks = []

    for surah in surahs:
        for ar_ayah, en_ayah in zip(surah["ayahs_arabic"], surah["ayahs_english"]):
            chunk = {
                "content_arabic": ar_ayah["text"],
                "content_english": en_ayah["text"],
                "chunk_type": "ayah",
                "page_number": ar_ayah.get("page"),
                "section": f"Surah {surah['surah_name_english']}",
                "metadata_json": {
                    "surah_number": surah["surah_number"],
                    "surah_name_arabic": surah["surah_name_arabic"],
                    "surah_name_english": surah["surah_name_english"],
                    "ayah_number": ar_ayah["numberInSurah"],
                    "juz": ar_ayah["juz"],
                    "ruku": ar_ayah["ruku"],
                    "revelation_type": surah["revelation_type"],
                },
            }
            chunks.append(chunk)

    logger.info("Built %d ayah chunks.", len(chunks))
    return chunks


async def ingest_chunks(chunks: list[dict]) -> None:
    """Embed all chunks and store in Qdrant + PostgreSQL."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Create the Quran book record
        book = Book(
            title="The Holy Quran",
            author="",
            language="both",
            madhab="general",
            category="quran",
        )
        session.add(book)
        await session.flush()

        # Create a source record
        source = Source(
            book_id=book.id,
            filename="quran-api-alquran-cloud",
            file_type="api",
            file_path="https://api.alquran.cloud",
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
            logger.info("Embedding batch %d/%d (%d chunks)...", batch_num, total_batches, len(batch))

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
                    "chunk_type": "ayah",
                    "book_title": "The Holy Quran",
                    "book_author": "",
                    "madhab": "general",
                    "category": "quran",
                    "language": "both",
                    "surah_number": meta["surah_number"],
                    "surah_name_arabic": meta["surah_name_arabic"],
                    "surah_name_english": meta["surah_name_english"],
                    "ayah_number": meta["ayah_number"],
                    "juz": meta["juz"],
                    "ruku": meta["ruku"],
                    "page_number": c.get("page_number"),
                }
                payloads.append(payload)

            point_ids = await upsert_points(embeddings, payloads)
            all_point_ids.extend(point_ids)

        # Save chunk records to PostgreSQL
        logger.info("Saving %d chunk records to PostgreSQL...", len(chunks))
        for c, point_id in zip(chunks, all_point_ids):
            db_chunk = Chunk(
                source_id=source.id,
                content_arabic=c["content_arabic"],
                content_english=c["content_english"],
                chunk_type="ayah",
                page_number=c.get("page_number"),
                section=c.get("section"),
                metadata_json=c["metadata_json"],
                qdrant_point_id=uuid.UUID(point_id),
            )
            session.add(db_chunk)

        source.status = "completed"
        await session.commit()

    logger.info("Quran ingestion complete!")


async def main():
    logger.info("Starting Quran ingestion...")

    # 1. Fetch from API
    surahs = await fetch_all_surahs()

    # 2. Build chunks
    chunks = build_ayah_chunks(surahs)

    # 3. Embed and store
    await ingest_chunks(chunks)

    await engine.dispose()
    logger.info("Done! %d ayahs ingested.", len(chunks))


if __name__ == "__main__":
    asyncio.run(main())
