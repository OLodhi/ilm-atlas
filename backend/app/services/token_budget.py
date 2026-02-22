"""Token estimation utilities for auto-scaling LLM context.

Uses a character-based heuristic calibrated on actual data:
~1,076,793 chars ≈ 657,787 tokens → ~1.64 chars/token.
We use 1.5 chars/token — slightly below the measured ratio so we
*overestimate* token count (safer: prevents context overflow).
"""

MODEL_CONTEXT_WINDOW = 262_144
MODEL_MAX_OUTPUT = 32_768
SAFETY_MARGIN = 5_000

# Lower ratio → more estimated tokens → smaller chunks → safer
_CHARS_PER_TOKEN = 1.5


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using character heuristic."""
    return int(len(text) / _CHARS_PER_TOKEN)


def available_source_tokens(
    system_prompt: str,
    history: list[dict[str, str]],
    question: str,
    context: str = "",
) -> int:
    """Return the token budget available for source text.

    Accounts for system prompt, conversation history, user question,
    query context wrapper, max output tokens, and a safety margin.
    """
    used = estimate_tokens(system_prompt)
    for msg in history:
        used += estimate_tokens(msg.get("content", ""))
    # The user message wraps sources + question + context
    used += estimate_tokens(question)
    used += estimate_tokens(context)
    # Overhead for "## Source Texts\n", "## User Question\n", etc.
    used += 50

    budget = MODEL_CONTEXT_WINDOW - MODEL_MAX_OUTPUT - SAFETY_MARGIN - used
    return max(budget, 1_000)
