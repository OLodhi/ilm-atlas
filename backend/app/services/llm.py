import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


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

    async with httpx.AsyncClient(timeout=60.0) as client:
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
    max_chars: int = 80_000,
) -> list[dict[str, str]]:
    """Keep the most recent messages within a character budget.

    Always keeps the last message (current turn). Walks backward from
    the end, dropping older messages first when the budget is exceeded.
    """
    if not messages:
        return messages

    # Always keep the last message
    total = len(messages[-1].get("content", ""))
    keep_from = len(messages) - 1

    for i in range(len(messages) - 2, -1, -1):
        msg_len = len(messages[i].get("content", ""))
        if total + msg_len > max_chars:
            break
        total += msg_len
        keep_from = i

    trimmed = messages[keep_from:]
    if len(trimmed) < len(messages):
        logger.info(
            "History trimmed: %d → %d messages (~%d chars)",
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

    async with httpx.AsyncClient(timeout=60.0) as client:
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
