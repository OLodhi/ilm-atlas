import logging

from fastapi import APIRouter

from app.models.schemas import QueryRequest, QueryResponse
from app.prompts.adab_system import ADAB_SYSTEM_PROMPT
from app.services.llm import LLMError, call_llm
from app.services.rag import build_citations, finalize_citations, retrieve_and_format

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a question using RAG: classify → embed → search → LLM → respond."""
    # 1. Retrieve and format sources
    rag_result = await retrieve_and_format(
        question=request.question,
        madhab=request.madhab,
        category=request.category,
        top_k=request.top_k,
    )

    if rag_result is None:
        return QueryResponse(
            answer="I could not find any relevant sources to answer your question. "
            "Please try rephrasing your question or broadening your search.",
            citations=[],
        )

    # 2. Build LLM prompt
    prompt = ADAB_SYSTEM_PROMPT.format(
        sources=rag_result.sources_text,
        question=request.question,
        query_context=rag_result.query_context,
    )

    # 3. Call LLM
    try:
        answer = await call_llm(system_prompt=prompt, user_message=request.question)
    except LLMError as exc:
        logger.error("LLM call failed: %s", exc)
        answer = (
            "I'm sorry, the AI service is temporarily unavailable. "
            "The relevant sources have been retrieved and are shown below."
        )

    # 4. Build and finalize citations
    citations = build_citations(rag_result.hits, rag_result.intent)
    citations = await finalize_citations(answer, citations)

    return QueryResponse(answer=answer, citations=citations)
