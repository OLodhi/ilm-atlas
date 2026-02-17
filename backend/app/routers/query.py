import logging

from fastapi import APIRouter

from app.models.schemas import Citation, QueryRequest, QueryResponse
from app.services.embedding import embed_texts
from app.services.keyword_search import keyword_search, metadata_search
from app.services.llm import call_llm, LLMError
from app.services.query_classifier import classify_query
from app.services.query_expander import expand_query
from app.services.vector_store import fetch_passage, search
from app.prompts.adab_system import ADAB_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


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
        meta = payload.get("metadata", {})
        hadith_num = meta.get("hadith_number", "")
        parts.append(f"{book_title}, Hadith {hadith_num}")
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
        meta = payload.get("metadata", {})
        hadith_num = meta.get("hadith_number", "")
        source_label = f"{book_title}, Hadith {hadith_num}"
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

        # Group consecutive ayahs from the same ruku
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


def _merge_keyword_priority(
    vector_hits: list[dict],
    keyword_hits: list[dict],
    max_results: int,
) -> list[dict]:
    """Merge results, keeping only hits confirmed by keyword search.

    Vector hits that also appear in keyword results get their vector score
    preserved (higher relevance ranking). Vector-only hits are dropped to
    avoid noise in counting/listing queries.
    """
    kw_ids = {h["id"] for h in keyword_hits}
    seen: dict[str, dict] = {}

    # Start with all keyword hits
    for hit in keyword_hits:
        seen[hit["id"]] = hit

    # Boost keyword hits that also appeared in vector results (use higher score)
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
    return ""


async def _expand_to_passages(
    vector_hits: list[dict],
    top_k: int,
) -> list[dict]:
    """Expand individual ayah hits into full ruku passages.

    Groups hits by ruku, fetches each ruku's full ayah set,
    and returns passages ordered by the best-scoring original hit per ruku.
    Limits to the top 3 unique rukus to avoid context bloat.
    """
    # Collect unique rukus with the best score per ruku
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

    # Take top 3 rukus by score
    top_rukus = sorted(ruku_best, key=lambda r: ruku_best[r], reverse=True)[:3]

    # Fetch full passages for each ruku
    expanded: list[dict] = []
    seen_ids: set[str] = set()
    for ruku_num in top_rukus:
        passage_hits = await fetch_passage(ruku_num)
        for h in passage_hits:
            if h["id"] not in seen_ids:
                # Preserve the original vector score if this ayah was a direct hit
                original = next(
                    (v for v in vector_hits if v["id"] == h["id"]),
                    None,
                )
                if original:
                    h["score"] = original["score"]
                seen_ids.add(h["id"])
                expanded.append(h)

    # Also include any non-ayah hits (hadith, paragraph) that don't have ruku
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


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a question using RAG: classify → embed → search → LLM → respond."""
    # 1. Classify query intent
    intent = classify_query(request.question)
    logger.info("Query classified: type=%s, keywords=%d", intent.query_type, len(intent.keywords))

    # 2. Structural fact (no search needed at all)
    if intent.structural_context:
        hits = []
        logger.info("Structural fact query — no search needed")

    # 3. Metadata lookup (skip embedding/vector search entirely)
    elif intent.query_type == "metadata" and intent.metadata_filter:
        hits = await metadata_search(
            metadata_filter=intent.metadata_filter,
            max_results=intent.max_results,
        )
        logger.info("Metadata search returned %d results", len(hits))
    else:
        # 3. Expand query for better retrieval (semantic queries only)
        expanded_phrases = await expand_query(request.question)

        # 4. Embed original + expanded phrases in one batch
        all_phrases = [request.question] + expanded_phrases
        all_vectors = embed_texts(all_phrases)

        # 5. Search with each vector and merge results (keep highest score)
        all_hits: dict[str, dict] = {}
        for vec in all_vectors:
            hits_batch = await search(
                query_vector=vec,
                top_k=request.top_k,
                madhab=request.madhab,
                category=request.category,
            )
            for hit in hits_batch:
                pid = hit["id"]
                if pid not in all_hits or hit["score"] > all_hits[pid]["score"]:
                    all_hits[pid] = hit

        vector_hits = sorted(all_hits.values(), key=lambda h: h["score"], reverse=True)
        vector_hits = vector_hits[:request.top_k]

        # 5b. Expand ayah hits to full ruku passages (semantic queries only)
        if intent.query_type not in ("counting", "listing") and any(
            h["payload"].get("ruku") for h in vector_hits
        ):
            vector_hits = await _expand_to_passages(vector_hits, request.top_k)

        # 6. Keyword search (for counting/listing queries with keywords)
        if intent.query_type in ("counting", "listing") and intent.keywords:
            kw_hits = await keyword_search(
                keywords=intent.keywords,
                madhab=request.madhab,
                category=request.category,
                max_results=intent.max_results,
            )
            hits = _merge_keyword_priority(vector_hits, kw_hits, intent.max_results)
            # Sort by Quran order (surah then ayah) for consistent presentation
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

    if not hits and not intent.structural_context:
        return QueryResponse(
            answer="I could not find any relevant sources to answer your question. "
            "Please try rephrasing your question or broadening your search.",
            citations=[],
        )

    # 5. Build prompt with sources
    if intent.structural_context:
        sources_text = (
            f"[Database Metadata — Structural Fact]\n"
            f"{intent.structural_context}\n"
            f"This information comes from the Ilm Atlas database structure."
        )
    elif intent.query_type in ("counting", "listing"):
        # Individual per-hit formatting for exact counting/listing
        source_blocks = [_format_source(hit, i + 1) for i, hit in enumerate(hits)]
        sources_text = "\n\n---\n\n".join(source_blocks)
    else:
        # Group ayah hits by ruku for passage-aware formatting
        source_blocks = []
        source_idx = 1
        i = 0
        while i < len(hits):
            hit = hits[i]
            ruku = hit["payload"].get("ruku")
            if ruku is not None and hit["payload"].get("chunk_type") == "ayah":
                # Collect consecutive ayahs from the same ruku
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
    if intent.structural_context:
        # Structural fact — the answer is already in sources_text
        query_context = (
            "This is a structural fact about the Quran answered from the database. "
            "The factual answer is provided in the sources above — present it "
            "confidently as an authoritative fact. Do NOT say the sources are insufficient."
        )
    elif intent.query_type == "metadata" and intent.metadata_filter and hits:
        mf = intent.metadata_filter
        # Pull the surah name from the first hit's payload for richer context
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

        # Prepend metadata context as a source-level fact so the LLM
        # treats it as authoritative data (not overridden by Rule #1).
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

    prompt = ADAB_SYSTEM_PROMPT.format(
        sources=sources_text,
        question=request.question,
        query_context=query_context,
    )

    # 6. Call LLM
    try:
        answer = await call_llm(system_prompt=prompt, user_message=request.question)
    except LLMError as exc:
        logger.error("LLM call failed: %s", exc)
        answer = (
            "I'm sorry, the AI service is temporarily unavailable. "
            "The relevant sources have been retrieved and are shown below."
        )

    # 7. Build citations (group consecutive same-ruku ayahs for semantic queries)
    if intent.query_type in ("counting", "listing"):
        citations = [_build_citation(hit) for hit in hits]
    else:
        citations = _build_grouped_citations(hits)

    return QueryResponse(answer=answer, citations=citations)
