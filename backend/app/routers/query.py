import logging

from fastapi import APIRouter

from app.models.schemas import Citation, QueryRequest, QueryResponse
from app.services.embedding import embed_query
from app.services.llm import call_llm
from app.services.vector_store import search
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


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a question using RAG: embed → search → LLM → respond."""
    # 1. Embed the question
    query_vector = embed_query(request.question)

    # 2. Search Qdrant
    hits = await search(
        query_vector=query_vector,
        top_k=request.top_k,
        madhab=request.madhab,
        category=request.category,
    )

    if not hits:
        return QueryResponse(
            answer="I could not find any relevant sources to answer your question. "
            "Please try rephrasing your question or broadening your search.",
            citations=[],
        )

    # 3. Build prompt with sources
    source_blocks = [_format_source(hit, i + 1) for i, hit in enumerate(hits)]
    sources_text = "\n\n---\n\n".join(source_blocks)

    prompt = ADAB_SYSTEM_PROMPT.format(
        sources=sources_text,
        question=request.question,
    )

    # 4. Call LLM
    answer = await call_llm(system_prompt=prompt, user_message=request.question)

    # 5. Build citations
    citations = [_build_citation(hit) for hit in hits]

    return QueryResponse(answer=answer, citations=citations)
