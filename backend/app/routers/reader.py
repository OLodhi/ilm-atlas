"""Read-only browse endpoints for Quran, Hadith, and Tafsir content.

All endpoints are public (no auth required) and rate-limited to 60 req/min.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.middleware.rate_limit import limiter
from app.models.reader_schemas import (
    CollectionSummary,
    HadithBookDetailResponse,
    HadithBookSummary,
    LibraryStats,
    SurahDetailResponse,
    SurahSummary,
    TafsirForAyah,
    TafsirSurahDetailResponse,
    TafsirSummary,
)
from app.services import reader as reader_service
from app.services.translation import translate_texts
from app.services.llm import LLMError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/read", tags=["reader"])


# ---------------------------------------------------------------------------
# Library Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=LibraryStats)
@limiter.limit("60/minute")
async def get_library_stats(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Return aggregate counts across all library content."""
    return await reader_service.get_library_stats(session)


# ---------------------------------------------------------------------------
# Quran
# ---------------------------------------------------------------------------


@router.get("/quran/surahs", response_model=list[SurahSummary])
@limiter.limit("60/minute")
async def get_quran_surahs(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Return a summary list of all 114 surahs."""
    return await reader_service.get_quran_surahs(session)


@router.get("/quran/surahs/{surah_number}", response_model=SurahDetailResponse)
@limiter.limit("60/minute")
async def get_surah_detail(
    request: Request,
    surah_number: int,
    session: AsyncSession = Depends(get_session),
):
    """Return all ayahs for a given surah."""
    if surah_number < 1 or surah_number > 114:
        raise HTTPException(status_code=400, detail="surah_number must be between 1 and 114.")

    result = await reader_service.get_surah_detail(session, surah_number)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Surah {surah_number} not found.")
    return result


@router.get(
    "/quran/surahs/{surah_number}/ayahs/{ayah_number}/tafsir",
    response_model=list[TafsirForAyah],
)
@limiter.limit("60/minute")
async def get_tafsir_for_ayah(
    request: Request,
    surah_number: int,
    ayah_number: int,
    session: AsyncSession = Depends(get_session),
):
    """Return all tafsir entries for a specific ayah across all tafsir books."""
    return await reader_service.get_tafsir_for_ayah(session, surah_number, ayah_number)


# ---------------------------------------------------------------------------
# Hadith
# ---------------------------------------------------------------------------


@router.get("/hadith/collections", response_model=list[CollectionSummary])
@limiter.limit("60/minute")
async def get_hadith_collections(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Return a summary list of all hadith collections."""
    return await reader_service.get_hadith_collections(session)


@router.get(
    "/hadith/collections/{slug}/books",
    response_model=list[HadithBookSummary],
)
@limiter.limit("60/minute")
async def get_hadith_books(
    request: Request,
    slug: str,
    session: AsyncSession = Depends(get_session),
):
    """Return books/chapters within a hadith collection."""
    result = await reader_service.get_hadith_books(session, slug)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Hadith collection '{slug}' not found.")
    _collection_name, books = result
    return books


@router.get(
    "/hadith/collections/{slug}/books/{book_number}",
    response_model=HadithBookDetailResponse,
)
@limiter.limit("60/minute")
async def get_hadith_book_detail(
    request: Request,
    slug: str,
    book_number: int,
    session: AsyncSession = Depends(get_session),
):
    """Return hadiths in a specific book/chapter within a hadith collection."""
    result = await reader_service.get_hadith_book_detail(session, slug, book_number)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Book {book_number} not found in collection '{slug}'.",
        )
    return result


# ---------------------------------------------------------------------------
# Tafsir
# ---------------------------------------------------------------------------


@router.get("/tafsir", response_model=list[TafsirSummary])
@limiter.limit("60/minute")
async def get_tafsir_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Return a summary list of all available tafsir books."""
    return await reader_service.get_tafsir_list(session)


@router.get(
    "/tafsir/{slug}/surahs/{surah_number}",
    response_model=TafsirSurahDetailResponse,
)
@limiter.limit("60/minute")
async def get_tafsir_surah_detail(
    request: Request,
    slug: str,
    surah_number: int,
    session: AsyncSession = Depends(get_session),
):
    """Return tafsir entries for a specific surah within a tafsir book."""
    result = await reader_service.get_tafsir_surah_detail(session, slug, surah_number)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Tafsir '{slug}' surah {surah_number} not found.",
        )
    return result


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------


class TranslateRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=10)


class TranslateResponse(BaseModel):
    translations: list[str]


@router.post("/translate", response_model=TranslateResponse)
@limiter.limit("10/minute")
async def translate(request: Request, body: TranslateRequest):
    """Translate a batch of Arabic texts to English via LLM."""
    try:
        translations = await translate_texts(body.texts)
    except (LLMError, ValueError) as exc:
        logger.warning("Reader translation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Translation service unavailable.")
    return TranslateResponse(translations=translations)
