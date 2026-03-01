# Reader Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a library-style reader allowing users to browse and read Quran, Hadith, and Tafsir source material in full, with stacked Arabic/English text, expandable tafsir, and typography controls.

**Architecture:** New read-only FastAPI router queries PostgreSQL chunks via `metadata_json` JSONB. Next.js App Router pages under `/read` with a sidebar+reading-pane layout. All public (no auth). Tafsir loads on demand per ayah.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL JSONB, Next.js 14 App Router, Tailwind CSS, Shadcn/UI.

---

## Context: Data Shape in PostgreSQL

All content lives in the `chunks` table, joined through `sources` → `books`.

**Quran chunks** (`chunk_type='ayah'`, `book.category='quran'`):
```json
{
  "metadata_json": {
    "surah_number": 2,
    "surah_name_arabic": "البقرة",
    "surah_name_english": "Al-Baqarah",
    "ayah_number": 255,
    "juz": 3,
    "ruku": 35,
    "revelation_type": "Medinan"
  },
  "section": "Surah Al-Baqarah"
}
```

**Hadith chunks** (`chunk_type='hadith'`, `book.category='hadith'`):
```json
{
  "metadata_json": {
    "hadith_number": "1",
    "book_slug": "sahih-bukhari",
    "chapter_number": "1",
    "chapter_english": "Revelation",
    "chapter_arabic": "بدء الوحي",
    "volume": "1",
    "status": "authentic",
    "narrator_english": "Narrated 'Umar bin Al-Khattab"
  },
  "section": "Chapter: Revelation"
}
```

**Tafsir chunks** (`chunk_type='tafsir'`, `book.category='tafsir'`):
```json
{
  "metadata_json": {
    "surah_number": 2,
    "surah_name_english": "Al-Baqarah",
    "ayah_number": 255,
    "tafsir_name": "Tafsir Ibn Kathir",
    "tafsir_author": "Hafiz Ibn Kathir"
  },
  "section": "Tafsir of Surah Al-Baqarah (2:255)"
}
```

Books for hadith collections have titles like "Sahih Bukhari" with `category='hadith'`.
Books for tafsirs have titles like "Tafsir Ibn Kathir" with `category='tafsir'`.
Each tafsir book is language-specific (`language='arabic'` or `language='english'`).

---

## Task 1: Backend — Reader Pydantic Schemas

**Files:**
- Create: `backend/app/models/reader_schemas.py`

**Step 1: Create the schema file**

```python
# backend/app/models/reader_schemas.py
from pydantic import BaseModel


# ── Quran ──

class SurahSummary(BaseModel):
    number: int
    name_arabic: str
    name_english: str
    ayah_count: int
    revelation_type: str


class AyahResponse(BaseModel):
    number: int
    text_arabic: str | None
    text_english: str | None
    juz: int | None
    ruku: int | None


class SurahDetailResponse(BaseModel):
    surah: SurahSummary
    ayahs: list[AyahResponse]


# ── Hadith ──

class CollectionSummary(BaseModel):
    slug: str
    name: str
    author: str
    hadith_count: int
    book_count: int


class HadithBookSummary(BaseModel):
    number: int
    name_arabic: str | None
    name_english: str | None
    hadith_count: int


class HadithResponse(BaseModel):
    number: int
    text_arabic: str | None
    text_english: str | None
    chapter: str | None


class HadithBookDetailResponse(BaseModel):
    book: HadithBookSummary
    collection_name: str
    collection_slug: str
    hadiths: list[HadithResponse]


# ── Tafsir ──

class TafsirSummary(BaseModel):
    slug: str
    name: str
    author: str
    language: str
    surah_count: int


class TafsirEntryResponse(BaseModel):
    ayah_number: int
    text_arabic: str | None
    text_english: str | None


class TafsirSurahDetailResponse(BaseModel):
    tafsir: TafsirSummary
    surah_number: int
    surah_name: str
    entries: list[TafsirEntryResponse]


class TafsirForAyah(BaseModel):
    tafsir_name: str
    tafsir_slug: str
    language: str
    text: str | None


# ── Library stats ──

class LibraryStats(BaseModel):
    quran_surah_count: int
    quran_ayah_count: int
    hadith_collection_count: int
    hadith_count: int
    tafsir_count: int
    tafsir_entry_count: int
```

**Step 2: Verify import works**

Run: `cd backend && python -c "from app.models.reader_schemas import SurahSummary; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/models/reader_schemas.py
git commit -m "feat(reader): add Pydantic schemas for reader API"
```

---

## Task 2: Backend — Reader Service Layer

**Files:**
- Create: `backend/app/services/reader.py`

This service contains all PostgreSQL queries for browsing content. It uses SQLAlchemy with `metadata_json` JSONB access.

**Step 1: Create the service file**

```python
# backend/app/services/reader.py
import re
from sqlalchemy import select, func, cast, Integer, distinct, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Book, Source, Chunk
from app.models.reader_schemas import (
    SurahSummary,
    AyahResponse,
    SurahDetailResponse,
    CollectionSummary,
    HadithBookSummary,
    HadithResponse,
    HadithBookDetailResponse,
    TafsirSummary,
    TafsirEntryResponse,
    TafsirSurahDetailResponse,
    TafsirForAyah,
    LibraryStats,
)


def slugify(name: str) -> str:
    """Generate a URL slug from a book title."""
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s.strip())
    return s


# ── helpers for JSONB access ──

def _json_text(column, key: str):
    """Extract a text value from a JSONB column: column->>'key'."""
    return column[key].astext


def _json_int(column, key: str):
    """Extract an integer from a JSONB column: (column->>'key')::int."""
    return cast(column[key].astext, Integer)


# ── Quran ──

async def get_quran_surahs(session: AsyncSession) -> list[SurahSummary]:
    query = (
        select(
            _json_int(Chunk.metadata_json, "surah_number").label("number"),
            _json_text(Chunk.metadata_json, "surah_name_arabic").label("name_arabic"),
            _json_text(Chunk.metadata_json, "surah_name_english").label("name_english"),
            func.count().label("ayah_count"),
            _json_text(Chunk.metadata_json, "revelation_type").label("revelation_type"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(Book.category == "quran")
        .group_by(
            _json_text(Chunk.metadata_json, "surah_number"),
            _json_text(Chunk.metadata_json, "surah_name_arabic"),
            _json_text(Chunk.metadata_json, "surah_name_english"),
            _json_text(Chunk.metadata_json, "revelation_type"),
        )
        .order_by(_json_int(Chunk.metadata_json, "surah_number"))
    )
    rows = (await session.execute(query)).all()
    return [
        SurahSummary(
            number=r.number,
            name_arabic=r.name_arabic,
            name_english=r.name_english,
            ayah_count=r.ayah_count,
            revelation_type=r.revelation_type,
        )
        for r in rows
    ]


async def get_surah_detail(session: AsyncSession, surah_number: int) -> SurahDetailResponse | None:
    # Get ayahs
    query = (
        select(
            _json_int(Chunk.metadata_json, "ayah_number").label("number"),
            Chunk.content_arabic.label("text_arabic"),
            Chunk.content_english.label("text_english"),
            _json_int(Chunk.metadata_json, "juz").label("juz"),
            _json_int(Chunk.metadata_json, "ruku").label("ruku"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Book.category == "quran",
                _json_int(Chunk.metadata_json, "surah_number") == surah_number,
            )
        )
        .order_by(_json_int(Chunk.metadata_json, "ayah_number"))
    )
    rows = (await session.execute(query)).all()
    if not rows:
        return None

    ayahs = [
        AyahResponse(
            number=r.number,
            text_arabic=r.text_arabic,
            text_english=r.text_english,
            juz=r.juz,
            ruku=r.ruku,
        )
        for r in rows
    ]

    # Derive surah metadata from first ayah row + count
    first = rows[0]
    # Get surah name from metadata
    name_query = (
        select(
            _json_text(Chunk.metadata_json, "surah_name_arabic").label("name_arabic"),
            _json_text(Chunk.metadata_json, "surah_name_english").label("name_english"),
            _json_text(Chunk.metadata_json, "revelation_type").label("revelation_type"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Book.category == "quran",
                _json_int(Chunk.metadata_json, "surah_number") == surah_number,
            )
        )
        .limit(1)
    )
    meta = (await session.execute(name_query)).first()

    surah = SurahSummary(
        number=surah_number,
        name_arabic=meta.name_arabic if meta else "",
        name_english=meta.name_english if meta else "",
        ayah_count=len(ayahs),
        revelation_type=meta.revelation_type if meta else "",
    )

    return SurahDetailResponse(surah=surah, ayahs=ayahs)


async def get_tafsir_for_ayah(
    session: AsyncSession, surah_number: int, ayah_number: int
) -> list[TafsirForAyah]:
    query = (
        select(
            Book.title.label("tafsir_name"),
            Book.language.label("language"),
            Chunk.content_arabic,
            Chunk.content_english,
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Book.category == "tafsir",
                _json_int(Chunk.metadata_json, "surah_number") == surah_number,
                _json_int(Chunk.metadata_json, "ayah_number") == ayah_number,
            )
        )
        .order_by(Book.title)
    )
    rows = (await session.execute(query)).all()
    return [
        TafsirForAyah(
            tafsir_name=r.tafsir_name,
            tafsir_slug=slugify(r.tafsir_name),
            language=r.language,
            text=r.content_arabic if r.language == "arabic" else r.content_english,
        )
        for r in rows
    ]


# ── Hadith ──

async def get_hadith_collections(session: AsyncSession) -> list[CollectionSummary]:
    query = (
        select(
            func.min(_json_text(Chunk.metadata_json, "book_slug")).label("slug"),
            Book.title.label("name"),
            Book.author,
            func.count(Chunk.id).label("hadith_count"),
            func.count(
                distinct(_json_text(Chunk.metadata_json, "chapter_number"))
            ).label("book_count"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(Book.category == "hadith")
        .group_by(Book.id, Book.title, Book.author)
        .order_by(Book.title)
    )
    rows = (await session.execute(query)).all()
    return [
        CollectionSummary(
            slug=r.slug,
            name=r.name,
            author=r.author,
            hadith_count=r.hadith_count,
            book_count=r.book_count,
        )
        for r in rows
    ]


async def get_hadith_books(
    session: AsyncSession, collection_slug: str
) -> tuple[str, list[HadithBookSummary]] | None:
    """Returns (collection_name, books) or None if collection not found."""
    # First, find the book (collection) by joining chunks that have this slug
    name_query = (
        select(Book.title)
        .join(Source, Book.id == Source.book_id)
        .join(Chunk, Source.id == Chunk.source_id)
        .where(
            and_(
                Book.category == "hadith",
                _json_text(Chunk.metadata_json, "book_slug") == collection_slug,
            )
        )
        .limit(1)
    )
    name_row = (await session.execute(name_query)).scalar_one_or_none()
    if name_row is None:
        return None

    # Get distinct chapters (books)
    query = (
        select(
            _json_int(Chunk.metadata_json, "chapter_number").label("number"),
            _json_text(Chunk.metadata_json, "chapter_arabic").label("name_arabic"),
            _json_text(Chunk.metadata_json, "chapter_english").label("name_english"),
            func.count(Chunk.id).label("hadith_count"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Book.category == "hadith",
                _json_text(Chunk.metadata_json, "book_slug") == collection_slug,
            )
        )
        .group_by(
            _json_text(Chunk.metadata_json, "chapter_number"),
            _json_text(Chunk.metadata_json, "chapter_arabic"),
            _json_text(Chunk.metadata_json, "chapter_english"),
        )
        .order_by(_json_int(Chunk.metadata_json, "chapter_number"))
    )
    rows = (await session.execute(query)).all()
    books = [
        HadithBookSummary(
            number=r.number,
            name_arabic=r.name_arabic,
            name_english=r.name_english,
            hadith_count=r.hadith_count,
        )
        for r in rows
    ]
    return (name_row, books)


async def get_hadith_book_detail(
    session: AsyncSession, collection_slug: str, book_number: int
) -> HadithBookDetailResponse | None:
    # Verify collection exists and get name
    name_query = (
        select(Book.title)
        .join(Source, Book.id == Source.book_id)
        .join(Chunk, Source.id == Chunk.source_id)
        .where(
            and_(
                Book.category == "hadith",
                _json_text(Chunk.metadata_json, "book_slug") == collection_slug,
            )
        )
        .limit(1)
    )
    collection_name = (await session.execute(name_query)).scalar_one_or_none()
    if collection_name is None:
        return None

    # Get hadiths in this book (chapter)
    query = (
        select(
            _json_int(Chunk.metadata_json, "hadith_number").label("number"),
            Chunk.content_arabic.label("text_arabic"),
            Chunk.content_english.label("text_english"),
            _json_text(Chunk.metadata_json, "chapter_english").label("chapter"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Book.category == "hadith",
                _json_text(Chunk.metadata_json, "book_slug") == collection_slug,
                _json_int(Chunk.metadata_json, "chapter_number") == book_number,
            )
        )
        .order_by(_json_int(Chunk.metadata_json, "hadith_number"))
    )
    rows = (await session.execute(query)).all()
    if not rows:
        return None

    hadiths = [
        HadithResponse(
            number=r.number,
            text_arabic=r.text_arabic,
            text_english=r.text_english,
            chapter=r.chapter,
        )
        for r in rows
    ]

    # Get book summary
    book_meta_query = (
        select(
            _json_text(Chunk.metadata_json, "chapter_arabic").label("name_arabic"),
            _json_text(Chunk.metadata_json, "chapter_english").label("name_english"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Book.category == "hadith",
                _json_text(Chunk.metadata_json, "book_slug") == collection_slug,
                _json_int(Chunk.metadata_json, "chapter_number") == book_number,
            )
        )
        .limit(1)
    )
    meta = (await session.execute(book_meta_query)).first()

    book = HadithBookSummary(
        number=book_number,
        name_arabic=meta.name_arabic if meta else None,
        name_english=meta.name_english if meta else None,
        hadith_count=len(hadiths),
    )

    return HadithBookDetailResponse(
        book=book,
        collection_name=collection_name,
        collection_slug=collection_slug,
        hadiths=hadiths,
    )


# ── Tafsir ──

async def get_tafsir_list(session: AsyncSession) -> list[TafsirSummary]:
    query = (
        select(
            Book.title.label("name"),
            Book.author,
            Book.language,
            func.count(distinct(_json_text(Chunk.metadata_json, "surah_number"))).label(
                "surah_count"
            ),
        )
        .join(Source, Book.id == Source.book_id)
        .join(Chunk, Source.id == Chunk.source_id)
        .where(Book.category == "tafsir")
        .group_by(Book.id, Book.title, Book.author, Book.language)
        .order_by(Book.title)
    )
    rows = (await session.execute(query)).all()
    return [
        TafsirSummary(
            slug=slugify(r.name),
            name=r.name,
            author=r.author,
            language=r.language,
            surah_count=r.surah_count,
        )
        for r in rows
    ]


async def get_tafsir_surah_detail(
    session: AsyncSession, tafsir_slug: str, surah_number: int
) -> TafsirSurahDetailResponse | None:
    # Find the tafsir book whose slugified title matches
    books_query = (
        select(Book.id, Book.title, Book.author, Book.language)
        .where(Book.category == "tafsir")
    )
    books = (await session.execute(books_query)).all()
    matched_book = None
    for b in books:
        if slugify(b.title) == tafsir_slug:
            matched_book = b
            break
    if matched_book is None:
        return None

    # Get entries for this surah
    query = (
        select(
            _json_int(Chunk.metadata_json, "ayah_number").label("ayah_number"),
            Chunk.content_arabic.label("text_arabic"),
            Chunk.content_english.label("text_english"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .where(
            and_(
                Source.book_id == matched_book.id,
                _json_int(Chunk.metadata_json, "surah_number") == surah_number,
            )
        )
        .order_by(_json_int(Chunk.metadata_json, "ayah_number"))
    )
    rows = (await session.execute(query)).all()
    if not rows:
        return None

    # Get surah name from first entry
    surah_name_query = (
        select(_json_text(Chunk.metadata_json, "surah_name_english"))
        .join(Source, Chunk.source_id == Source.id)
        .where(
            and_(
                Source.book_id == matched_book.id,
                _json_int(Chunk.metadata_json, "surah_number") == surah_number,
            )
        )
        .limit(1)
    )
    surah_name = (await session.execute(surah_name_query)).scalar_one_or_none() or ""

    # Count total surahs for this tafsir
    surah_count_query = (
        select(func.count(distinct(_json_text(Chunk.metadata_json, "surah_number"))))
        .join(Source, Chunk.source_id == Source.id)
        .where(Source.book_id == matched_book.id)
    )
    surah_count = (await session.execute(surah_count_query)).scalar_one()

    return TafsirSurahDetailResponse(
        tafsir=TafsirSummary(
            slug=tafsir_slug,
            name=matched_book.title,
            author=matched_book.author,
            language=matched_book.language,
            surah_count=surah_count,
        ),
        surah_number=surah_number,
        surah_name=surah_name,
        entries=[
            TafsirEntryResponse(
                ayah_number=r.ayah_number,
                text_arabic=r.text_arabic,
                text_english=r.text_english,
            )
            for r in rows
        ],
    )


# ── Library stats ──

async def get_library_stats(session: AsyncSession) -> LibraryStats:
    # Quran
    quran_q = (
        select(
            func.count(distinct(_json_text(Chunk.metadata_json, "surah_number"))).label("surahs"),
            func.count(Chunk.id).label("ayahs"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(Book.category == "quran")
    )
    quran = (await session.execute(quran_q)).first()

    # Hadith
    hadith_q = (
        select(
            func.count(distinct(Book.id)).label("collections"),
            func.count(Chunk.id).label("hadiths"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(Book.category == "hadith")
    )
    hadith = (await session.execute(hadith_q)).first()

    # Tafsir
    tafsir_q = (
        select(
            func.count(distinct(Book.id)).label("tafsirs"),
            func.count(Chunk.id).label("entries"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(Book.category == "tafsir")
    )
    tafsir = (await session.execute(tafsir_q)).first()

    return LibraryStats(
        quran_surah_count=quran.surahs if quran else 0,
        quran_ayah_count=quran.ayahs if quran else 0,
        hadith_collection_count=hadith.collections if hadith else 0,
        hadith_count=hadith.hadiths if hadith else 0,
        tafsir_count=tafsir.tafsirs if tafsir else 0,
        tafsir_entry_count=tafsir.entries if tafsir else 0,
    )
```

**Step 2: Verify import**

Run: `cd backend && python -c "from app.services.reader import get_quran_surahs; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/services/reader.py
git commit -m "feat(reader): add service layer with PostgreSQL browse queries"
```

---

## Task 3: Backend — Reader Router

**Files:**
- Create: `backend/app/routers/reader.py`
- Modify: `backend/app/main.py:17,51-54` — add import and register router

**Step 1: Create the router**

```python
# backend/app/routers/reader.py
from fastapi import APIRouter, Depends, HTTPException, Request
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

router = APIRouter(prefix="/read", tags=["reader"])


@router.get("/stats", response_model=LibraryStats)
@limiter.limit("60/minute")
async def get_library_stats(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await reader_service.get_library_stats(session)


# ── Quran ──


@router.get("/quran/surahs", response_model=list[SurahSummary])
@limiter.limit("60/minute")
async def list_surahs(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await reader_service.get_quran_surahs(session)


@router.get("/quran/surahs/{surah_number}", response_model=SurahDetailResponse)
@limiter.limit("60/minute")
async def get_surah(
    surah_number: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    if surah_number < 1 or surah_number > 114:
        raise HTTPException(status_code=400, detail="Surah number must be 1-114")
    result = await reader_service.get_surah_detail(session, surah_number)
    if result is None:
        raise HTTPException(status_code=404, detail="Surah not found")
    return result


@router.get(
    "/quran/surahs/{surah_number}/ayahs/{ayah_number}/tafsir",
    response_model=list[TafsirForAyah],
)
@limiter.limit("60/minute")
async def get_ayah_tafsir(
    surah_number: int,
    ayah_number: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await reader_service.get_tafsir_for_ayah(session, surah_number, ayah_number)


# ── Hadith ──


@router.get("/hadith/collections", response_model=list[CollectionSummary])
@limiter.limit("60/minute")
async def list_hadith_collections(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await reader_service.get_hadith_collections(session)


@router.get(
    "/hadith/collections/{slug}/books",
    response_model=list[HadithBookSummary],
)
@limiter.limit("60/minute")
async def list_hadith_books(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    result = await reader_service.get_hadith_books(session, slug)
    if result is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    _name, books = result
    return books


@router.get(
    "/hadith/collections/{slug}/books/{book_number}",
    response_model=HadithBookDetailResponse,
)
@limiter.limit("60/minute")
async def get_hadith_book(
    slug: str,
    book_number: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    result = await reader_service.get_hadith_book_detail(session, slug, book_number)
    if result is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return result


# ── Tafsir ──


@router.get("/tafsir", response_model=list[TafsirSummary])
@limiter.limit("60/minute")
async def list_tafsirs(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await reader_service.get_tafsir_list(session)


@router.get(
    "/tafsir/{slug}/surahs/{surah_number}",
    response_model=TafsirSurahDetailResponse,
)
@limiter.limit("60/minute")
async def get_tafsir_surah(
    slug: str,
    surah_number: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    result = await reader_service.get_tafsir_surah_detail(session, slug, surah_number)
    if result is None:
        raise HTTPException(status_code=404, detail="Tafsir or surah not found")
    return result
```

**Step 2: Register in main.py**

In `backend/app/main.py`:

Add to imports (line 17):
```python
from app.routers import admin, auth, chat, query, reader
```

Add after line 54:
```python
app.include_router(reader.router)
```

**Step 3: Verify server starts**

Run: `cd backend && python -c "from app.main import app; print([r.path for r in app.routes if '/read' in getattr(r, 'path', '')])"`
Expected: List of `/read/...` paths

**Step 4: Commit**

```bash
git add backend/app/routers/reader.py backend/app/main.py
git commit -m "feat(reader): add read-only browse API endpoints"
```

---

## Task 4: Backend — Tests for Reader Service

**Files:**
- Create: `backend/tests/test_reader.py`

**Step 1: Write tests**

```python
# backend/tests/test_reader.py
"""Tests for reader service — uses mock database rows."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.reader import slugify


def test_slugify_basic():
    assert slugify("Sahih Bukhari") == "sahih-bukhari"


def test_slugify_apostrophe():
    assert slugify("Jami' Al-Tirmidhi") == "jami-al-tirmidhi"


def test_slugify_parentheses():
    assert slugify("Tafsir Ibn Kathir (Abridged)") == "tafsir-ibn-kathir-abridged"


def test_slugify_quran_special_chars():
    assert slugify("Ma'arif al-Qur'an") == "maarif-al-quran"
```

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/test_reader.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add backend/tests/test_reader.py
git commit -m "test(reader): add unit tests for reader service slugify"
```

---

## Task 5: Frontend — TypeScript Types + API Client Functions

**Files:**
- Modify: `frontend/src/lib/types.ts` — add reader interfaces at the end
- Modify: `frontend/src/lib/api-client.ts` — add reader fetch functions at the end

**Step 1: Add types to `frontend/src/lib/types.ts`**

Append after the `StreamCallbacks` interface (end of file):

```typescript
// --- Reader ---

export interface SurahSummary {
  number: number;
  name_arabic: string;
  name_english: string;
  ayah_count: number;
  revelation_type: string;
}

export interface AyahResponse {
  number: number;
  text_arabic: string | null;
  text_english: string | null;
  juz: number | null;
  ruku: number | null;
}

export interface SurahDetailResponse {
  surah: SurahSummary;
  ayahs: AyahResponse[];
}

export interface CollectionSummary {
  slug: string;
  name: string;
  author: string;
  hadith_count: number;
  book_count: number;
}

export interface HadithBookSummary {
  number: number;
  name_arabic: string | null;
  name_english: string | null;
  hadith_count: number;
}

export interface HadithResponseType {
  number: number;
  text_arabic: string | null;
  text_english: string | null;
  chapter: string | null;
}

export interface HadithBookDetailResponse {
  book: HadithBookSummary;
  collection_name: string;
  collection_slug: string;
  hadiths: HadithResponseType[];
}

export interface TafsirSummary {
  slug: string;
  name: string;
  author: string;
  language: string;
  surah_count: number;
}

export interface TafsirEntryResponse {
  ayah_number: number;
  text_arabic: string | null;
  text_english: string | null;
}

export interface TafsirSurahDetailResponse {
  tafsir: TafsirSummary;
  surah_number: number;
  surah_name: string;
  entries: TafsirEntryResponse[];
}

export interface TafsirForAyah {
  tafsir_name: string;
  tafsir_slug: string;
  language: string;
  text: string | null;
}

export interface LibraryStats {
  quran_surah_count: number;
  quran_ayah_count: number;
  hadith_collection_count: number;
  hadith_count: number;
  tafsir_count: number;
  tafsir_entry_count: number;
}
```

**Step 2: Add API functions to `frontend/src/lib/api-client.ts`**

Add reader type imports at top (line 1-20 area), then append functions at end of file:

Add to the import block at the top:
```typescript
import type {
  // ...existing imports...
  SurahSummary,
  SurahDetailResponse,
  CollectionSummary,
  HadithBookSummary,
  HadithBookDetailResponse,
  TafsirSummary,
  TafsirSurahDetailResponse,
  TafsirForAyah,
  LibraryStats,
} from "./types";
```

Then append at end of file:

```typescript
// --- Reader (public, no auth) ---

export async function fetchLibraryStats(): Promise<LibraryStats> {
  return apiFetch<LibraryStats>("/read/stats");
}

export async function fetchSurahs(): Promise<SurahSummary[]> {
  return apiFetch<SurahSummary[]>("/read/quran/surahs");
}

export async function fetchSurahDetail(
  surahNumber: number
): Promise<SurahDetailResponse> {
  return apiFetch<SurahDetailResponse>(`/read/quran/surahs/${surahNumber}`);
}

export async function fetchAyahTafsir(
  surahNumber: number,
  ayahNumber: number
): Promise<TafsirForAyah[]> {
  return apiFetch<TafsirForAyah[]>(
    `/read/quran/surahs/${surahNumber}/ayahs/${ayahNumber}/tafsir`
  );
}

export async function fetchHadithCollections(): Promise<CollectionSummary[]> {
  return apiFetch<CollectionSummary[]>("/read/hadith/collections");
}

export async function fetchHadithBooks(
  collectionSlug: string
): Promise<HadithBookSummary[]> {
  return apiFetch<HadithBookSummary[]>(
    `/read/hadith/collections/${collectionSlug}/books`
  );
}

export async function fetchHadithBookDetail(
  collectionSlug: string,
  bookNumber: number
): Promise<HadithBookDetailResponse> {
  return apiFetch<HadithBookDetailResponse>(
    `/read/hadith/collections/${collectionSlug}/books/${bookNumber}`
  );
}

export async function fetchTafsirList(): Promise<TafsirSummary[]> {
  return apiFetch<TafsirSummary[]>("/read/tafsir");
}

export async function fetchTafsirSurahDetail(
  tafsirSlug: string,
  surahNumber: number
): Promise<TafsirSurahDetailResponse> {
  return apiFetch<TafsirSurahDetailResponse>(
    `/read/tafsir/${tafsirSlug}/surahs/${surahNumber}`
  );
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api-client.ts
git commit -m "feat(reader): add TypeScript types and API client functions for reader"
```

---

## Task 6: Frontend — Reader Layout Shell + Header Update

**Files:**
- Modify: `frontend/src/components/shared/header.tsx:33-57` — add "Read" nav link
- Create: `frontend/src/hooks/use-reader-settings.ts` — localStorage-persisted font/theme settings
- Create: `frontend/src/components/reader/reader-layout.tsx` — sidebar + reading pane shell
- Create: `frontend/src/components/reader/reader-sidebar.tsx` — contextual sidebar
- Create: `frontend/src/components/reader/breadcrumbs.tsx` — breadcrumb navigation
- Create: `frontend/src/components/reader/typography-controls.tsx` — font size + theme controls
- Create: `frontend/src/app/read/layout.tsx` — Next.js layout wrapping reader pages

**Step 1: Add "Read" link to header**

In `frontend/src/components/shared/header.tsx`, inside the `<nav>` element (after the Chat link, before the Admin link), add:

```tsx
<Link
  href="/read"
  className={cn(
    "transition-colors hover:text-foreground",
    pathname.startsWith("/read")
      ? "text-foreground"
      : "text-muted-foreground"
  )}
>
  Read
</Link>
```

**Step 2: Create reader settings hook**

```typescript
// frontend/src/hooks/use-reader-settings.ts
"use client";

import { useState, useCallback, useEffect } from "react";

interface ReaderSettings {
  arabicFontSize: number;    // rem
  englishFontSize: number;   // rem
  theme: "light" | "dark" | "sepia";
}

const DEFAULTS: ReaderSettings = {
  arabicFontSize: 1.5,
  englishFontSize: 1,
  theme: "light",
};

const STORAGE_KEY = "ilm-atlas-reader-settings";
const STEP = 0.125;
const MIN_SIZE = 0.75;
const MAX_SIZE = 3;

function load(): ReaderSettings {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return DEFAULTS;
  }
}

function save(settings: ReaderSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function useReaderSettings() {
  const [settings, setSettings] = useState<ReaderSettings>(DEFAULTS);

  useEffect(() => {
    setSettings(load());
  }, []);

  const update = useCallback((partial: Partial<ReaderSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...partial };
      save(next);
      return next;
    });
  }, []);

  const increaseArabic = useCallback(() => {
    update({ arabicFontSize: Math.min(settings.arabicFontSize + STEP, MAX_SIZE) });
  }, [settings.arabicFontSize, update]);

  const decreaseArabic = useCallback(() => {
    update({ arabicFontSize: Math.max(settings.arabicFontSize - STEP, MIN_SIZE) });
  }, [settings.arabicFontSize, update]);

  const increaseEnglish = useCallback(() => {
    update({ englishFontSize: Math.min(settings.englishFontSize + STEP, MAX_SIZE) });
  }, [settings.englishFontSize, update]);

  const decreaseEnglish = useCallback(() => {
    update({ englishFontSize: Math.max(settings.englishFontSize - STEP, MIN_SIZE) });
  }, [settings.englishFontSize, update]);

  return {
    settings,
    update,
    increaseArabic,
    decreaseArabic,
    increaseEnglish,
    decreaseEnglish,
  };
}
```

**Step 3: Create breadcrumbs component**

```tsx
// frontend/src/components/reader/breadcrumbs.tsx
import Link from "next/link";
import { ChevronRight } from "lucide-react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRight className="h-3.5 w-3.5" />}
          {item.href ? (
            <Link
              href={item.href}
              className="hover:text-foreground transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-foreground font-medium">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
```

**Step 4: Create typography controls**

```tsx
// frontend/src/components/reader/typography-controls.tsx
"use client";

import { Button } from "@/components/ui/button";
import { Minus, Plus } from "lucide-react";

interface TypographyControlsProps {
  arabicSize: number;
  englishSize: number;
  onIncreaseArabic: () => void;
  onDecreaseArabic: () => void;
  onIncreaseEnglish: () => void;
  onDecreaseEnglish: () => void;
}

export function TypographyControls({
  arabicSize,
  englishSize,
  onIncreaseArabic,
  onDecreaseArabic,
  onIncreaseEnglish,
  onDecreaseEnglish,
}: TypographyControlsProps) {
  return (
    <div className="flex items-center gap-4 text-sm text-muted-foreground">
      <div className="flex items-center gap-1">
        <span className="font-amiri text-base" dir="rtl">ع</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onDecreaseArabic}>
          <Minus className="h-3 w-3" />
        </Button>
        <span className="w-10 text-center text-xs">{arabicSize.toFixed(2)}</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onIncreaseArabic}>
          <Plus className="h-3 w-3" />
        </Button>
      </div>
      <div className="h-4 w-px bg-border" />
      <div className="flex items-center gap-1">
        <span className="text-xs font-medium">A</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onDecreaseEnglish}>
          <Minus className="h-3 w-3" />
        </Button>
        <span className="w-10 text-center text-xs">{englishSize.toFixed(2)}</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onIncreaseEnglish}>
          <Plus className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}
```

**Step 5: Create reader sidebar**

```tsx
// frontend/src/components/reader/reader-sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { BookOpen, BookText, MessageSquareText } from "lucide-react";

const SOURCE_TYPES = [
  { href: "/read/quran", label: "Quran", icon: BookOpen, color: "text-emerald-600" },
  { href: "/read/hadith", label: "Hadith", icon: BookText, color: "text-amber-600" },
  { href: "/read/tafsir", label: "Tafsir", icon: MessageSquareText, color: "text-violet-600" },
] as const;

interface ReaderSidebarProps {
  children?: React.ReactNode;
}

export function ReaderSidebar({ children }: ReaderSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b p-4">
        <h2 className="text-sm font-semibold">Library</h2>
      </div>

      <div className="shrink-0 border-b p-2">
        {SOURCE_TYPES.map(({ href, label, icon: Icon, color }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
              pathname.startsWith(href)
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <Icon className={cn("h-4 w-4", color)} />
            {label}
          </Link>
        ))}
      </div>

      {/* Source-specific sidebar content (surah list, collection list, etc.) */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}
```

**Step 6: Create reader layout component**

```tsx
// frontend/src/components/reader/reader-layout.tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { ReaderSidebar } from "./reader-sidebar";

interface ReaderLayoutProps {
  sidebarContent?: React.ReactNode;
  children: React.ReactNode;
}

export function ReaderLayout({ sidebarContent, children }: ReaderLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } fixed inset-y-[3.5rem] left-0 z-50 w-[280px] border-r bg-background transition-transform lg:static lg:translate-x-0`}
      >
        <ReaderSidebar>{sidebarContent}</ReaderSidebar>
      </div>

      {/* Main reading area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile menu button */}
        <div className="flex shrink-0 items-center border-b px-4 py-2 lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </Button>
        </div>

        {/* Reading pane */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
```

**Step 7: Create `/read` layout**

```tsx
// frontend/src/app/read/layout.tsx
export default function ReadLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
```

**Step 8: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 9: Commit**

```bash
git add frontend/src/components/shared/header.tsx \
  frontend/src/hooks/use-reader-settings.ts \
  frontend/src/components/reader/reader-layout.tsx \
  frontend/src/components/reader/reader-sidebar.tsx \
  frontend/src/components/reader/breadcrumbs.tsx \
  frontend/src/components/reader/typography-controls.tsx \
  frontend/src/app/read/layout.tsx
git commit -m "feat(reader): add reader layout shell, sidebar, header nav, and typography controls"
```

---

## Task 7: Frontend — Library Landing Page

**Files:**
- Create: `frontend/src/app/read/page.tsx`

**Step 1: Create library landing page**

```tsx
// frontend/src/app/read/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, BookText, MessageSquareText } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchLibraryStats } from "@/lib/api-client";
import type { LibraryStats } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

const SOURCE_CARDS = [
  {
    href: "/read/quran",
    title: "Quran",
    icon: BookOpen,
    color: "border-emerald-600",
    bgHover: "hover:bg-emerald-50 dark:hover:bg-emerald-950/20",
    iconColor: "text-emerald-600",
    getStat: (s: LibraryStats) =>
      `${s.quran_surah_count} Surahs \u00b7 ${s.quran_ayah_count.toLocaleString()} Ayahs`,
  },
  {
    href: "/read/hadith",
    title: "Hadith",
    icon: BookText,
    color: "border-amber-600",
    bgHover: "hover:bg-amber-50 dark:hover:bg-amber-950/20",
    iconColor: "text-amber-600",
    getStat: (s: LibraryStats) =>
      `${s.hadith_collection_count} Collections \u00b7 ${s.hadith_count.toLocaleString()} Hadiths`,
  },
  {
    href: "/read/tafsir",
    title: "Tafsir",
    icon: MessageSquareText,
    color: "border-violet-600",
    bgHover: "hover:bg-violet-50 dark:hover:bg-violet-950/20",
    iconColor: "text-violet-600",
    getStat: (s: LibraryStats) =>
      `${s.tafsir_count} Tafsirs \u00b7 ${s.tafsir_entry_count.toLocaleString()} Entries`,
  },
] as const;

export default function ReadPage() {
  const [stats, setStats] = useState<LibraryStats | null>(null);

  useEffect(() => {
    fetchLibraryStats().then(setStats).catch(console.error);
  }, []);

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-3xl p-6">
        <Breadcrumbs items={[{ label: "Library" }]} />

        <h1 className="mt-4 text-2xl font-semibold">Source Library</h1>
        <p className="mt-1 text-muted-foreground">
          Browse and read the Quran, Hadith collections, and Tafsir commentaries.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {SOURCE_CARDS.map(({ href, title, icon: Icon, color, bgHover, iconColor, getStat }) => (
            <Link
              key={href}
              href={href}
              className={`rounded-lg border-l-4 ${color} border bg-card p-5 transition-colors ${bgHover}`}
            >
              <Icon className={`h-8 w-8 ${iconColor}`} />
              <h2 className="mt-3 font-semibold">{title}</h2>
              {stats ? (
                <p className="mt-1 text-sm text-muted-foreground">
                  {getStat(stats)}
                </p>
              ) : (
                <Skeleton className="mt-1 h-4 w-32" />
              )}
            </Link>
          ))}
        </div>
      </div>
    </ReaderLayout>
  );
}
```

**Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/app/read/page.tsx
git commit -m "feat(reader): add library landing page with source type cards"
```

---

## Task 8: Frontend — Quran Reader (Surah List + Reading View)

**Files:**
- Create: `frontend/src/app/read/quran/page.tsx` — surah list
- Create: `frontend/src/app/read/quran/[surahNumber]/page.tsx` — surah reading view
- Create: `frontend/src/components/reader/quran/surah-list-sidebar.tsx` — sidebar surah navigation
- Create: `frontend/src/components/reader/quran/ayah-card.tsx` — individual ayah display
- Create: `frontend/src/components/reader/quran/tafsir-panel.tsx` — expandable tafsir per ayah

**Step 1: Create surah list sidebar**

```tsx
// frontend/src/components/reader/quran/surah-list-sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { SurahSummary } from "@/lib/types";

interface SurahListSidebarProps {
  surahs: SurahSummary[];
}

export function SurahListSidebar({ surahs }: SurahListSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="p-2">
      {surahs.map((s) => {
        const href = `/read/quran/${s.number}`;
        const active = pathname === href;
        return (
          <Link
            key={s.number}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              active
                ? "bg-emerald-50 text-emerald-900 font-medium dark:bg-emerald-950/30 dark:text-emerald-100"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border text-xs font-medium">
              {s.number}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground">
                {s.name_english}
              </div>
              <div className="truncate text-xs font-amiri" dir="rtl">
                {s.name_arabic}
              </div>
            </div>
            <span className="shrink-0 text-xs">{s.ayah_count}</span>
          </Link>
        );
      })}
    </div>
  );
}
```

**Step 2: Create tafsir panel**

```tsx
// frontend/src/components/reader/quran/tafsir-panel.tsx
"use client";

import { useEffect, useState } from "react";
import { fetchAyahTafsir } from "@/lib/api-client";
import type { TafsirForAyah } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface TafsirPanelProps {
  surahNumber: number;
  ayahNumber: number;
}

export function TafsirPanel({ surahNumber, ayahNumber }: TafsirPanelProps) {
  const [entries, setEntries] = useState<TafsirForAyah[] | null>(null);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEntries(null);
    setError(null);
    fetchAyahTafsir(surahNumber, ayahNumber)
      .then((data) => {
        setEntries(data);
        if (data.length > 0) setActiveSlug(data[0].tafsir_slug);
      })
      .catch(() => setError("Failed to load tafsir"));
  }, [surahNumber, ayahNumber]);

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }

  if (!entries) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No tafsir available for this ayah.
      </p>
    );
  }

  const active = entries.find((e) => e.tafsir_slug === activeSlug) ?? entries[0];

  return (
    <div className="space-y-3">
      {/* Tafsir tabs */}
      <div className="flex flex-wrap gap-1.5">
        {entries.map((e) => (
          <button
            key={e.tafsir_slug}
            onClick={() => setActiveSlug(e.tafsir_slug)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              e.tafsir_slug === activeSlug
                ? "border-violet-300 bg-violet-50 text-violet-800 dark:border-violet-700 dark:bg-violet-950/30 dark:text-violet-200"
                : "text-muted-foreground hover:bg-accent"
            )}
          >
            {e.tafsir_name}
            <span className="ml-1 opacity-60">({e.language})</span>
          </button>
        ))}
      </div>

      {/* Active tafsir content */}
      {active.text ? (
        <div
          className={cn(
            "rounded-md border-l-4 border-violet-600 bg-violet-50/50 p-4 text-sm leading-relaxed dark:bg-violet-950/10",
            active.language === "arabic" && "font-amiri text-right text-lg leading-loose"
          )}
          dir={active.language === "arabic" ? "rtl" : "ltr"}
        >
          {active.text}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No content available.</p>
      )}
    </div>
  );
}
```

**Step 3: Create ayah card**

```tsx
// frontend/src/components/reader/quran/ayah-card.tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { ArabicText } from "@/components/shared/arabic-text";
import { TafsirPanel } from "./tafsir-panel";
import type { AyahResponse } from "@/lib/types";

interface AyahCardProps {
  ayah: AyahResponse;
  surahNumber: number;
  arabicFontSize: number;
  englishFontSize: number;
}

export function AyahCard({
  ayah,
  surahNumber,
  arabicFontSize,
  englishFontSize,
}: AyahCardProps) {
  const [tafsirOpen, setTafsirOpen] = useState(false);

  return (
    <div className="border-b py-6 last:border-b-0">
      {/* Ayah number badge */}
      <div className="mb-3 flex items-center justify-between">
        <span className="flex h-8 w-8 items-center justify-center rounded-full border text-xs font-medium text-muted-foreground">
          {ayah.number}
        </span>
      </div>

      {/* Arabic text */}
      {ayah.text_arabic && (
        <ArabicText variant="quran" className="mb-3" style={{ fontSize: `${arabicFontSize}rem` }}>
          {ayah.text_arabic}
        </ArabicText>
      )}

      {/* English translation */}
      {ayah.text_english && (
        <p
          className="text-muted-foreground leading-relaxed"
          style={{ fontSize: `${englishFontSize}rem` }}
        >
          {ayah.text_english}
        </p>
      )}

      {/* Tafsir toggle */}
      <button
        onClick={() => setTafsirOpen(!tafsirOpen)}
        className="mt-3 flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 transition-colors dark:text-violet-400"
      >
        {tafsirOpen ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
        {tafsirOpen ? "Hide Tafsir" : "View Tafsir"}
      </button>

      {/* Tafsir panel (loaded on demand) */}
      {tafsirOpen && (
        <div className="mt-3">
          <TafsirPanel surahNumber={surahNumber} ayahNumber={ayah.number} />
        </div>
      )}
    </div>
  );
}
```

Note: The `ArabicText` component needs to accept a `style` prop. Modify `frontend/src/components/shared/arabic-text.tsx` to pass through `...rest` props:

```tsx
// Update the interface to include style:
interface ArabicTextProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: "default" | "quran";
  className?: string;
}

export function ArabicText({
  children,
  variant = "default",
  className,
  ...rest
}: ArabicTextProps) {
  return (
    <div
      dir="rtl"
      lang="ar"
      className={cn(
        "font-amiri",
        variant === "quran"
          ? "text-2xl leading-[2.25]"
          : "text-xl leading-loose",
        className
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
```

**Step 4: Create surah list page**

```tsx
// frontend/src/app/read/quran/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { SurahListSidebar } from "@/components/reader/quran/surah-list-sidebar";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchSurahs } from "@/lib/api-client";
import type { SurahSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function QuranPage() {
  const [surahs, setSurahs] = useState<SurahSummary[] | null>(null);

  useEffect(() => {
    fetchSurahs().then(setSurahs).catch(console.error);
  }, []);

  return (
    <ReaderLayout
      sidebarContent={surahs ? <SurahListSidebar surahs={surahs} /> : null}
    >
      <div className="mx-auto max-w-3xl p-6">
        <Breadcrumbs
          items={[
            { label: "Library", href: "/read" },
            { label: "Quran" },
          ]}
        />

        <h1 className="mt-4 text-2xl font-semibold">The Holy Quran</h1>
        <p className="mt-1 text-muted-foreground">
          {surahs ? `${surahs.length} Surahs` : "Loading..."}
        </p>

        {!surahs ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {surahs.map((s) => (
              <Link
                key={s.number}
                href={`/read/quran/${s.number}`}
                className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-emerald-50/50 dark:hover:bg-emerald-950/10"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border-2 border-emerald-200 text-sm font-semibold text-emerald-700 dark:border-emerald-800 dark:text-emerald-300">
                  {s.number}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{s.name_english}</div>
                  <div className="text-xs text-muted-foreground">
                    {s.ayah_count} Ayahs &middot; {s.revelation_type}
                  </div>
                </div>
                <div className="shrink-0 font-amiri text-lg" dir="rtl">
                  {s.name_arabic}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </ReaderLayout>
  );
}
```

**Step 5: Create surah reading view**

```tsx
// frontend/src/app/read/quran/[surahNumber]/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { SurahListSidebar } from "@/components/reader/quran/surah-list-sidebar";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { TypographyControls } from "@/components/reader/typography-controls";
import { AyahCard } from "@/components/reader/quran/ayah-card";
import { fetchSurahs, fetchSurahDetail } from "@/lib/api-client";
import { useReaderSettings } from "@/hooks/use-reader-settings";
import type { SurahSummary, SurahDetailResponse } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function SurahPage() {
  const params = useParams();
  const surahNumber = Number(params.surahNumber);

  const [surahs, setSurahs] = useState<SurahSummary[] | null>(null);
  const [detail, setDetail] = useState<SurahDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    settings,
    increaseArabic,
    decreaseArabic,
    increaseEnglish,
    decreaseEnglish,
  } = useReaderSettings();

  useEffect(() => {
    fetchSurahs().then(setSurahs).catch(console.error);
  }, []);

  useEffect(() => {
    setDetail(null);
    setError(null);
    fetchSurahDetail(surahNumber)
      .then(setDetail)
      .catch(() => setError("Failed to load surah"));
  }, [surahNumber]);

  return (
    <ReaderLayout
      sidebarContent={surahs ? <SurahListSidebar surahs={surahs} /> : null}
    >
      <div className="mx-auto max-w-3xl p-6">
        <div className="flex items-center justify-between">
          <Breadcrumbs
            items={[
              { label: "Library", href: "/read" },
              { label: "Quran", href: "/read/quran" },
              { label: detail?.surah.name_english ?? `Surah ${surahNumber}` },
            ]}
          />
          <TypographyControls
            arabicSize={settings.arabicFontSize}
            englishSize={settings.englishFontSize}
            onIncreaseArabic={increaseArabic}
            onDecreaseArabic={decreaseArabic}
            onIncreaseEnglish={increaseEnglish}
            onDecreaseEnglish={decreaseEnglish}
          />
        </div>

        {error && (
          <p className="mt-4 text-destructive">{error}</p>
        )}

        {!detail && !error ? (
          <div className="mt-6 space-y-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-2 border-b pb-6">
                <Skeleton className="h-6 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ))}
          </div>
        ) : detail ? (
          <>
            {/* Surah header */}
            <div className="mt-6 text-center">
              <h1 className="font-amiri text-3xl" dir="rtl">
                {detail.surah.name_arabic}
              </h1>
              <h2 className="mt-1 text-lg font-medium">
                {detail.surah.name_english}
              </h2>
              <p className="text-sm text-muted-foreground">
                {detail.surah.ayah_count} Ayahs &middot;{" "}
                {detail.surah.revelation_type}
              </p>
            </div>

            {/* Ayahs */}
            <div className="mt-8">
              {detail.ayahs.map((ayah) => (
                <AyahCard
                  key={ayah.number}
                  ayah={ayah}
                  surahNumber={surahNumber}
                  arabicFontSize={settings.arabicFontSize}
                  englishFontSize={settings.englishFontSize}
                />
              ))}
            </div>

            {/* Prev / Next navigation */}
            <div className="mt-8 flex items-center justify-between border-t pt-4">
              {surahNumber > 1 ? (
                <Link
                  href={`/read/quran/${surahNumber - 1}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                  {surahs?.[surahNumber - 2]?.name_english ?? `Surah ${surahNumber - 1}`}
                </Link>
              ) : (
                <div />
              )}
              {surahNumber < 114 ? (
                <Link
                  href={`/read/quran/${surahNumber + 1}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {surahs?.[surahNumber]?.name_english ?? `Surah ${surahNumber + 1}`}
                  <ChevronRight className="h-4 w-4" />
                </Link>
              ) : (
                <div />
              )}
            </div>
          </>
        ) : null}
      </div>
    </ReaderLayout>
  );
}
```

**Step 6: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 7: Commit**

```bash
git add frontend/src/app/read/quran/ \
  frontend/src/components/reader/quran/ \
  frontend/src/components/shared/arabic-text.tsx
git commit -m "feat(reader): add Quran reader with surah list, reading view, and expandable tafsir"
```

---

## Task 9: Frontend — Hadith Reader (Collections + Books + Reading View)

**Files:**
- Create: `frontend/src/app/read/hadith/page.tsx` — collection list
- Create: `frontend/src/app/read/hadith/[collection]/page.tsx` — book list
- Create: `frontend/src/app/read/hadith/[collection]/[bookNumber]/page.tsx` — hadiths in book
- Create: `frontend/src/components/reader/hadith/hadith-card.tsx` — individual hadith display

**Step 1: Create hadith card**

```tsx
// frontend/src/components/reader/hadith/hadith-card.tsx
import { ArabicText } from "@/components/shared/arabic-text";
import type { HadithResponseType } from "@/lib/types";

interface HadithCardProps {
  hadith: HadithResponseType;
  collectionName: string;
  bookNumber: number;
  arabicFontSize: number;
  englishFontSize: number;
}

export function HadithCard({
  hadith,
  collectionName,
  bookNumber,
  arabicFontSize,
  englishFontSize,
}: HadithCardProps) {
  return (
    <div className="border-l-4 border-l-amber-600 rounded-lg border bg-card p-5">
      {/* English text (primary) */}
      {hadith.text_english && (
        <p
          className="leading-relaxed"
          style={{ fontSize: `${englishFontSize}rem` }}
        >
          {hadith.text_english}
        </p>
      )}

      {/* Arabic text */}
      {hadith.text_arabic && (
        <ArabicText className="mt-4" style={{ fontSize: `${arabicFontSize}rem` }}>
          {hadith.text_arabic}
        </ArabicText>
      )}

      {/* Reference line */}
      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <span>{collectionName}</span>
        <span>&middot;</span>
        <span>Book {bookNumber}, Hadith {hadith.number}</span>
      </div>
    </div>
  );
}
```

**Step 2: Create collection list page**

```tsx
// frontend/src/app/read/hadith/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookText } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchHadithCollections } from "@/lib/api-client";
import type { CollectionSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function HadithPage() {
  const [collections, setCollections] = useState<CollectionSummary[] | null>(null);

  useEffect(() => {
    fetchHadithCollections().then(setCollections).catch(console.error);
  }, []);

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-3xl p-6">
        <Breadcrumbs
          items={[
            { label: "Library", href: "/read" },
            { label: "Hadith" },
          ]}
        />

        <h1 className="mt-4 text-2xl font-semibold">Hadith Collections</h1>
        <p className="mt-1 text-muted-foreground">
          {collections ? `${collections.length} collections` : "Loading..."}
        </p>

        {!collections ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-4">
            {collections.map((c) => (
              <Link
                key={c.slug}
                href={`/read/hadith/${c.slug}`}
                className="flex items-center gap-4 rounded-lg border-l-4 border-l-amber-600 border bg-card p-5 transition-colors hover:bg-amber-50/50 dark:hover:bg-amber-950/10"
              >
                <BookText className="h-8 w-8 shrink-0 text-amber-600" />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{c.name}</div>
                  <div className="text-sm text-muted-foreground">
                    by {c.author}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {c.book_count} Books &middot;{" "}
                    {c.hadith_count.toLocaleString()} Hadiths
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </ReaderLayout>
  );
}
```

**Step 3: Create book list page**

```tsx
// frontend/src/app/read/hadith/[collection]/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchHadithBooks, fetchHadithCollections } from "@/lib/api-client";
import type { HadithBookSummary, CollectionSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function HadithCollectionPage() {
  const params = useParams();
  const slug = params.collection as string;

  const [collection, setCollection] = useState<CollectionSummary | null>(null);
  const [books, setBooks] = useState<HadithBookSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Get collection name from collections list
    fetchHadithCollections()
      .then((cols) => {
        const match = cols.find((c) => c.slug === slug);
        if (match) setCollection(match);
      })
      .catch(console.error);

    fetchHadithBooks(slug)
      .then(setBooks)
      .catch(() => setError("Collection not found"));
  }, [slug]);

  const collectionName = collection?.name ?? slug;

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-3xl p-6">
        <Breadcrumbs
          items={[
            { label: "Library", href: "/read" },
            { label: "Hadith", href: "/read/hadith" },
            { label: collectionName },
          ]}
        />

        <h1 className="mt-4 text-2xl font-semibold">{collectionName}</h1>
        <p className="mt-1 text-muted-foreground">
          {books ? `${books.length} Books` : "Loading..."}
        </p>

        {error && <p className="mt-4 text-destructive">{error}</p>}

        {!books && !error ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : books ? (
          <div className="mt-6 space-y-2">
            {books.map((b) => (
              <Link
                key={b.number}
                href={`/read/hadith/${slug}/${b.number}`}
                className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-amber-50/50 dark:hover:bg-amber-950/10"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-sm font-medium">
                  {b.number}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">
                    {b.name_english || `Book ${b.number}`}
                  </div>
                  {b.name_arabic && (
                    <div className="text-sm font-amiri text-muted-foreground" dir="rtl">
                      {b.name_arabic}
                    </div>
                  )}
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {b.hadith_count} hadiths
                </span>
              </Link>
            ))}
          </div>
        ) : null}
      </div>
    </ReaderLayout>
  );
}
```

**Step 4: Create hadith reading view**

```tsx
// frontend/src/app/read/hadith/[collection]/[bookNumber]/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { TypographyControls } from "@/components/reader/typography-controls";
import { HadithCard } from "@/components/reader/hadith/hadith-card";
import { fetchHadithBookDetail, fetchHadithBooks } from "@/lib/api-client";
import { useReaderSettings } from "@/hooks/use-reader-settings";
import type { HadithBookDetailResponse, HadithBookSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function HadithBookPage() {
  const params = useParams();
  const slug = params.collection as string;
  const bookNumber = Number(params.bookNumber);

  const [detail, setDetail] = useState<HadithBookDetailResponse | null>(null);
  const [books, setBooks] = useState<HadithBookSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    settings,
    increaseArabic,
    decreaseArabic,
    increaseEnglish,
    decreaseEnglish,
  } = useReaderSettings();

  useEffect(() => {
    fetchHadithBooks(slug).then(setBooks).catch(console.error);
  }, [slug]);

  useEffect(() => {
    setDetail(null);
    setError(null);
    fetchHadithBookDetail(slug, bookNumber)
      .then(setDetail)
      .catch(() => setError("Book not found"));
  }, [slug, bookNumber]);

  const bookName = detail?.book.name_english || `Book ${bookNumber}`;

  // Find prev/next books
  const bookIndex = books?.findIndex((b) => b.number === bookNumber) ?? -1;
  const prevBook = bookIndex > 0 ? books![bookIndex - 1] : null;
  const nextBook = books && bookIndex < books.length - 1 ? books[bookIndex + 1] : null;

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-3xl p-6">
        <div className="flex items-center justify-between">
          <Breadcrumbs
            items={[
              { label: "Library", href: "/read" },
              { label: "Hadith", href: "/read/hadith" },
              { label: detail?.collection_name ?? slug, href: `/read/hadith/${slug}` },
              { label: bookName },
            ]}
          />
          <TypographyControls
            arabicSize={settings.arabicFontSize}
            englishSize={settings.englishFontSize}
            onIncreaseArabic={increaseArabic}
            onDecreaseArabic={decreaseArabic}
            onIncreaseEnglish={increaseEnglish}
            onDecreaseEnglish={decreaseEnglish}
          />
        </div>

        {error && <p className="mt-4 text-destructive">{error}</p>}

        {!detail && !error ? (
          <div className="mt-6 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-32 w-full" />
            ))}
          </div>
        ) : detail ? (
          <>
            <h1 className="mt-6 text-xl font-semibold">{bookName}</h1>
            {detail.book.name_arabic && (
              <p className="font-amiri text-lg text-muted-foreground" dir="rtl">
                {detail.book.name_arabic}
              </p>
            )}
            <p className="text-sm text-muted-foreground">
              {detail.hadiths.length} Hadiths
            </p>

            <div className="mt-6 space-y-4">
              {detail.hadiths.map((h) => (
                <HadithCard
                  key={h.number}
                  hadith={h}
                  collectionName={detail.collection_name}
                  bookNumber={bookNumber}
                  arabicFontSize={settings.arabicFontSize}
                  englishFontSize={settings.englishFontSize}
                />
              ))}
            </div>

            {/* Prev / Next navigation */}
            <div className="mt-8 flex items-center justify-between border-t pt-4">
              {prevBook ? (
                <Link
                  href={`/read/hadith/${slug}/${prevBook.number}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                  {prevBook.name_english || `Book ${prevBook.number}`}
                </Link>
              ) : (
                <div />
              )}
              {nextBook ? (
                <Link
                  href={`/read/hadith/${slug}/${nextBook.number}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {nextBook.name_english || `Book ${nextBook.number}`}
                  <ChevronRight className="h-4 w-4" />
                </Link>
              ) : (
                <div />
              )}
            </div>
          </>
        ) : null}
      </div>
    </ReaderLayout>
  );
}
```

**Step 5: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 6: Commit**

```bash
git add frontend/src/app/read/hadith/ \
  frontend/src/components/reader/hadith/
git commit -m "feat(reader): add Hadith reader with collection list, book list, and reading view"
```

---

## Task 10: Frontend — Tafsir Reader (List + Reading View)

**Files:**
- Create: `frontend/src/app/read/tafsir/page.tsx` — tafsir list
- Create: `frontend/src/app/read/tafsir/[tafsirSlug]/[surahNumber]/page.tsx` — tafsir reading view

**Step 1: Create tafsir list page**

```tsx
// frontend/src/app/read/tafsir/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessageSquareText } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchTafsirList } from "@/lib/api-client";
import type { TafsirSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function TafsirPage() {
  const [tafsirs, setTafsirs] = useState<TafsirSummary[] | null>(null);

  useEffect(() => {
    fetchTafsirList().then(setTafsirs).catch(console.error);
  }, []);

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-3xl p-6">
        <Breadcrumbs
          items={[
            { label: "Library", href: "/read" },
            { label: "Tafsir" },
          ]}
        />

        <h1 className="mt-4 text-2xl font-semibold">Tafsir Commentaries</h1>
        <p className="mt-1 text-muted-foreground">
          {tafsirs ? `${tafsirs.length} tafsirs available` : "Loading..."}
        </p>

        {!tafsirs ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-4">
            {tafsirs.map((t) => (
              <Link
                key={t.slug}
                href={`/read/tafsir/${t.slug}/1`}
                className="flex items-center gap-4 rounded-lg border-l-4 border-l-violet-600 border bg-card p-5 transition-colors hover:bg-violet-50/50 dark:hover:bg-violet-950/10"
              >
                <MessageSquareText className="h-8 w-8 shrink-0 text-violet-600" />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{t.name}</div>
                  <div className="text-sm text-muted-foreground">
                    by {t.author}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {t.surah_count} Surahs &middot; {t.language}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </ReaderLayout>
  );
}
```

**Step 2: Create tafsir surah reading view**

```tsx
// frontend/src/app/read/tafsir/[tafsirSlug]/[surahNumber]/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { TypographyControls } from "@/components/reader/typography-controls";
import { ArabicText } from "@/components/shared/arabic-text";
import { fetchTafsirSurahDetail } from "@/lib/api-client";
import { useReaderSettings } from "@/hooks/use-reader-settings";
import type { TafsirSurahDetailResponse } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function TafsirSurahPage() {
  const params = useParams();
  const tafsirSlug = params.tafsirSlug as string;
  const surahNumber = Number(params.surahNumber);

  const [detail, setDetail] = useState<TafsirSurahDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    settings,
    increaseArabic,
    decreaseArabic,
    increaseEnglish,
    decreaseEnglish,
  } = useReaderSettings();

  useEffect(() => {
    setDetail(null);
    setError(null);
    fetchTafsirSurahDetail(tafsirSlug, surahNumber)
      .then(setDetail)
      .catch(() => setError("Tafsir or surah not found"));
  }, [tafsirSlug, surahNumber]);

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-3xl p-6">
        <div className="flex items-center justify-between">
          <Breadcrumbs
            items={[
              { label: "Library", href: "/read" },
              { label: "Tafsir", href: "/read/tafsir" },
              { label: detail?.tafsir.name ?? tafsirSlug },
              { label: detail ? `Surah ${detail.surah_name}` : `Surah ${surahNumber}` },
            ]}
          />
          <TypographyControls
            arabicSize={settings.arabicFontSize}
            englishSize={settings.englishFontSize}
            onIncreaseArabic={increaseArabic}
            onDecreaseArabic={decreaseArabic}
            onIncreaseEnglish={increaseEnglish}
            onDecreaseEnglish={decreaseEnglish}
          />
        </div>

        {error && <p className="mt-4 text-destructive">{error}</p>}

        {!detail && !error ? (
          <div className="mt-6 space-y-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : detail ? (
          <>
            <h1 className="mt-6 text-xl font-semibold">{detail.tafsir.name}</h1>
            <p className="text-sm text-muted-foreground">
              Surah {detail.surah_name} ({detail.surah_number}) &middot;{" "}
              {detail.entries.length} entries
            </p>

            <div className="mt-8 space-y-8">
              {detail.entries.map((entry) => (
                <div key={entry.ayah_number} className="space-y-3">
                  {/* Ayah reference badge */}
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-0.5 text-xs font-medium text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200">
                      {detail.surah_number}:{entry.ayah_number}
                    </span>
                  </div>

                  {/* Tafsir content */}
                  {detail.tafsir.language === "arabic" && entry.text_arabic ? (
                    <ArabicText style={{ fontSize: `${settings.arabicFontSize}rem` }}>
                      {entry.text_arabic}
                    </ArabicText>
                  ) : entry.text_english ? (
                    <p
                      className="leading-relaxed"
                      style={{ fontSize: `${settings.englishFontSize}rem` }}
                    >
                      {entry.text_english}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">
                      No content available.
                    </p>
                  )}

                  <div className="border-b" />
                </div>
              ))}
            </div>

            {/* Prev / Next surah navigation */}
            <div className="mt-8 flex items-center justify-between border-t pt-4">
              {surahNumber > 1 ? (
                <Link
                  href={`/read/tafsir/${tafsirSlug}/${surahNumber - 1}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Surah {surahNumber - 1}
                </Link>
              ) : (
                <div />
              )}
              {surahNumber < 114 ? (
                <Link
                  href={`/read/tafsir/${tafsirSlug}/${surahNumber + 1}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Surah {surahNumber + 1}
                  <ChevronRight className="h-4 w-4" />
                </Link>
              ) : (
                <div />
              )}
            </div>
          </>
        ) : null}
      </div>
    </ReaderLayout>
  );
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/app/read/tafsir/
git commit -m "feat(reader): add Tafsir reader with list and per-surah reading view"
```

---

## Task 11: Lint, Build, and Integration Test

**Step 1: Run backend linter**

Run: `cd backend && pip install ruff && ruff check app/`
Expected: No errors (fix any issues)

**Step 2: Run frontend linter**

Run: `cd frontend && npm run lint`
Expected: No errors (fix any issues)

**Step 3: Run frontend TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

**Step 5: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 6: Fix any issues found**

Address lint errors, type errors, or build failures.

**Step 7: Commit any fixes**

```bash
git add -A
git commit -m "fix(reader): address lint and build issues"
```

---

## Task 12: Manual Integration Test

**Step 1: Start dev services**

Run: `docker compose -f docker-compose.dev.yml up -d` (PostgreSQL + Qdrant)
Run: `cd backend && uvicorn app.main:app --reload`
Run: `cd frontend && npm run dev`

**Step 2: Test backend endpoints**

Open each endpoint in a browser or curl:

```bash
# Library stats
curl http://localhost:8000/read/stats | python -m json.tool

# Quran
curl http://localhost:8000/read/quran/surahs | python -m json.tool
curl http://localhost:8000/read/quran/surahs/1 | python -m json.tool
curl http://localhost:8000/read/quran/surahs/1/ayahs/1/tafsir | python -m json.tool

# Hadith
curl http://localhost:8000/read/hadith/collections | python -m json.tool
curl http://localhost:8000/read/hadith/collections/sahih-bukhari/books | python -m json.tool
curl http://localhost:8000/read/hadith/collections/sahih-bukhari/books/1 | python -m json.tool

# Tafsir
curl http://localhost:8000/read/tafsir | python -m json.tool
curl http://localhost:8000/read/tafsir/tafsir-ibn-kathir/surahs/1 | python -m json.tool
```

**Step 3: Test frontend pages**

Visit in browser:
- `http://localhost:3000/read` — Library landing with stats
- `http://localhost:3000/read/quran` — Surah list (114 cards)
- `http://localhost:3000/read/quran/1` — Al-Fatihah reading view, click "View Tafsir" on an ayah
- `http://localhost:3000/read/hadith` — 6 collections
- `http://localhost:3000/read/hadith/sahih-bukhari` — Books list
- `http://localhost:3000/read/hadith/sahih-bukhari/1` — Hadiths in Book 1
- `http://localhost:3000/read/tafsir` — Tafsir list
- `http://localhost:3000/read/tafsir/tafsir-ibn-kathir/1` — Tafsir for Surah 1

**Step 4: Test responsive design**

- Toggle browser to mobile width (~375px)
- Verify sidebar becomes a hamburger menu
- Verify text remains readable

**Step 5: Test typography controls**

- Click A+/A- buttons
- Verify Arabic and English font sizes change independently
- Refresh page — verify settings persist

**Step 6: Final commit**

```bash
git add -A
git commit -m "feat(reader): complete reader feature with all source types"
```
