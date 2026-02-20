import json
import logging
import re

from app.models.schemas import Citation
from app.prompts.translation import TRANSLATION_SYSTEM_PROMPT
from app.services.llm import call_llm, LLMError

logger = logging.getLogger(__name__)

MAX_BATCH = 10
MAX_CHARS_PER_TEXT = 1500


async def translate_arabic_citations(citations: list[Citation]) -> list[Citation]:
    """Auto-translate Arabic-only citations via a single LLM call.

    Scans for citations that have ``text_arabic`` but no ``text_english``,
    batches them (up to MAX_BATCH), sends one translation request to the LLM,
    and populates ``text_english`` + sets ``auto_translated=True``.

    On any failure the citations are returned unchanged (graceful degradation).
    """
    # Collect indices of Arabic-only citations
    arabic_indices: list[int] = []
    for i, cit in enumerate(citations):
        if cit.text_arabic and not cit.text_english:
            arabic_indices.append(i)

    if not arabic_indices:
        return citations

    # Cap to MAX_BATCH
    batch_indices = arabic_indices[:MAX_BATCH]

    # Build numbered input for the LLM
    numbered_lines: list[str] = []
    for seq, idx in enumerate(batch_indices, start=1):
        text = citations[idx].text_arabic or ""
        if len(text) > MAX_CHARS_PER_TEXT:
            text = text[:MAX_CHARS_PER_TEXT] + "..."
        numbered_lines.append(f"{seq}. {text}")

    user_message = "\n\n".join(numbered_lines)

    try:
        raw = await call_llm(
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.2,
            max_tokens=800,
        )
        translations = _parse_json_array(raw, expected=len(batch_indices))
    except (LLMError, ValueError) as exc:
        logger.warning("Translation failed, returning citations untranslated: %s", exc)
        return citations

    # Apply translations
    translated_count = 0
    for idx, translation in zip(batch_indices, translations):
        if translation:
            citations[idx].text_english = translation
            citations[idx].auto_translated = True
            translated_count += 1

    logger.info("Auto-translated %d Arabic-only citations", translated_count)
    return citations


def _parse_json_array(raw: str, expected: int) -> list[str]:
    """Parse the LLM response as a JSON array of strings.

    Handles common LLM quirks: markdown code fences, trailing commas, etc.
    Raises ValueError if the result cannot be parsed or has wrong length.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()

    # Try direct parse
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try fixing trailing comma before closing bracket
        fixed = re.sub(r",\s*]", "]", text)
        try:
            parsed = json.loads(fixed)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not parse LLM translation response as JSON: {text[:200]}") from exc

    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")

    if len(parsed) != expected:
        logger.warning(
            "Translation array length mismatch: got %d, expected %d",
            len(parsed), expected,
        )
        # Pad or truncate to match expected length
        if len(parsed) < expected:
            parsed.extend([""] * (expected - len(parsed)))
        else:
            parsed = parsed[:expected]

    return [str(item) if item else "" for item in parsed]
