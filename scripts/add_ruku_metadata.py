"""One-time migration: add `ruku` field to all existing Quran ayah points in Qdrant.

Fetches ruku data from alquran.cloud API, builds a (surah, ayah) → ruku mapping,
then updates each existing ayah point via set_payload.

Safe to re-run (idempotent — just overwrites the ruku field).

Usage (from project root):
    python scripts/add_ruku_metadata.py
"""

import asyncio
import logging
import sys
from pathlib import Path

import httpx

# Add backend to path so we can import app modules
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.vector_store import get_client, COLLECTION_NAME
from qdrant_client.models import FieldCondition, Filter, MatchValue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

API_BASE = "https://api.alquran.cloud/v1"
ARABIC_EDITION = "quran-uthmani"
TOTAL_SURAHS = 114


async def fetch_ruku_mapping() -> dict[tuple[int, int], int]:
    """Fetch all surahs and build a (surah_number, ayah_number) → ruku mapping."""
    mapping: dict[tuple[int, int], int] = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        batch_size = 5
        for i in range(1, TOTAL_SURAHS + 1, batch_size):
            batch_end = min(i + batch_size, TOTAL_SURAHS + 1)
            logger.info("Fetching ruku data for surahs %d-%d...", i, batch_end - 1)

            tasks = []
            for n in range(i, batch_end):
                url = f"{API_BASE}/surah/{n}/{ARABIC_EDITION}"
                tasks.append(client.get(url))

            responses = await asyncio.gather(*tasks)

            for resp in responses:
                resp.raise_for_status()
                data = resp.json()
                if data["code"] != 200:
                    raise RuntimeError(f"API error: {data}")

                surah_data = data["data"]
                surah_num = surah_data["number"]
                for ayah in surah_data["ayahs"]:
                    ayah_num = ayah["numberInSurah"]
                    ruku = ayah["ruku"]
                    mapping[(surah_num, ayah_num)] = ruku

            if batch_end <= TOTAL_SURAHS:
                await asyncio.sleep(1.0)

    logger.info("Built ruku mapping for %d ayahs.", len(mapping))
    return mapping


async def update_qdrant_points(mapping: dict[tuple[int, int], int]) -> None:
    """Scroll all ayah points in Qdrant and add the ruku field."""
    client = get_client()

    scroll_filter = Filter(
        must=[FieldCondition(key="chunk_type", match=MatchValue(value="ayah"))]
    )

    offset = None
    batch_size = 250
    updated = 0
    skipped = 0
    pending_updates: list[tuple[str, int]] = []

    while True:
        results, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=scroll_filter,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in results:
            payload = point.payload or {}
            surah_num = payload.get("surah_number")
            ayah_num = payload.get("ayah_number")

            if surah_num is None or ayah_num is None:
                skipped += 1
                continue

            key = (int(surah_num), int(ayah_num))
            ruku = mapping.get(key)
            if ruku is None:
                logger.warning("No ruku found for %s — skipping", key)
                skipped += 1
                continue

            pending_updates.append((str(point.id), ruku))

            # Flush in batches of 100
            if len(pending_updates) >= 100:
                _flush_updates(client, pending_updates)
                updated += len(pending_updates)
                logger.info("Updated %d points so far...", updated)
                pending_updates.clear()

        if next_offset is None:
            break
        offset = next_offset

    # Flush remaining
    if pending_updates:
        _flush_updates(client, pending_updates)
        updated += len(pending_updates)

    logger.info("Done. Updated %d ayah points, skipped %d.", updated, skipped)


def _flush_updates(client, updates: list[tuple[str, int]]) -> None:
    """Batch set_payload calls to Qdrant."""
    for point_id, ruku in updates:
        client.set_payload(
            collection_name=COLLECTION_NAME,
            payload={"ruku": ruku},
            points=[point_id],
        )


async def main():
    logger.info("Starting ruku metadata migration...")

    # 1. Fetch ruku data from API
    mapping = await fetch_ruku_mapping()

    # 2. Update existing Qdrant points
    await update_qdrant_points(mapping)

    logger.info("Migration complete!")


if __name__ == "__main__":
    asyncio.run(main())
