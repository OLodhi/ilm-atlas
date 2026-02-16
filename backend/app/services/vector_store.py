import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "ilm-atlas-v1"
VECTOR_DIM = 1024  # bge-m3 output dimension

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
    return _client


async def ensure_collection():
    """Create the Qdrant collection if it doesn't exist."""
    client = get_client()
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if COLLECTION_NAME not in names:
        logger.info("Creating Qdrant collection: %s", COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
    else:
        logger.info("Qdrant collection %s already exists.", COLLECTION_NAME)


async def upsert_points(
    embeddings: list[list[float]],
    payloads: list[dict],
) -> list[str]:
    """Upsert embedding vectors with metadata payloads into Qdrant.

    Returns a list of point IDs (UUIDs as strings).
    """
    client = get_client()
    await ensure_collection()

    point_ids = [str(uuid.uuid4()) for _ in embeddings]
    points = [
        PointStruct(id=pid, vector=emb, payload=payload)
        for pid, emb, payload in zip(point_ids, embeddings, payloads)
    ]

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)

    logger.info("Upserted %d points to Qdrant.", len(points))
    return point_ids


async def search(
    query_vector: list[float],
    top_k: int = 5,
    madhab: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Search Qdrant for similar vectors with optional filtering.

    Returns a list of dicts with 'id', 'score', and 'payload'.
    """
    client = get_client()

    must_conditions = []
    if madhab:
        must_conditions.append(FieldCondition(key="madhab", match=MatchValue(value=madhab)))
    if category:
        must_conditions.append(FieldCondition(key="category", match=MatchValue(value=category)))

    query_filter = Filter(must=must_conditions) if must_conditions else None

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        query_filter=query_filter,
    )

    return [
        {
            "id": str(hit.id),
            "score": hit.score,
            "payload": hit.payload,
        }
        for hit in results.points
    ]
