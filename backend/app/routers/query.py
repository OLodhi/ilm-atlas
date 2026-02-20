import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_optional_user
from app.middleware.rate_limit import limiter
from app.models.db import User
from app.models.schemas import Citation, QueryRequest, QueryResponse
from app.prompts.adab_system import ADAB_SYSTEM_PROMPT
from app.services.auth.usage import check_and_increment_usage
from app.services.llm import LLMError, call_llm
from app.services.rag import build_numbered_citations, finalize_citations, retrieve_and_format

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
@limiter.limit("10/minute")
async def query(
    request: Request,
    body: QueryRequest,
    user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Answer a question using RAG: classify → embed → search → LLM → respond."""
    # If authenticated, check per-user daily limits
    if user:
        allowed, used, limit = await check_and_increment_usage(user, session)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Daily query limit reached ({limit}/{limit}). Resets at midnight UTC.",
            )

    # 1. Retrieve and format sources
    rag_result = await retrieve_and_format(
        question=body.question,
        madhab=body.madhab,
        category=body.category,
        top_k=body.top_k,
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
        question=body.question,
        query_context=rag_result.query_context,
    )

    # 3. Call LLM
    llm_failed = False
    try:
        answer = await call_llm(system_prompt=prompt, user_message=body.question)
    except LLMError as exc:
        logger.error("LLM call failed: %s", exc)
        llm_failed = True
        answer = (
            "I'm sorry, the AI service is temporarily unavailable. "
            "The relevant sources have been retrieved and are shown below."
        )

    # 4. Build and finalize citations (numbered to match [Source N] blocks)
    # Skip when the LLM failed — no [N] markers in the error message.
    citations: list[Citation] = []
    if not llm_failed:
        citations = build_numbered_citations(rag_result.hits, rag_result.intent)
        citations = await finalize_citations(answer, citations, numbered=True)

    return QueryResponse(answer=answer, citations=citations)
