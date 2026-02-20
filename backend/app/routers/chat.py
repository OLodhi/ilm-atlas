import asyncio
import json as json_mod
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session, get_session
from app.models.db import ChatMessage, ChatSession
from app.models.schemas import (
    ChatMessageResponse,
    ChatSendRequest,
    ChatSendResponse,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionRenameRequest,
    ChatSessionResponse,
    Citation,
)
from app.prompts.adab_chat_system import ADAB_CHAT_SYSTEM_PROMPT
from app.prompts.query_rewrite import QUERY_REWRITE_SYSTEM_PROMPT
from app.prompts.session_title import SESSION_TITLE_SYSTEM_PROMPT
from app.services.llm import LLMError, call_llm, call_llm_chat, stream_llm_chat
from app.services.rag import build_numbered_citations, finalize_citations, retrieve_and_format

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(db: AsyncSession = Depends(get_session)):
    """Create a new empty chat session."""
    session = ChatSession()
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(db: AsyncSession = Depends(get_session)):
    """List all chat sessions, most recently updated first."""
    result = await db.execute(
        select(ChatSession).order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return ChatSessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session_detail(
    session_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """Get a session with all its messages."""
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return ChatSessionDetailResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            ChatMessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=[Citation(**c) for c in m.citations_json] if m.citations_json else None,
                created_at=m.created_at,
            )
            for m in session.messages
        ],
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """Delete a session and all its messages."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def rename_session(
    session_id: UUID,
    body: ChatSessionRenameRequest,
    db: AsyncSession = Depends(get_session),
):
    """Rename a session."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.title = body.title
    await db.commit()
    await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Send message (core endpoint)
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatSendResponse,
)
async def send_message(
    session_id: UUID,
    body: ChatSendRequest,
    db: AsyncSession = Depends(get_session),
):
    """Send a user message → RAG → LLM → return assistant response."""
    # 1. Validate session
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Save user message (capture prior count before flush mutates identity map)
    prior_message_count = len(session.messages)
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=body.message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    await db.flush()

    # 3. Load conversation history (prior messages, not the one we just added)
    history_messages: list[dict[str, str]] = []
    for m in session.messages:
        # session.messages is ordered by created_at; skip our just-flushed msg
        if m.id == user_msg.id:
            continue
        history_messages.append({"role": m.role, "content": m.content})

    # 4. Rewrite follow-up queries into standalone questions for better RAG retrieval
    search_query = body.message
    if history_messages:
        search_query = await _rewrite_query(body.message, history_messages)
        logger.info("Query rewritten: %r → %r", body.message, search_query)

    # 5. RAG retrieval using the (possibly rewritten) query
    rag_result = await retrieve_and_format(
        question=search_query,
        madhab=body.madhab,
        category=body.category,
    )

    # 6. Build source-augmented current turn
    if rag_result:
        current_user_content = (
            f"## Source Texts\n{rag_result.sources_text}\n\n"
            f"## User Question\n{body.message}\n\n"
            f"{rag_result.query_context}"
        )
    else:
        current_user_content = body.message

    # 7. Build LLM messages: history (raw text) + current turn (with sources)
    llm_messages = history_messages + [
        {"role": "user", "content": current_user_content},
    ]

    # 8. Call LLM
    llm_failed = False
    try:
        answer = await call_llm_chat(
            system_prompt=ADAB_CHAT_SYSTEM_PROMPT,
            messages=llm_messages,
        )
    except LLMError as exc:
        logger.error("LLM call failed: %s", exc)
        llm_failed = True
        answer = (
            "I'm sorry, the AI service is temporarily unavailable. "
            "Please try again in a moment."
        )

    # 9. Build citations + auto-title (parallel when both needed)
    # Skip citations when the LLM failed — no [N] markers in the error message.
    citations: list[Citation] = []
    needs_title = prior_message_count == 0 and not session.title
    if rag_result and not llm_failed:
        citations = build_numbered_citations(rag_result.hits, rag_result.intent)
        if needs_title:
            citations, title = await asyncio.gather(
                finalize_citations(answer, citations, numbered=True),
                _generate_title(body.message),
            )
            session.title = title
        else:
            citations = await finalize_citations(answer, citations, numbered=True)
    elif needs_title:
        session.title = await _generate_title(body.message)

    # 10. Save assistant message
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        citations_json=[c.model_dump() for c in citations] if citations else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)

    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    await db.refresh(session)

    return ChatSendResponse(
        message=ChatMessageResponse(
            id=assistant_msg.id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            citations=citations if citations else None,
            created_at=assistant_msg.created_at,
        ),
        user_message=ChatMessageResponse(
            id=user_msg.id,
            role=user_msg.role,
            content=user_msg.content,
            citations=None,
            created_at=user_msg.created_at,
        ),
        session_id=session.id,
        session_title=session.title,
    )


async def _generate_title(question: str) -> str:
    """Generate a short session title from the first question."""
    try:
        title = await call_llm(
            system_prompt=SESSION_TITLE_SYSTEM_PROMPT,
            user_message=question,
            max_tokens=30,
            temperature=0.5,
        )
        # Clean up: strip quotes and trailing punctuation
        title = title.strip().strip('"\'').rstrip(".")
        if len(title) > 100:
            title = title[:97] + "..."
        return title
    except LLMError:
        logger.warning("Failed to generate session title, using fallback")
        fallback = question[:60]
        if len(question) > 60:
            fallback += "..."
        return fallback


async def _rewrite_query(
    follow_up: str,
    history: list[dict[str, str]],
) -> str:
    """Rewrite a follow-up message into a standalone query using conversation context.

    This ensures the RAG retrieval gets a complete question with all entities
    and context, even when the user's message is a brief follow-up like
    "What about in the Quran only?" (which needs "Isa" from history).
    """
    # Build a compact summary of recent conversation for the rewriter
    # Only use the last few turns to keep it short
    recent = history[-6:]  # last 3 exchanges max
    conv_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:300]}"
        for m in recent
    )
    user_message = (
        f"Conversation so far:\n{conv_text}\n\n"
        f"Follow-up message: {follow_up}\n\n"
        f"Rewritten standalone question:"
    )
    try:
        rewritten = await call_llm(
            system_prompt=QUERY_REWRITE_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=200,
            temperature=0.1,
        )
        rewritten = rewritten.strip().strip('"\'')
        if rewritten:
            return rewritten
    except LLMError:
        logger.warning("Query rewrite failed, using original message")
    return follow_up


# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------

def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json_mod.dumps(data)}\n\n"


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: UUID,
    body: ChatSendRequest,
    request: Request,
):
    """Send a user message and stream the assistant response via SSE.

    NOTE: This endpoint does NOT use Depends(get_session). FastAPI cleans up
    yield-dependencies when the handler returns, which is BEFORE the
    StreamingResponse generator finishes. The generator manages its own
    DB session so the connection stays alive for the full stream lifecycle.
    """
    return StreamingResponse(
        _stream_response(session_id, body, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_response(
    session_id: UUID,
    body: ChatSendRequest,
    request: Request,
):
    """Async generator that yields SSE events for a chat response."""
    async with async_session() as db:
        try:
            # 0. Validate session
            result = await db.execute(
                select(ChatSession)
                .options(selectinload(ChatSession.messages))
                .where(ChatSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                yield _sse_event("error", {"detail": "Session not found"})
                return

            # 1. Save user message
            prior_message_count = len(session.messages)
            user_msg = ChatMessage(
                session_id=session.id,
                role="user",
                content=body.message,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user_msg)
            await db.flush()

            yield _sse_event("user_message", {
                "id": str(user_msg.id),
                "role": "user",
                "content": user_msg.content,
                "citations": None,
                "created_at": user_msg.created_at.isoformat(),
            })

            # 2. Build conversation history
            history_messages: list[dict[str, str]] = []
            for m in session.messages:
                if m.id == user_msg.id:
                    continue
                history_messages.append({"role": m.role, "content": m.content})

            # 3. Rewrite follow-up queries
            search_query = body.message
            if history_messages:
                search_query = await _rewrite_query(body.message, history_messages)
                logger.info("Query rewritten: %r → %r", body.message, search_query)

            # 4. RAG retrieval
            rag_result = await retrieve_and_format(
                question=search_query,
                madhab=body.madhab,
                category=body.category,
            )

            # 5. Build LLM messages
            if rag_result:
                current_user_content = (
                    f"## Source Texts\n{rag_result.sources_text}\n\n"
                    f"## User Question\n{body.message}\n\n"
                    f"{rag_result.query_context}"
                )
            else:
                current_user_content = body.message

            llm_messages = history_messages + [
                {"role": "user", "content": current_user_content},
            ]

            # 6. Start title generation concurrently (if first message)
            needs_title = prior_message_count == 0 and not session.title
            title_task = None
            if needs_title:
                title_task = asyncio.create_task(_generate_title(body.message))

            # 7. Stream LLM response
            full_answer = ""
            llm_failed = False
            try:
                async for token in stream_llm_chat(
                    system_prompt=ADAB_CHAT_SYSTEM_PROMPT,
                    messages=llm_messages,
                ):
                    full_answer += token
                    yield _sse_event("content_delta", {"token": token})
                    if await request.is_disconnected():
                        logger.info("Client disconnected during streaming")
                        if title_task:
                            title_task.cancel()
                        return
            except (LLMError, httpx.ReadTimeout, httpx.ReadError) as exc:
                logger.error("LLM streaming failed: %s", exc)
                llm_failed = True
                full_answer = (
                    "I'm sorry, the AI service is temporarily unavailable. "
                    "Please try again in a moment."
                )
                yield _sse_event("content_delta", {"token": full_answer})

            # 8. Build citations
            citations: list[Citation] = []
            if rag_result and not llm_failed:
                citations = build_numbered_citations(rag_result.hits, rag_result.intent)
                citations = await finalize_citations(full_answer, citations, numbered=True)

            if citations:
                yield _sse_event("citations", {
                    "citations": [c.model_dump() for c in citations],
                })

            # 9. Await title
            if title_task:
                try:
                    session.title = await title_task
                except Exception:
                    logger.warning("Title generation failed during stream")
                    session.title = body.message[:60] + ("..." if len(body.message) > 60 else "")
                yield _sse_event("title", {"title": session.title})

            # 10. Save assistant message and commit
            assistant_msg = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=full_answer,
                citations_json=[c.model_dump() for c in citations] if citations else None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)

            yield _sse_event("done", {
                "message_id": str(assistant_msg.id),
                "created_at": assistant_msg.created_at.isoformat(),
            })

        except Exception as exc:
            logger.exception("Streaming error")
            yield _sse_event("error", {"detail": str(exc)})
