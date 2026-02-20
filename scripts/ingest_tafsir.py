"""Ingest 5 Quran Tafsirs (7 editions) into PostgreSQL + Qdrant.

Uses two APIs:
  - api.quran.com (Ibn Kathir Arabic/English, Maarif-ul-Quran, Al-Sa'di, Al-Qurtubi)
  - alquran.cloud (Al-Jalalayn Arabic/English)

Each ayah's tafsir becomes one chunk, embedded and stored alongside Quran/Hadith data.

Usage (from project root):
    python scripts/ingest_tafsir.py
"""

import asyncio
import logging
import re
import sys
import uuid
from html import unescape
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

from app.database import async_session, engine  # noqa: E402
from app.models.db import Base, Book, Chunk, Source  # noqa: E402
from app.services.embedding import embed_texts  # noqa: E402
from app.services.vector_store import upsert_points  # noqa: E402

TOTAL_SURAHS = 114
BATCH_CONCURRENCY = 5
BATCH_DELAY = 1.0

TAFSIRS = [
    # Quran Foundation API (api.quran.com)
    {"name": "Tafsir Ibn Kathir", "author": "Hafiz Ibn Kathir", "language": "arabic", "source": "quran_com", "resource_id": 14},
    {"name": "Tafsir Ibn Kathir (Abridged)", "author": "Hafiz Ibn Kathir", "language": "english", "source": "quran_com", "resource_id": 169},
    {"name": "Ma'arif al-Qur'an", "author": "Mufti Muhammad Shafi", "language": "english", "source": "quran_com", "resource_id": 168},
    {"name": "Tafsir Al-Sa'di", "author": "Abdur Rahman Al-Sa'di", "language": "arabic", "source": "quran_com", "resource_id": 91},
    {"name": "Tafsir Al-Qurtubi", "author": "Imam Al-Qurtubi", "language": "arabic", "source": "quran_com", "resource_id": 90},
    # alquran.cloud API
    {"name": "Tafsir Al-Jalalayn", "author": "Al-Mahalli & As-Suyuti", "language": "arabic", "source": "alquran_cloud", "edition": "ar.jalalayn"},
    {"name": "Tafsir Al-Jalalayn (English)", "author": "Al-Mahalli & As-Suyuti", "language": "english", "source": "alquran_cloud", "edition": "en.jalalayn"},
]

# fmt: off
SURAH_NAMES = [
    "Al-Fatihah", "Al-Baqarah", "Aal-E-Imran", "An-Nisa", "Al-Ma'idah",
    "Al-An'am", "Al-A'raf", "Al-Anfal", "At-Tawbah", "Yunus",
    "Hud", "Yusuf", "Ar-Ra'd", "Ibrahim", "Al-Hijr",
    "An-Nahl", "Al-Isra", "Al-Kahf", "Maryam", "Ta-Ha",
    "Al-Anbiya", "Al-Hajj", "Al-Mu'minun", "An-Nur", "Al-Furqan",
    "Ash-Shu'ara", "An-Naml", "Al-Qasas", "Al-Ankabut", "Ar-Rum",
    "Luqman", "As-Sajdah", "Al-Ahzab", "Saba", "Fatir",
    "Ya-Sin", "As-Saffat", "Sad", "Az-Zumar", "Ghafir",
    "Fussilat", "Ash-Shura", "Az-Zukhruf", "Ad-Dukhan", "Al-Jathiyah",
    "Al-Ahqaf", "Muhammad", "Al-Fath", "Al-Hujurat", "Qaf",
    "Adh-Dhariyat", "At-Tur", "An-Najm", "Al-Qamar", "Ar-Rahman",
    "Al-Waqi'ah", "Al-Hadid", "Al-Mujadila", "Al-Hashr", "Al-Mumtahanah",
    "As-Saf", "Al-Jumu'ah", "Al-Munafiqun", "At-Taghabun", "At-Talaq",
    "At-Tahrim", "Al-Mulk", "Al-Qalam", "Al-Haqqah", "Al-Ma'arij",
    "Nuh", "Al-Jinn", "Al-Muzzammil", "Al-Muddaththir", "Al-Qiyamah",
    "Al-Insan", "Al-Mursalat", "An-Naba", "An-Nazi'at", "Abasa",
    "At-Takwir", "Al-Infitar", "Al-Mutaffifin", "Al-Inshiqaq", "Al-Buruj",
    "At-Tariq", "Al-A'la", "Al-Ghashiyah", "Al-Fajr", "Al-Balad",
    "Ash-Shams", "Al-Layl", "Ad-Duhaa", "Ash-Sharh", "At-Tin",
    "Al-Alaq", "Al-Qadr", "Al-Bayyinah", "Az-Zalzalah", "Al-Adiyat",
    "Al-Qari'ah", "At-Takathur", "Al-Asr", "Al-Humazah", "Al-Fil",
    "Quraysh", "Al-Ma'un", "Al-Kawthar", "Al-Kafirun", "An-Nasr",
    "Al-Masad", "Al-Ikhlas", "Al-Falaq", "An-Nas",
]
# fmt: on

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    text = _HTML_TAG_RE.sub("", text)
    text = unescape(text)
    return text.strip()


# ---------------------------------------------------------------------------
# Fetching — quran.com API
# ---------------------------------------------------------------------------

async def fetch_chapter_quran_com(
    client: httpx.AsyncClient, resource_id: int, chapter: int,
) -> list[dict]:
    """Fetch all ayah tafsirs for one chapter from api.quran.com. Handles pagination."""
    all_tafsirs = []
    page = 1

    while True:
        url = f"https://api.quran.com/api/v4/tafsirs/{resource_id}/by_chapter/{chapter}"
        resp = await client.get(url, params={"page": page, "per_page": 50})
        resp.raise_for_status()
        data = resp.json()

        tafsirs = data.get("tafsirs", [])
        all_tafsirs.extend(tafsirs)

        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return all_tafsirs


async def fetch_all_quran_com(
    client: httpx.AsyncClient, resource_id: int, tafsir_name: str,
) -> list[dict]:
    """Fetch tafsir for all 114 surahs from api.quran.com in batches."""
    all_entries = []

    for i in range(1, TOTAL_SURAHS + 1, BATCH_CONCURRENCY):
        batch_end = min(i + BATCH_CONCURRENCY, TOTAL_SURAHS + 1)
        logger.info(
            "[%s] Fetching chapters %d-%d from quran.com...",
            tafsir_name, i, batch_end - 1,
        )

        tasks = [
            fetch_chapter_quran_com(client, resource_id, ch)
            for ch in range(i, batch_end)
        ]
        results = await asyncio.gather(*tasks)
        for chapter_tafsirs in results:
            all_entries.extend(chapter_tafsirs)

        if batch_end <= TOTAL_SURAHS:
            await asyncio.sleep(BATCH_DELAY)

    logger.info("[%s] Fetched %d tafsir entries from quran.com.", tafsir_name, len(all_entries))
    return all_entries


# ---------------------------------------------------------------------------
# Fetching — alquran.cloud API
# ---------------------------------------------------------------------------

async def fetch_surah_alquran_cloud(
    client: httpx.AsyncClient, edition: str, surah_number: int,
) -> list[dict]:
    """Fetch one surah's tafsir from alquran.cloud."""
    url = f"https://api.alquran.cloud/v1/surah/{surah_number}/{edition}"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["ayahs"]


async def fetch_all_alquran_cloud(
    client: httpx.AsyncClient, edition: str, tafsir_name: str,
) -> list[dict]:
    """Fetch tafsir for all 114 surahs from alquran.cloud in batches."""
    all_ayahs = []

    for i in range(1, TOTAL_SURAHS + 1, BATCH_CONCURRENCY):
        batch_end = min(i + BATCH_CONCURRENCY, TOTAL_SURAHS + 1)
        logger.info(
            "[%s] Fetching surahs %d-%d from alquran.cloud...",
            tafsir_name, i, batch_end - 1,
        )

        tasks = [
            fetch_surah_alquran_cloud(client, edition, s)
            for s in range(i, batch_end)
        ]
        results = await asyncio.gather(*tasks)
        for surah_ayahs in results:
            all_ayahs.extend(surah_ayahs)

        if batch_end <= TOTAL_SURAHS:
            await asyncio.sleep(BATCH_DELAY)

    logger.info("[%s] Fetched %d tafsir entries from alquran.cloud.", tafsir_name, len(all_ayahs))
    return all_ayahs


# ---------------------------------------------------------------------------
# Chunk building
# ---------------------------------------------------------------------------

def build_chunks_quran_com(entries: list[dict], tafsir: dict) -> list[dict]:
    """Build one chunk per ayah tafsir entry from quran.com API data."""
    chunks = []
    language = tafsir["language"]

    for entry in entries:
        raw_text = (entry.get("text") or "").strip()
        if not raw_text:
            continue

        text = strip_html(raw_text)
        if not text:
            continue

        # verse_key is e.g. "2:255"
        verse_key = entry.get("verse_key", "")
        parts = verse_key.split(":")
        surah_num = int(parts[0]) if len(parts) == 2 else 0
        ayah_num = int(parts[1]) if len(parts) == 2 else 0
        surah_name = SURAH_NAMES[surah_num - 1] if 1 <= surah_num <= 114 else ""

        chunk = {
            "content_arabic": text if language == "arabic" else None,
            "content_english": text if language == "english" else None,
            "chunk_type": "tafsir",
            "page_number": None,
            "section": f"Tafsir of Surah {surah_name} ({surah_num}:{ayah_num})",
            "metadata_json": {
                "surah_number": surah_num,
                "surah_name_english": surah_name,
                "ayah_number": ayah_num,
                "tafsir_name": tafsir["name"],
                "tafsir_author": tafsir["author"],
            },
        }
        chunks.append(chunk)

    logger.info("[%s] Built %d chunks from quran.com data.", tafsir["name"], len(chunks))
    return chunks


def build_chunks_alquran_cloud(ayahs: list[dict], tafsir: dict, surah_lookup: bool = True) -> list[dict]:
    """Build one chunk per ayah tafsir entry from alquran.cloud API data."""
    chunks = []
    language = tafsir["language"]

    for ayah in ayahs:
        text = (ayah.get("text") or "").strip()
        if not text:
            continue

        # alquran.cloud provides surah number via ayah["surah"]["number"]
        surah_info = ayah.get("surah", {})
        surah_num = surah_info.get("number", 0) if isinstance(surah_info, dict) else 0
        ayah_num = ayah.get("numberInSurah", 0)
        surah_name = SURAH_NAMES[surah_num - 1] if 1 <= surah_num <= 114 else ""

        chunk = {
            "content_arabic": text if language == "arabic" else None,
            "content_english": text if language == "english" else None,
            "chunk_type": "tafsir",
            "page_number": None,
            "section": f"Tafsir of Surah {surah_name} ({surah_num}:{ayah_num})",
            "metadata_json": {
                "surah_number": surah_num,
                "surah_name_english": surah_name,
                "ayah_number": ayah_num,
                "tafsir_name": tafsir["name"],
                "tafsir_author": tafsir["author"],
            },
        }
        chunks.append(chunk)

    logger.info("[%s] Built %d chunks from alquran.cloud data.", tafsir["name"], len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Ingestion (embed + store)
# ---------------------------------------------------------------------------

async def ingest_chunks(chunks: list[dict], tafsir: dict) -> None:
    """Embed all chunks and store in Qdrant + PostgreSQL."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Create the book record
        book = Book(
            title=tafsir["name"],
            author=tafsir["author"],
            language=tafsir["language"],
            madhab="general",
            category="tafsir",
        )
        session.add(book)
        await session.flush()

        # Create a source record
        if tafsir["source"] == "quran_com":
            file_path = f"https://api.quran.com/api/v4/tafsirs/{tafsir['resource_id']}"
        else:
            file_path = f"https://api.alquran.cloud/v1/surah/{{surah}}/{tafsir['edition']}"

        source = Source(
            book_id=book.id,
            filename=f"tafsir-{tafsir['name'].lower().replace(' ', '-')}",
            file_type="api",
            file_path=file_path,
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
                tafsir["name"], batch_num, total_batches, len(batch),
            )

            # Build texts for embedding (use whichever language is available)
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
                    "chunk_type": "tafsir",
                    "book_title": tafsir["name"],
                    "book_author": tafsir["author"],
                    "madhab": "general",
                    "category": "tafsir",
                    "language": tafsir["language"],
                    "surah_number": meta["surah_number"],
                    "surah_name_english": meta["surah_name_english"],
                    "ayah_number": meta["ayah_number"],
                    "page_number": None,
                    "tafsir_name": meta["tafsir_name"],
                }
                payloads.append(payload)

            point_ids = await upsert_points(embeddings, payloads)
            all_point_ids.extend(point_ids)

        # Save chunk records to PostgreSQL
        logger.info(
            "[%s] Saving %d chunk records to PostgreSQL...",
            tafsir["name"], len(chunks),
        )
        for c, point_id in zip(chunks, all_point_ids):
            db_chunk = Chunk(
                source_id=source.id,
                content_arabic=c["content_arabic"],
                content_english=c["content_english"],
                chunk_type="tafsir",
                page_number=None,
                section=c.get("section"),
                metadata_json=c["metadata_json"],
                qdrant_point_id=uuid.UUID(point_id),
            )
            session.add(db_chunk)

        source.status = "completed"
        await session.commit()

    logger.info(
        "[%s] Ingestion complete (%d chunks).", tafsir["name"], len(chunks),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    logger.info("Starting Quran Tafsir ingestion (7 editions)...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for tafsir in TAFSIRS:
            logger.info("=== Processing %s (%s) ===", tafsir["name"], tafsir["language"])

            # 1. Fetch from appropriate API
            if tafsir["source"] == "quran_com":
                entries = await fetch_all_quran_com(
                    client, tafsir["resource_id"], tafsir["name"],
                )
                chunks = build_chunks_quran_com(entries, tafsir)
            else:
                ayahs = await fetch_all_alquran_cloud(
                    client, tafsir["edition"], tafsir["name"],
                )
                chunks = build_chunks_alquran_cloud(ayahs, tafsir)

            if not chunks:
                logger.warning("[%s] No chunks built — skipping.", tafsir["name"])
                continue

            # 2. Embed and store
            await ingest_chunks(chunks, tafsir)

            logger.info("=== Done with %s ===\n", tafsir["name"])

    await engine.dispose()
    logger.info("All tafsir editions ingested successfully!")


if __name__ == "__main__":
    asyncio.run(main())
