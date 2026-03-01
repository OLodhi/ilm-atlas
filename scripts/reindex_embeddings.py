"""Re-index all Qdrant vectors using Voyage AI embeddings.

Scrolls through every point in the ilm-atlas-v1 collection, re-embeds the
text content via Voyage AI, and upserts the updated vectors back (preserving
point IDs and payloads).

Usage:
    Set EMBEDDING_PROVIDER=voyageai and VOYAGE_API_KEY in backend/.env
    Run: cd backend && python ../scripts/reindex_embeddings.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
logger = logging.getLogger(__name__)

from app.config import settings
from app.services.embedding import embed_texts
from app.services.vector_store import get_client, COLLECTION_NAME

# Windows asyncio compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_embeddable_text(payload: dict) -> str:
    """Reconstruct the text that should be embedded from a Qdrant payload."""
    parts = []
    if payload.get("content_arabic"):
        parts.append(payload["content_arabic"])
    if payload.get("content_english"):
        parts.append(payload["content_english"])
    return " ".join(parts) if parts else ""


async def reindex():
    if settings.embedding_provider != "voyageai":
        logger.error("EMBEDDING_PROVIDER must be 'voyageai'. Current: %s", settings.embedding_provider)
        sys.exit(1)

    client = get_client()

    # Get collection info
    info = await client.get_collection(COLLECTION_NAME)
    total_points = info.points_count
    logger.info("Collection %s has %d points to re-index", COLLECTION_NAME, total_points)

    processed = 0
    skipped = 0
    batch_size = 64  # Voyage AI batch + Qdrant scroll batch
    offset = None

    while True:
        # Scroll through points
        points, next_offset = await client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            break

        # Extract texts
        ids = []
        texts = []
        payloads = []
        for point in points:
            text = get_embeddable_text(point.payload or {})
            if not text.strip():
                skipped += 1
                continue
            ids.append(point.id)
            texts.append(text)
            payloads.append(point.payload)

        if texts:
            # Re-embed via Voyage AI
            vectors = embed_texts(texts)

            # Upsert back with same IDs and payloads
            from qdrant_client.models import PointStruct
            upsert_points = [
                PointStruct(id=pid, vector=vec, payload=pay)
                for pid, vec, pay in zip(ids, vectors, payloads)
            ]

            await client.upsert(collection_name=COLLECTION_NAME, points=upsert_points)
            processed += len(texts)

        logger.info("Progress: %d / %d processed (%d skipped)", processed, total_points, skipped)

        if next_offset is None:
            break
        offset = next_offset

    logger.info("Re-indexing complete. %d points updated, %d skipped.", processed, skipped)


if __name__ == "__main__":
    asyncio.run(reindex())
