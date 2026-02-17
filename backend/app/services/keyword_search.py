"""Keyword search using Qdrant's scroll API for exhaustive matching.

Used for counting and listing queries where vector search's top-k
is insufficient to find all relevant results.
"""

import logging
import re
import unicodedata

from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.services.query_classifier import MetadataFilter
from app.services.vector_store import get_client, COLLECTION_NAME

logger = logging.getLogger(__name__)


def _strip_diacritics(text: str) -> str:
    """Remove Arabic tashkeel/diacritics for fuzzy matching."""
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _is_latin(text: str) -> bool:
    """Check if text is primarily Latin script (needs word-boundary matching)."""
    return all(c.isascii() for c in text if c.isalpha())


def _text_matches(text: str, keywords: list[str]) -> bool:
    """Check if any keyword appears in the text (case-insensitive, diacritics-stripped).

    Latin-script keywords use word-boundary matching to avoid false positives
    (e.g. "isa" inside "disaster"). Arabic keywords use substring matching.
    """
    text_normalized = _strip_diacritics(text).lower()
    for kw in keywords:
        kw_normalized = _strip_diacritics(kw).lower()
        if _is_latin(kw_normalized):
            if re.search(r"\b" + re.escape(kw_normalized) + r"\b", text_normalized):
                return True
        else:
            if kw_normalized in text_normalized:
                return True
    return False


async def keyword_search(
    keywords: list[str],
    madhab: str | None = None,
    category: str | None = None,
    max_results: int = 100,
) -> list[dict]:
    """Scroll through all Qdrant points and return those matching any keyword.

    Returns results in the same shape as vector_store.search:
    [{"id": str, "score": float, "payload": dict}, ...]
    """
    if not keywords:
        return []

    client = get_client()

    # Build optional filter (same pattern as vector_store.search)
    must_conditions = []
    if madhab:
        must_conditions.append(
            FieldCondition(key="madhab", match=MatchValue(value=madhab))
        )
    if category:
        must_conditions.append(
            FieldCondition(key="category", match=MatchValue(value=category))
        )
    scroll_filter = Filter(must=must_conditions) if must_conditions else None

    matches: list[dict] = []
    offset = None
    batch_size = 250

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
            arabic = payload.get("content_arabic", "")
            english = payload.get("content_english", "")

            if _text_matches(arabic, keywords) or _text_matches(english, keywords):
                matches.append(
                    {
                        "id": str(point.id),
                        "score": 1.0,
                        "payload": payload,
                    }
                )
                if len(matches) >= max_results:
                    break

        if len(matches) >= max_results or next_offset is None:
            break

        offset = next_offset

    logger.info(
        "Keyword search found %d matches for keywords: %s",
        len(matches),
        keywords[:5],
    )
    return matches


async def metadata_search(
    metadata_filter: MetadataFilter,
    max_results: int = 300,
) -> list[dict]:
    """Fetch Qdrant points by payload filters (no vector search).

    Used for structural lookups like "show me surah 2" or "ayah 2:255".
    Returns results sorted by surah_number, ayah_number.
    """
    client = get_client()

    must_conditions: list[FieldCondition] = []
    if metadata_filter.surah_number is not None:
        must_conditions.append(
            FieldCondition(key="surah_number", match=MatchValue(value=metadata_filter.surah_number))
        )
    if metadata_filter.ayah_number is not None:
        must_conditions.append(
            FieldCondition(key="ayah_number", match=MatchValue(value=metadata_filter.ayah_number))
        )
    if metadata_filter.juz is not None:
        must_conditions.append(
            FieldCondition(key="juz", match=MatchValue(value=metadata_filter.juz))
        )

    if not must_conditions:
        return []

    scroll_filter = Filter(must=must_conditions)

    results_list: list[dict] = []
    offset = None
    batch_size = 250

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
            results_list.append(
                {
                    "id": str(point.id),
                    "score": 1.0,
                    "payload": point.payload or {},
                }
            )
            if len(results_list) >= max_results:
                break

        if len(results_list) >= max_results or next_offset is None:
            break

        offset = next_offset

    # Sort by Quran order
    results_list.sort(key=lambda h: (
        int(h["payload"].get("surah_number", 0)),
        int(h["payload"].get("ayah_number", 0)),
    ))

    logger.info(
        "Metadata search found %d results (filter: surah=%s, ayah=%s, juz=%s)",
        len(results_list),
        metadata_filter.surah_number,
        metadata_filter.ayah_number,
        metadata_filter.juz,
    )
    return results_list
