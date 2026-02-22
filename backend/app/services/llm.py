import asyncio
import json as json_mod
import logging
from collections.abc import AsyncIterator

import httpx

from app.config import settings
from app.services.token_budget import estimate_tokens

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Shared persistent HTTP client — avoids TCP+TLS handshake per LLM call
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Lazily create and return a shared httpx.AsyncClient."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=60.0)
    return _http_client


async def close_http_client() -> None:
    """Close the shared HTTP client (call on app shutdown)."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


class LLMError(Exception):
    """Raised when the LLM service fails."""


async def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> str:
    """Call the LLM via OpenRouter and return the response text.

    Uses Qwen 2.5 (or configured model) through OpenRouter's API.
    """
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ilm-atlas.app",
        "X-Title": "Ilm Atlas",
    }

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    client = get_http_client()
    resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)

    if resp.status_code != 200:
        body = resp.text
        logger.error("OpenRouter returned %s: %s", resp.status_code, body)
        raise LLMError(f"LLM service returned {resp.status_code}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected LLM response shape: %s", data)
        raise LLMError("Unexpected response from LLM service") from exc


def _trim_history(
    messages: list[dict[str, str]],
    max_tokens: int = 40_000,
) -> list[dict[str, str]]:
    """Keep the most recent messages within a token budget.

    Always keeps the last message (current turn). Walks backward from
    the end, dropping older messages first when the budget is exceeded.
    """
    if not messages:
        return messages

    # Always keep the last message
    total = estimate_tokens(messages[-1].get("content", ""))
    keep_from = len(messages) - 1

    for i in range(len(messages) - 2, -1, -1):
        msg_tokens = estimate_tokens(messages[i].get("content", ""))
        if total + msg_tokens > max_tokens:
            break
        total += msg_tokens
        keep_from = i

    trimmed = messages[keep_from:]
    if len(trimmed) < len(messages):
        logger.info(
            "History trimmed: %d → %d messages (~%d tokens)",
            len(messages), len(trimmed), total,
        )
    return trimmed


async def call_llm_chat(
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> str:
    """Call the LLM with a multi-turn conversation history.

    Messages should be a list of {"role": "user"|"assistant", "content": ...}.
    The system prompt is prepended automatically.
    """
    messages = _trim_history(messages)

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ilm-atlas.app",
        "X-Title": "Ilm Atlas",
    }

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages,
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    client = get_http_client()
    resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)

    if resp.status_code != 200:
        body = resp.text
        logger.error("OpenRouter returned %s: %s", resp.status_code, body)
        raise LLMError(f"LLM service returned {resp.status_code}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected LLM response shape: %s", data)
        raise LLMError("Unexpected response from LLM service") from exc


async def stream_llm_chat(
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> AsyncIterator[str]:
    """Stream LLM tokens via OpenRouter (SSE).

    Yields individual token strings as they arrive.
    Raises LLMError on non-200 status before streaming begins.
    """
    messages = _trim_history(messages)

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ilm-atlas.app",
        "X-Title": "Ilm Atlas",
    }

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages,
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    client = get_http_client()
    async with client.stream(
        "POST", OPENROUTER_URL, json=payload, headers=headers
    ) as resp:
        if resp.status_code != 200:
            body = await resp.aread()
            logger.error("OpenRouter returned %s: %s", resp.status_code, body)
            raise LLMError(f"LLM service returned {resp.status_code}")

        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json_mod.loads(data_str)
                token = chunk["choices"][0]["delta"].get("content")
                if token:
                    yield token
            except (json_mod.JSONDecodeError, KeyError, IndexError):
                continue


async def stream_llm_chunked_synthesis(
    system_prompt: str,
    source_chunks: list[str],
    question: str,
    query_context: str,
    history: list[dict[str, str]],
    temperature: float = 0.3,
) -> AsyncIterator[str]:
    """Tier 3: parallel chunk analysis followed by streamed synthesis.

    1. Makes parallel non-streaming LLM calls, one per source chunk.
    2. Collects the partial answers.
    3. Streams a final synthesis call that merges them.

    Yields tokens from the synthesis call only.
    """
    # Phase 1: parallel chunk analysis
    async def _analyze_chunk(chunk_text: str, chunk_num: int) -> str:
        user_content = (
            f"## Source Texts (Part {chunk_num}/{len(source_chunks)})\n"
            f"{chunk_text}\n\n"
            f"## User Question\n{question}\n\n"
            f"{query_context}\n\n"
            "Provide a thorough partial answer based ONLY on the sources above. "
            "CRITICAL: Every claim MUST be cited by its source number in square "
            "brackets, like [1], [42], [103]. The numbers correspond to the "
            "[Source N] blocks above. NEVER cite by source title or book name — "
            "ONLY use bracketed numbers. "
            "This is part of a multi-part analysis — cover what these sources contain."
        )
        messages = history + [{"role": "user", "content": user_content}]
        return await call_llm_chat(
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=4_000,
            temperature=temperature,
        )

    logger.info("Tier 3 chunked synthesis: %d chunks", len(source_chunks))
    partial_answers = await asyncio.gather(
        *[_analyze_chunk(chunk, i + 1) for i, chunk in enumerate(source_chunks)]
    )

    # Phase 2: synthesis call (streamed)
    parts_text = "\n\n---\n\n".join(
        f"## Partial Answer {i + 1}\n{answer}"
        for i, answer in enumerate(partial_answers)
    )
    synthesis_content = (
        f"The user asked: {question}\n\n"
        f"The following partial answers were generated from different sets of sources. "
        f"Synthesize them into a single, coherent, well-structured response. "
        f"Preserve all bracketed citation numbers exactly as they appear "
        f"(e.g. [1], [42], [103]). Do NOT replace them with source titles "
        f"or book names, and do NOT add the word 'Source' before the number. "
        f"Remove redundancy and organize by theme.\n\n"
        f"{parts_text}"
    )
    synthesis_messages = history + [{"role": "user", "content": synthesis_content}]

    async for token in stream_llm_chat(
        system_prompt=system_prompt,
        messages=synthesis_messages,
        max_tokens=8_000,
        temperature=temperature,
    ):
        yield token
