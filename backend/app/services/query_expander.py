import logging

from app.prompts.query_expansion import QUERY_EXPANSION_PROMPT
from app.services.llm import LLMError, call_llm

logger = logging.getLogger(__name__)


async def expand_query(question: str) -> list[str]:
    """Use LLM to generate alternative search phrases for better retrieval."""
    try:
        response = await call_llm(
            system_prompt=QUERY_EXPANSION_PROMPT,
            user_message=question,
            max_tokens=200,
            temperature=0.5,
        )
    except LLMError:
        logger.warning("Query expansion failed — proceeding with original query only")
        return []

    phrases = [line.strip() for line in response.splitlines() if line.strip()]
    # Cap at 8 phrases to allow broader sub-topic coverage
    phrases = phrases[:8]
    logger.info("Query expanded: %s", phrases)
    return phrases
