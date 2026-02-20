"""Reusable RAG pipeline: classify → embed → search → diversify → expand → format.

Extracted from query.py so both the /query endpoint and /chat endpoints
can share the same retrieval logic.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from math import ceil

from app.models.schemas import Citation
from app.services.embedding import embed_texts
from app.services.keyword_search import keyword_search, metadata_search
from app.services.query_classifier import QueryIntent, classify_query
from app.services.query_expander import expand_query
from app.services.translation import translate_arabic_citations
from app.services.vector_store import fetch_passage, search

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """Result of the RAG retrieval pipeline."""
    sources_text: str              # formatted source text for LLM prompt
    query_context: str             # query context instruction
    hits: list[dict]               # raw Qdrant hits for citation building
    intent: QueryIntent            # classified intent
    citations: list[Citation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def retrieve_and_format(
    question: str,
    madhab: str | None = None,
    category: str | None = None,
    top_k: int = 10,
) -> RAGResult | None:
    """Run the full RAG retrieval pipeline and return formatted sources.

    Returns None when no sources were found (and the query isn't structural).
    """
    # 1. Classify query intent
    intent = classify_query(question)
    logger.info("Query classified: type=%s, keywords=%d", intent.query_type, len(intent.keywords))

    # Use category hint from classifier when user hasn't set an explicit filter
    if not category and intent.category_hint:
        category = intent.category_hint
        logger.info("Auto-detected category from question: %s", category)

    # 2. Structural fact (no search needed at all)
    if intent.structural_context:
        hits: list[dict] = []
        logger.info("Structural fact query — no search needed")

    # 3. Metadata lookup (skip embedding/vector search entirely)
    elif intent.query_type == "metadata" and intent.metadata_filter:
        hits = await metadata_search(
            metadata_filter=intent.metadata_filter,
            max_results=intent.max_results,
        )
        logger.info("Metadata search returned %d results", len(hits))
    else:
        hits = await _vector_search_pipeline(question, intent, madhab, category, top_k)

    if not hits and not intent.structural_context:
        return None

    # 5. Build prompt with sources
    sources_text, query_context = _build_sources_and_context(hits, intent, top_k)

    return RAGResult(
        sources_text=sources_text,
        query_context=query_context,
        hits=hits,
        intent=intent,
    )


def build_citations(hits: list[dict], intent: QueryIntent) -> list[Citation]:
    """Build citation objects from RAG hits."""
    if intent.query_type in ("counting", "listing"):
        return [_build_citation(hit) for hit in hits]
    return _build_grouped_citations(hits)


def build_numbered_citations(hits: list[dict], intent: QueryIntent) -> list[Citation]:
    """Build citations in the exact order matching [Source N] blocks.

    Mirrors the grouping logic from ``_build_sources_and_context`` so that
    citation index N in the returned list corresponds to ``[Source N]`` in the
    LLM prompt.
    """
    if intent.query_type in ("counting", "listing"):
        return [_build_citation(hit) for hit in hits]

    # Same ruku-grouping walk as _build_sources_and_context for semantic queries
    citations: list[Citation] = []
    i = 0
    while i < len(hits):
        hit = hits[i]
        payload = hit["payload"]
        ruku = payload.get("ruku")

        if ruku is not None and payload.get("chunk_type") == "ayah":
            group = [hit]
            j = i + 1
            while j < len(hits):
                next_p = hits[j]["payload"]
                if (next_p.get("ruku") == ruku
                        and next_p.get("chunk_type") == "ayah"):
                    group.append(hits[j])
                    j += 1
                else:
                    break
            # Always use passage citation for ruku groups (matches
            # _format_passage used by _build_sources_and_context)
            citations.append(_build_passage_citation(group))
            i = j
        else:
            citations.append(_build_citation(hit))
            i += 1

    return citations


async def finalize_citations(
    answer: str,
    citations: list[Citation],
    *,
    numbered: bool = False,
) -> list[Citation]:
    """Deduplicate, auto-translate, and optionally filter citations.

    When *numbered* is True the citation order already matches the ``[Source N]``
    numbering used by the LLM, so we skip both deduplication (which would shift
    indices) and the answer-text-matching reorder step.
    """
    if not numbered:
        citations = _deduplicate_citations(citations)
    citations = await translate_arabic_citations(citations)
    if not numbered:
        citations = _filter_and_order_citations(answer, citations)
    return citations


# ---------------------------------------------------------------------------
# Internals — search pipeline
# ---------------------------------------------------------------------------

async def _vector_search_pipeline(
    question: str,
    intent: QueryIntent,
    madhab: str | None,
    category: str | None,
    top_k: int,
) -> list[dict]:
    """Full vector + keyword search pipeline."""
    # Expand query for better retrieval (semantic queries only)
    expanded_phrases = await expand_query(question)

    # Embed original + expanded phrases in one batch
    all_phrases = [question] + expanded_phrases
    all_vectors = embed_texts(all_phrases)

    # Auto-scale top_k based on sub-topic count
    effective_top_k = min(max(top_k, len(all_phrases) * 2), 20)
    if effective_top_k != top_k:
        logger.info(
            "Auto-scaled top_k: %d → %d (%d sub-topics)",
            top_k, effective_top_k, len(all_phrases),
        )

    # Search with each vector in parallel and merge results (keep highest score)
    search_limit = effective_top_k * 3
    search_tasks = [
        search(query_vector=vec, top_k=search_limit, madhab=madhab, category=category)
        for vec in all_vectors
    ]
    all_results = await asyncio.gather(*search_tasks)

    all_hits: dict[str, dict] = {}
    for hits_batch in all_results:
        for hit in hits_batch:
            pid = hit["id"]
            if pid not in all_hits or hit["score"] > all_hits[pid]["score"]:
                all_hits[pid] = hit

    vector_hits = sorted(all_hits.values(), key=lambda h: h["score"], reverse=True)

    # Supplementary Quran search + source diversification (semantic only)
    if intent.query_type not in ("counting", "listing"):
        quran_count = sum(
            1 for h in vector_hits[:effective_top_k]
            if h["payload"].get("chunk_type") == "ayah"
        )
        quran_quota = ceil(effective_top_k * 0.4)

        if quran_count < quran_quota and not category:
            supp_hits = await search(
                query_vector=all_vectors[0],
                top_k=search_limit,
                madhab=madhab,
                category="quran",
            )
            for hit in supp_hits:
                pid = hit["id"]
                if pid not in all_hits or hit["score"] > all_hits[pid]["score"]:
                    all_hits[pid] = hit
            vector_hits = sorted(
                all_hits.values(), key=lambda h: h["score"], reverse=True,
            )
            logger.info(
                "Supplementary Quran search: %d quran hits in top-%d (quota %d), "
                "pool now %d",
                quran_count, effective_top_k, quran_quota, len(vector_hits),
            )

        vector_hits = _diversify_sources(vector_hits, effective_top_k)
    else:
        vector_hits = vector_hits[:top_k]

    # Expand ayah hits to full ruku passages (semantic queries only)
    if intent.query_type not in ("counting", "listing") and any(
        h["payload"].get("ruku") for h in vector_hits
    ):
        vector_hits = await _expand_to_passages(vector_hits, effective_top_k)

    # Keyword search (for counting/listing queries with keywords)
    if intent.query_type in ("counting", "listing") and intent.keywords:
        kw_hits = await keyword_search(
            keywords=intent.keywords,
            madhab=madhab,
            category=category,
            max_results=intent.max_results,
        )
        hits = _merge_keyword_priority(vector_hits, kw_hits, intent.max_results)
        hits.sort(key=lambda h: (
            int(h["payload"].get("surah_number", 0)),
            int(h["payload"].get("ayah_number", 0)),
        ))
        logger.info(
            "Hybrid search: %d vector + %d keyword = %d merged (keyword-only)",
            len(vector_hits), len(kw_hits), len(hits),
        )
    else:
        hits = vector_hits

    return hits


# ---------------------------------------------------------------------------
# Internals — formatting
# ---------------------------------------------------------------------------

def _build_sources_and_context(
    hits: list[dict],
    intent: QueryIntent,
    top_k: int,
) -> tuple[str, str]:
    """Build the sources_text and query_context strings for the LLM prompt."""
    if intent.structural_context:
        sources_text = (
            f"[Database Metadata — Structural Fact]\n"
            f"{intent.structural_context}\n"
            f"This information comes from the Ilm Atlas database structure."
        )
        query_context = (
            "This is a structural fact about the Quran answered from the database. "
            "The factual answer is provided in the sources above — present it "
            "confidently as an authoritative fact. Do NOT say the sources are insufficient."
        )
        return sources_text, query_context

    if intent.query_type in ("counting", "listing"):
        source_blocks = [_format_source(hit, i + 1) for i, hit in enumerate(hits)]
        sources_text = "\n\n---\n\n".join(source_blocks)
    else:
        source_blocks = []
        source_idx = 1
        i = 0
        while i < len(hits):
            hit = hits[i]
            ruku = hit["payload"].get("ruku")
            if ruku is not None and hit["payload"].get("chunk_type") == "ayah":
                group = [hit]
                j = i + 1
                while j < len(hits):
                    next_hit = hits[j]
                    if (next_hit["payload"].get("ruku") == ruku
                            and next_hit["payload"].get("chunk_type") == "ayah"):
                        group.append(next_hit)
                        j += 1
                    else:
                        break
                source_blocks.append(_format_passage(group, source_idx))
                source_idx += 1
                i = j
            else:
                source_blocks.append(_format_source(hit, source_idx))
                source_idx += 1
                i += 1
        sources_text = "\n\n---\n\n".join(source_blocks)

    metadata_desc = ""
    if intent.query_type == "metadata" and intent.metadata_filter and hits:
        mf = intent.metadata_filter
        first_payload = hits[0]["payload"]
        surah_name = first_payload.get("surah_name_english", "")
        parts = []
        if mf.surah_number is not None:
            label = f"Surah {surah_name} (#{mf.surah_number})" if surah_name else f"Surah {mf.surah_number}"
            parts.append(label)
        if mf.ayah_number is not None:
            parts.append(f"Ayah {mf.ayah_number}")
        if mf.juz is not None:
            parts.append(f"Juz {mf.juz}")
        if parts:
            metadata_desc = f" from {', '.join(parts)}"

        metadata_header = (
            f"[Database Metadata]\n"
            f"The following {len(hits)} ayah(s) were retrieved{metadata_desc}. "
            f"Surah {surah_name} is surah number {mf.surah_number} out of 114 surahs in the Quran."
            if mf.surah_number and surah_name else
            f"[Database Metadata]\n"
            f"The following {len(hits)} ayah(s) were retrieved{metadata_desc}."
        )
        sources_text = metadata_header + "\n\n---\n\n" + sources_text
        query_context = _build_query_context(intent.query_type, len(hits), metadata_desc)
    else:
        query_context = _build_query_context(intent.query_type, len(hits))

    return sources_text, query_context


# ---------------------------------------------------------------------------
# Internals — helpers (moved from query.py)
# ---------------------------------------------------------------------------

def _format_source(hit: dict, index: int) -> str:
    """Format a single Qdrant hit into a source text block for the LLM prompt."""
    payload = hit["payload"]
    parts = [f"[Source {index}]"]

    chunk_type = payload.get("chunk_type", "")
    if chunk_type == "ayah":
        surah = payload.get("surah_name_english", "")
        surah_num = payload.get("surah_number", "")
        ayah_num = payload.get("ayah_number", "")
        parts.append(f"Quran, Surah {surah} ({surah_num}:{ayah_num})")
    elif chunk_type == "hadith":
        book_title = payload.get("book_title", "Unknown")
        meta = payload.get("metadata", {}) or {}
        hadith_num = payload.get("hadith_number") or meta.get("hadith_number", "")
        parts.append(f"{book_title}, Hadith {hadith_num}")
    elif chunk_type == "tafsir":
        book_title = payload.get("book_title", "Unknown Tafsir")
        surah = payload.get("surah_name_english", "")
        surah_num = payload.get("surah_number", 0)
        ayah_num = payload.get("ayah_number", 0)
        if surah_num and surah:
            parts.append(f"{book_title}, Surah {surah} ({surah_num}:{ayah_num})")
        elif surah_num:
            parts.append(f"{book_title} ({surah_num}:{ayah_num})")
        else:
            parts.append(book_title)
    else:
        book_title = payload.get("book_title", "Unknown")
        page = payload.get("page_number", "")
        parts.append(f"{book_title}, p. {page}" if page else book_title)

    arabic = payload.get("content_arabic", "")
    english = payload.get("content_english", "")

    if arabic:
        parts.append(f"Arabic: {arabic}")
    if english:
        parts.append(f"English: {english}")

    return "\n".join(parts)


def _build_citation(hit: dict) -> Citation:
    """Build a Citation object from a Qdrant search hit."""
    payload = hit["payload"]
    chunk_type = payload.get("chunk_type", "paragraph")

    if chunk_type == "ayah":
        surah = payload.get("surah_name_english", "")
        surah_num = payload.get("surah_number", "")
        ayah_num = payload.get("ayah_number", "")
        source_label = f"Quran {surah_num}:{ayah_num} (Surah {surah})"
    elif chunk_type == "hadith":
        book_title = payload.get("book_title", "Unknown")
        meta = payload.get("metadata", {}) or {}
        hadith_num = payload.get("hadith_number") or meta.get("hadith_number", "")
        source_label = f"{book_title}, Hadith {hadith_num}"
    elif chunk_type == "tafsir":
        book_title = payload.get("book_title", "Unknown Tafsir")
        surah = payload.get("surah_name_english", "")
        surah_num = payload.get("surah_number", 0)
        ayah_num = payload.get("ayah_number", 0)
        if surah_num and surah:
            source_label = f"{book_title}, Surah {surah} ({surah_num}:{ayah_num})"
        elif surah_num:
            source_label = f"{book_title} ({surah_num}:{ayah_num})"
        else:
            source_label = book_title
    else:
        book_title = payload.get("book_title", "Unknown")
        page = payload.get("page_number")
        source_label = f"{book_title}, p. {page}" if page else book_title

    return Citation(
        text_arabic=payload.get("content_arabic") or None,
        text_english=payload.get("content_english") or None,
        source=source_label,
        chunk_type=chunk_type,
        metadata=payload.get("metadata"),
    )


def _build_grouped_citations(hits: list[dict]) -> list[Citation]:
    """Build citations, grouping consecutive same-ruku ayahs into one citation."""
    citations: list[Citation] = []
    i = 0
    while i < len(hits):
        hit = hits[i]
        payload = hit["payload"]
        ruku = payload.get("ruku")

        if ruku is not None and payload.get("chunk_type") == "ayah":
            group = [hit]
            j = i + 1
            while j < len(hits):
                next_p = hits[j]["payload"]
                if (next_p.get("ruku") == ruku
                        and next_p.get("chunk_type") == "ayah"):
                    group.append(hits[j])
                    j += 1
                else:
                    break

            if len(group) == 1:
                citations.append(_build_citation(hit))
            else:
                citations.append(_build_passage_citation(group))
            i = j
        else:
            citations.append(_build_citation(hit))
            i += 1

    return citations


def _build_passage_citation(hits: list[dict]) -> Citation:
    """Build a single Citation from a group of same-ruku ayahs."""
    first = hits[0]["payload"]
    last = hits[-1]["payload"]
    surah = first.get("surah_name_english", "")
    surah_num = first.get("surah_number", "")
    first_ayah = first.get("ayah_number", "")
    last_ayah = last.get("ayah_number", "")

    source_label = f"Quran {surah_num}:{first_ayah}-{last_ayah} (Surah {surah})"

    arabic_parts = []
    english_parts = []
    for hit in hits:
        p = hit["payload"]
        ayah_num = p.get("ayah_number", "")
        arabic = p.get("content_arabic", "")
        english = p.get("content_english", "")
        if arabic:
            arabic_parts.append(arabic)
        if english:
            english_parts.append(f"({surah_num}:{ayah_num}) {english}")

    return Citation(
        text_arabic="\n".join(arabic_parts) or None,
        text_english="\n".join(english_parts) or None,
        source=source_label,
        chunk_type="ayah",
        metadata=None,
    )


def _diversify_sources(hits: list[dict], top_k: int) -> list[dict]:
    """Ensure three-tier source diversity: Quran → Hadith → Tafsir → Other."""
    quran_hits = [h for h in hits if h["payload"].get("chunk_type") == "ayah"]
    hadith_hits = [h for h in hits if h["payload"].get("chunk_type") == "hadith"]
    tafsir_hits = [h for h in hits if h["payload"].get("chunk_type") == "tafsir"]
    other_hits = [
        h for h in hits
        if h["payload"].get("chunk_type") not in ("ayah", "hadith", "tafsir")
    ]

    quran_quota = min(ceil(top_k * 0.4), len(quran_hits))
    hadith_quota = min(ceil(top_k * 0.3), len(hadith_hits))
    tafsir_quota = min(ceil(top_k * 0.2), len(tafsir_hits))

    selected: set[str] = set()
    result: list[dict] = []

    for h in quran_hits[:quran_quota]:
        result.append(h)
        selected.add(h["id"])

    for h in hadith_hits[:hadith_quota]:
        result.append(h)
        selected.add(h["id"])

    for h in tafsir_hits[:tafsir_quota]:
        result.append(h)
        selected.add(h["id"])

    remaining = top_k - len(result)
    for h in hits:
        if remaining <= 0:
            break
        if h["id"] not in selected:
            result.append(h)
            selected.add(h["id"])
            remaining -= 1

    def _tier(chunk_type: str | None) -> list[dict]:
        return sorted(
            [h for h in result if h["payload"].get("chunk_type") == chunk_type],
            key=lambda h: h["score"], reverse=True,
        )

    quran_final = _tier("ayah")
    hadith_final = _tier("hadith")
    tafsir_final = _tier("tafsir")
    other_final = sorted(
        [h for h in result if h["payload"].get("chunk_type") not in ("ayah", "hadith", "tafsir")],
        key=lambda h: h["score"], reverse=True,
    )

    logger.info(
        "Source diversification: %d quran + %d hadith + %d tafsir + %d other = %d total (from %d candidates)",
        len(quran_final), len(hadith_final), len(tafsir_final), len(other_final),
        len(quran_final) + len(hadith_final) + len(tafsir_final) + len(other_final),
        len(hits),
    )
    return quran_final + hadith_final + tafsir_final + other_final


def _find_citation_in_answer(answer: str, citation: Citation) -> int | None:
    """Find the earliest char position where this citation is referenced in the answer."""
    source = citation.source
    chunk_type = citation.chunk_type or ""

    if chunk_type == "ayah":
        m = re.match(r"Quran (\d+):(\d+)(?:-(\d+))? ", source)
        if m:
            surah_num, first_ayah, last_ayah = m.group(1), m.group(2), m.group(3)
            if last_ayah:
                for ayah in range(int(first_ayah), int(last_ayah) + 1):
                    pattern = rf"(?<!\d){re.escape(surah_num)}:{ayah}(?!\d)"
                    match = re.search(pattern, answer)
                    if match:
                        return match.start()
            else:
                pattern = rf"(?<!\d){re.escape(surah_num)}:{re.escape(first_ayah)}(?!\d)"
                match = re.search(pattern, answer)
                if match:
                    return match.start()

    elif chunk_type == "hadith":
        m = re.search(r"Hadith (\d+)", source)
        if m:
            hadith_num = m.group(1)
            pattern = rf"Hadith\s+{re.escape(hadith_num)}(?!\d)"
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                return match.start()
        book_title = source.split(",")[0].strip()
        if book_title:
            match = re.search(re.escape(book_title), answer, re.IGNORECASE)
            if match:
                return match.start()

    elif chunk_type == "tafsir":
        book_title = source.split(",")[0].strip()
        if book_title:
            match = re.search(re.escape(book_title), answer, re.IGNORECASE)
            if match:
                return match.start()

    else:
        book_title = source.split(",")[0].strip()
        if book_title:
            match = re.search(re.escape(book_title), answer, re.IGNORECASE)
            if match:
                return match.start()

    return None


def _deduplicate_citations(citations: list[Citation]) -> list[Citation]:
    """Remove citations with identical source labels, keeping first occurrence."""
    seen: set[str] = set()
    result: list[Citation] = []
    for cit in citations:
        if cit.source not in seen:
            seen.add(cit.source)
            result.append(cit)

    if len(result) < len(citations):
        logger.info(
            "Citation dedup: %d → %d (removed %d duplicates)",
            len(citations), len(result), len(citations) - len(result),
        )
    return result


def _filter_and_order_citations(answer: str, citations: list[Citation]) -> list[Citation]:
    """Keep only citations the LLM actually referenced, ordered by first appearance."""
    matched: list[tuple[int, Citation]] = []
    for cit in citations:
        pos = _find_citation_in_answer(answer, cit)
        if pos is not None:
            matched.append((pos, cit))

    matched.sort(key=lambda t: t[0])

    logger.info(
        "Citation filtering: %d of %d citations referenced in answer",
        len(matched), len(citations),
    )
    return [cit for _, cit in matched]


def _merge_keyword_priority(
    vector_hits: list[dict],
    keyword_hits: list[dict],
    max_results: int,
) -> list[dict]:
    """Merge results, keeping only hits confirmed by keyword search."""
    kw_ids = {h["id"] for h in keyword_hits}
    seen: dict[str, dict] = {}

    for hit in keyword_hits:
        seen[hit["id"]] = hit

    for hit in vector_hits:
        pid = hit["id"]
        if pid in kw_ids and hit["score"] > seen[pid]["score"]:
            seen[pid] = hit

    merged = sorted(seen.values(), key=lambda h: h["score"], reverse=True)
    return merged[:max_results]


def _build_query_context(query_type: str, total_sources: int, metadata_desc: str = "") -> str:
    """Build the query_context string injected into the LLM prompt."""
    if query_type == "metadata":
        return (
            f"This is a structural/metadata lookup. The system has directly "
            f"retrieved {total_sources} ayah(s){metadata_desc} from the database. "
            "These are the exact results the user asked for — present them "
            "confidently with full citations. Do NOT say the sources are "
            "insufficient; the metadata lookup already answered the question."
        )
    if query_type == "counting":
        return (
            f"This is a counting query. Exactly {total_sources} relevant sources "
            "have been found and provided below. Report this exact number — "
            "do NOT recount manually. Present the answer and list the sources."
        )
    if query_type == "listing":
        return (
            f"Exactly {total_sources} relevant sources have been found and "
            "provided below. List every single one systematically with full citations."
        )
    return (
        f"This is a semantic search query. {total_sources} relevant sources "
        "have been retrieved from the Quran and Hadith collections. "
        "Synthesize a comprehensive answer drawing on ALL provided sources. "
        "Focus on what the sources contain. If some aspect of the question "
        "is not covered, mention it briefly at the end — do NOT lead with "
        "gaps or caveats, and do NOT list out every possible missing detail."
    )


async def _expand_to_passages(
    vector_hits: list[dict],
    top_k: int,
) -> list[dict]:
    """Expand individual ayah hits into full ruku passages."""
    ruku_best: dict[int, float] = {}
    for hit in vector_hits:
        ruku = hit["payload"].get("ruku")
        if ruku is None or hit["payload"].get("chunk_type") != "ayah":
            continue
        ruku = int(ruku)
        if ruku not in ruku_best or hit["score"] > ruku_best[ruku]:
            ruku_best[ruku] = hit["score"]

    if not ruku_best:
        return vector_hits

    top_rukus = sorted(ruku_best, key=lambda r: ruku_best[r], reverse=True)[:3]

    expanded: list[dict] = []
    seen_ids: set[str] = set()
    passage_results = await asyncio.gather(
        *[fetch_passage(ruku_num) for ruku_num in top_rukus]
    )
    for passage_hits in passage_results:
        for h in passage_hits:
            if h["id"] not in seen_ids:
                original = next(
                    (v for v in vector_hits if v["id"] == h["id"]),
                    None,
                )
                if original:
                    h["score"] = original["score"]
                seen_ids.add(h["id"])
                expanded.append(h)

    for hit in vector_hits:
        if hit["id"] not in seen_ids:
            expanded.append(hit)
            seen_ids.add(hit["id"])

    logger.info(
        "Passage expansion: %d hits → %d ayahs across %d ruku(s)",
        len(vector_hits), len(expanded), len(top_rukus),
    )
    return expanded


def _format_passage(hits: list[dict], index: int) -> str:
    """Format a group of ayahs from the same ruku as one passage block."""
    if not hits:
        return ""

    first = hits[0]["payload"]
    last = hits[-1]["payload"]
    surah = first.get("surah_name_english", "")
    surah_num = first.get("surah_number", "")
    first_ayah = first.get("ayah_number", "")
    last_ayah = last.get("ayah_number", "")

    if first_ayah == last_ayah:
        ref = f"{surah_num}:{first_ayah}"
    else:
        ref = f"{surah_num}:{first_ayah}-{last_ayah}"

    parts = [f"[Source {index}]", f"Quran, Surah {surah} ({ref})"]

    for hit in hits:
        p = hit["payload"]
        ayah_num = p.get("ayah_number", "")
        arabic = p.get("content_arabic", "")
        english = p.get("content_english", "")
        parts.append(f"  {surah_num}:{ayah_num}")
        if arabic:
            parts.append(f"  Arabic: {arabic}")
        if english:
            parts.append(f"  English: {english}")

    return "\n".join(parts)
