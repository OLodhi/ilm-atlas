"""Reader service layer — PostgreSQL JSONB queries for all browse operations.

Provides functions that power the /library/* read-only endpoints:
Quran surahs/ayahs, Hadith collections/books/hadiths, Tafsir browsing,
and aggregate library statistics.
"""

import re

from sqlalchemy import select, func, cast, Integer, distinct, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Book, Source, Chunk
from app.models.reader_schemas import (
    SurahSummary,
    AyahResponse,
    SurahDetailResponse,
    TafsirForAyah,
    CollectionSummary,
    HadithBookSummary,
    HadithResponse,
    HadithBookDetailResponse,
    TafsirSummary,
    TafsirEntryResponse,
    TafsirSurahDetailResponse,
    LibraryStats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_text(column, key: str):
    """Extract text from a JSONB column: column->>'key'."""
    return column[key].astext


def _json_int(column, key: str):
    """Extract integer from a JSONB column: (column->>'key')::int."""
    return cast(column[key].astext, Integer)


def slugify(name: str) -> str:
    """Derive a URL-safe slug from a book title.

    Examples:
        "Sahih Bukhari"                  -> "sahih-bukhari"
        "Tafsir Ibn Kathir"              -> "tafsir-ibn-kathir"
        "Tafsir Ibn Kathir (Abridged)"   -> "tafsir-ibn-kathir-abridged"
        "Ma'arif al-Qur'an"             -> "maarif-al-quran"
        "Jami' Al-Tirmidhi"             -> "jami-al-tirmidhi"
        "Sunan An-Nasa'i"               -> "sunan-an-nasai"
    """
    s = name.lower()
    # Remove apostrophes / right-single-quotes (contraction marks)
    s = re.sub(r"['\u2019]", "", s)
    # Replace any non-alphanumeric character (except hyphen) with a hyphen
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    # Collapse consecutive hyphens
    s = re.sub(r"-{2,}", "-", s)
    # Strip leading/trailing hyphens
    return s.strip("-")


# ---------------------------------------------------------------------------
# Quran
# ---------------------------------------------------------------------------

async def get_quran_surahs(session: AsyncSession) -> list[SurahSummary]:
    """Return distinct surahs from quran chunks, grouped by surah_number."""
    meta = Chunk.metadata_json

    stmt = (
        select(
            _json_int(meta, "surah_number").label("surah_number"),
            _json_text(meta, "surah_name_arabic").label("name_arabic"),
            _json_text(meta, "surah_name_english").label("name_english"),
            func.count().label("ayah_count"),
            func.min(_json_text(meta, "revelation_type")).label("revelation_type"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "ayah",
                Book.category == "quran",
            )
        )
        .group_by(
            _json_int(meta, "surah_number"),
            _json_text(meta, "surah_name_arabic"),
            _json_text(meta, "surah_name_english"),
        )
        .order_by(_json_int(meta, "surah_number"))
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        SurahSummary(
            number=row.surah_number,
            name_arabic=row.name_arabic,
            name_english=row.name_english,
            ayah_count=row.ayah_count,
            revelation_type=row.revelation_type or "",
        )
        for row in rows
    ]


async def get_surah_detail(
    session: AsyncSession, surah_number: int
) -> SurahDetailResponse | None:
    """Return all ayahs for a given surah number."""
    meta = Chunk.metadata_json

    # First, fetch the surah summary
    summary_stmt = (
        select(
            _json_int(meta, "surah_number").label("surah_number"),
            _json_text(meta, "surah_name_arabic").label("name_arabic"),
            _json_text(meta, "surah_name_english").label("name_english"),
            func.count().label("ayah_count"),
            func.min(_json_text(meta, "revelation_type")).label("revelation_type"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "ayah",
                Book.category == "quran",
                _json_int(meta, "surah_number") == surah_number,
            )
        )
        .group_by(
            _json_int(meta, "surah_number"),
            _json_text(meta, "surah_name_arabic"),
            _json_text(meta, "surah_name_english"),
        )
    )

    summary_result = await session.execute(summary_stmt)
    summary_row = summary_result.first()
    if summary_row is None:
        return None

    surah = SurahSummary(
        number=summary_row.surah_number,
        name_arabic=summary_row.name_arabic,
        name_english=summary_row.name_english,
        ayah_count=summary_row.ayah_count,
        revelation_type=summary_row.revelation_type or "",
    )

    # Fetch all ayahs ordered by ayah number
    ayah_stmt = (
        select(
            _json_int(meta, "ayah_number").label("ayah_number"),
            Chunk.content_arabic,
            Chunk.content_english,
            _json_text(meta, "juz").label("juz"),
            _json_text(meta, "ruku").label("ruku"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "ayah",
                Book.category == "quran",
                _json_int(meta, "surah_number") == surah_number,
            )
        )
        .order_by(_json_int(meta, "ayah_number"))
    )

    ayah_result = await session.execute(ayah_stmt)
    ayah_rows = ayah_result.all()

    ayahs = [
        AyahResponse(
            number=row.ayah_number,
            text_arabic=row.content_arabic,
            text_english=row.content_english,
            juz=int(row.juz) if row.juz else None,
            ruku=int(row.ruku) if row.ruku else None,
        )
        for row in ayah_rows
    ]

    return SurahDetailResponse(surah=surah, ayahs=ayahs)


async def get_tafsir_for_ayah(
    session: AsyncSession, surah_number: int, ayah_number: int
) -> list[TafsirForAyah]:
    """Return all tafsir entries for a specific ayah across all tafsir books."""
    meta = Chunk.metadata_json

    stmt = (
        select(
            _json_text(meta, "tafsir_name").label("tafsir_name"),
            Book.title.label("book_title"),
            Book.language,
            Chunk.content_arabic,
            Chunk.content_english,
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "tafsir",
                Book.category == "tafsir",
                _json_int(meta, "surah_number") == surah_number,
                _json_int(meta, "ayah_number") == ayah_number,
            )
        )
        .order_by(_json_text(meta, "tafsir_name"))
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        TafsirForAyah(
            tafsir_name=row.tafsir_name,
            tafsir_slug=slugify(row.book_title),
            language=row.language,
            text=row.content_english or row.content_arabic,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Hadith
# ---------------------------------------------------------------------------

async def get_hadith_collections(session: AsyncSession) -> list[CollectionSummary]:
    """Return distinct hadith collections from the books table.

    Each collection corresponds to a Book row with category='hadith'.
    The slug is derived from the metadata_json->>'book_slug' stored on
    the chunks (set during hadith ingestion).
    """
    meta = Chunk.metadata_json

    stmt = (
        select(
            Book.title.label("name"),
            Book.author,
            func.min(_json_text(meta, "book_slug")).label("slug"),
            func.count().label("hadith_count"),
            func.count(
                distinct(_json_text(meta, "chapter_number"))
            ).label("book_count"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "hadith",
                Book.category == "hadith",
            )
        )
        .group_by(Book.id, Book.title, Book.author)
        .order_by(Book.title)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        CollectionSummary(
            slug=row.slug,
            name=row.name,
            author=row.author,
            hadith_count=row.hadith_count,
            book_count=row.book_count,
        )
        for row in rows
    ]


async def get_hadith_books(
    session: AsyncSession, collection_slug: str
) -> tuple[str, list[HadithBookSummary]] | None:
    """Return books/chapters within a hadith collection.

    Returns (collection_name, list_of_books) or None if not found.
    The collection is identified by the book_slug stored in chunk metadata.
    """
    meta = Chunk.metadata_json

    # First, verify the collection exists and get its name
    name_stmt = (
        select(Book.title)
        .join(Source, Source.book_id == Book.id)
        .join(Chunk, Chunk.source_id == Source.id)
        .where(
            and_(
                Chunk.chunk_type == "hadith",
                Book.category == "hadith",
                _json_text(meta, "book_slug") == collection_slug,
            )
        )
        .limit(1)
    )

    name_result = await session.execute(name_stmt)
    name_row = name_result.first()
    if name_row is None:
        return None

    collection_name = name_row.title

    # Fetch distinct chapters
    stmt = (
        select(
            _json_int(meta, "chapter_number").label("chapter_number"),
            func.min(_json_text(meta, "chapter_arabic")).label("chapter_arabic"),
            func.min(_json_text(meta, "chapter_english")).label("chapter_english"),
            func.count().label("hadith_count"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "hadith",
                Book.category == "hadith",
                _json_text(meta, "book_slug") == collection_slug,
            )
        )
        .group_by(_json_int(meta, "chapter_number"))
        .order_by(_json_int(meta, "chapter_number"))
    )

    result = await session.execute(stmt)
    rows = result.all()

    books = [
        HadithBookSummary(
            number=row.chapter_number,
            name_arabic=row.chapter_arabic,
            name_english=row.chapter_english,
            hadith_count=row.hadith_count,
        )
        for row in rows
    ]

    return collection_name, books


async def get_hadith_book_detail(
    session: AsyncSession, collection_slug: str, book_number: int
) -> HadithBookDetailResponse | None:
    """Return hadiths in a specific book/chapter within a hadith collection."""
    meta = Chunk.metadata_json

    # Fetch book/chapter info
    info_stmt = (
        select(
            Book.title.label("collection_name"),
            func.min(_json_text(meta, "chapter_arabic")).label("chapter_arabic"),
            func.min(_json_text(meta, "chapter_english")).label("chapter_english"),
            func.count().label("hadith_count"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "hadith",
                Book.category == "hadith",
                _json_text(meta, "book_slug") == collection_slug,
                _json_int(meta, "chapter_number") == book_number,
            )
        )
        .group_by(Book.title)
    )

    info_result = await session.execute(info_stmt)
    info_row = info_result.first()
    if info_row is None:
        return None

    book_summary = HadithBookSummary(
        number=book_number,
        name_arabic=info_row.chapter_arabic,
        name_english=info_row.chapter_english,
        hadith_count=info_row.hadith_count,
    )

    # Fetch hadiths in this chapter
    hadiths_stmt = (
        select(
            _json_int(meta, "hadith_number").label("hadith_number"),
            Chunk.content_arabic,
            Chunk.content_english,
            _json_text(meta, "chapter_english").label("chapter"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "hadith",
                Book.category == "hadith",
                _json_text(meta, "book_slug") == collection_slug,
                _json_int(meta, "chapter_number") == book_number,
            )
        )
        .order_by(_json_int(meta, "hadith_number"))
    )

    hadiths_result = await session.execute(hadiths_stmt)
    hadith_rows = hadiths_result.all()

    hadiths = [
        HadithResponse(
            number=row.hadith_number,
            text_arabic=row.content_arabic,
            text_english=row.content_english,
            chapter=row.chapter,
        )
        for row in hadith_rows
    ]

    return HadithBookDetailResponse(
        book=book_summary,
        collection_name=info_row.collection_name,
        collection_slug=collection_slug,
        hadiths=hadiths,
    )


# ---------------------------------------------------------------------------
# Tafsir
# ---------------------------------------------------------------------------

async def get_tafsir_list(session: AsyncSession) -> list[TafsirSummary]:
    """Return all tafsir books with their surah counts."""
    meta = Chunk.metadata_json

    stmt = (
        select(
            Book.title.label("name"),
            Book.author,
            Book.language,
            func.count(
                distinct(_json_int(meta, "surah_number"))
            ).label("surah_count"),
        )
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(
            and_(
                Chunk.chunk_type == "tafsir",
                Book.category == "tafsir",
            )
        )
        .group_by(Book.id, Book.title, Book.author, Book.language)
        .order_by(Book.title)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        TafsirSummary(
            slug=slugify(row.name),
            name=row.name,
            author=row.author,
            language=row.language,
            surah_count=row.surah_count,
        )
        for row in rows
    ]


async def get_tafsir_surah_detail(
    session: AsyncSession, tafsir_slug: str, surah_number: int
) -> TafsirSurahDetailResponse | None:
    """Return tafsir entries for a specific surah within a tafsir book.

    Since tafsir slugs are computed from book titles (not stored), we need
    to first find which Book matches the slug, then query its chunks.
    """
    meta = Chunk.metadata_json

    # Find the tafsir book matching this slug
    books_stmt = (
        select(Book.id, Book.title, Book.author, Book.language)
        .where(Book.category == "tafsir")
    )
    books_result = await session.execute(books_stmt)
    book_rows = books_result.all()

    matching_book = None
    for book_row in book_rows:
        if slugify(book_row.title) == tafsir_slug:
            matching_book = book_row
            break

    if matching_book is None:
        return None

    # Count distinct surahs for this tafsir (for the summary)
    surah_count_stmt = (
        select(func.count(distinct(_json_int(meta, "surah_number"))))
        .join(Source, Chunk.source_id == Source.id)
        .where(
            and_(
                Chunk.chunk_type == "tafsir",
                Source.book_id == matching_book.id,
            )
        )
    )
    surah_count_result = await session.execute(surah_count_stmt)
    surah_count = surah_count_result.scalar() or 0

    # Fetch entries for this surah
    entries_stmt = (
        select(
            _json_int(meta, "ayah_number").label("ayah_number"),
            Chunk.content_arabic,
            Chunk.content_english,
        )
        .join(Source, Chunk.source_id == Source.id)
        .where(
            and_(
                Chunk.chunk_type == "tafsir",
                Source.book_id == matching_book.id,
                _json_int(meta, "surah_number") == surah_number,
            )
        )
        .order_by(_json_int(meta, "ayah_number"))
    )

    entries_result = await session.execute(entries_stmt)
    entry_rows = entries_result.all()

    if not entry_rows:
        return None

    # Get the surah name from the first entry
    surah_name_stmt = (
        select(_json_text(meta, "surah_name_english"))
        .join(Source, Chunk.source_id == Source.id)
        .where(
            and_(
                Chunk.chunk_type == "tafsir",
                Source.book_id == matching_book.id,
                _json_int(meta, "surah_number") == surah_number,
            )
        )
        .limit(1)
    )
    surah_name_result = await session.execute(surah_name_stmt)
    surah_name = surah_name_result.scalar() or ""

    tafsir_summary = TafsirSummary(
        slug=tafsir_slug,
        name=matching_book.title,
        author=matching_book.author,
        language=matching_book.language,
        surah_count=surah_count,
    )

    entries = [
        TafsirEntryResponse(
            ayah_number=row.ayah_number,
            text_arabic=row.content_arabic,
            text_english=row.content_english,
        )
        for row in entry_rows
    ]

    return TafsirSurahDetailResponse(
        tafsir=tafsir_summary,
        surah_number=surah_number,
        surah_name=surah_name,
        entries=entries,
    )


# ---------------------------------------------------------------------------
# Library Stats
# ---------------------------------------------------------------------------

async def get_library_stats(session: AsyncSession) -> LibraryStats:
    """Return aggregate counts across all library content."""
    meta = Chunk.metadata_json

    # Quran stats
    quran_base = (
        select(Chunk.id)
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(and_(Chunk.chunk_type == "ayah", Book.category == "quran"))
    )

    quran_surah_stmt = select(
        func.count(distinct(_json_int(meta, "surah_number")))
    ).select_from(
        quran_base.add_columns(_json_int(meta, "surah_number")).subquery()
    )

    quran_ayah_stmt = select(func.count()).select_from(quran_base.subquery())

    # Hadith stats
    hadith_base = (
        select(Chunk.id)
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(and_(Chunk.chunk_type == "hadith", Book.category == "hadith"))
    )

    hadith_collection_stmt = select(
        func.count(distinct(Book.id))
    ).select_from(
        hadith_base.add_columns(Book.id).subquery()
    )

    hadith_count_stmt = select(func.count()).select_from(hadith_base.subquery())

    # Tafsir stats
    tafsir_base = (
        select(Chunk.id)
        .join(Source, Chunk.source_id == Source.id)
        .join(Book, Source.book_id == Book.id)
        .where(and_(Chunk.chunk_type == "tafsir", Book.category == "tafsir"))
    )

    tafsir_book_stmt = select(
        func.count(distinct(Book.id))
    ).select_from(
        tafsir_base.add_columns(Book.id).subquery()
    )

    tafsir_entry_stmt = select(func.count()).select_from(tafsir_base.subquery())

    # Execute all in parallel-ish (SQLAlchemy async session serialises,
    # but keeps the code intent clear)
    quran_surah_count = (await session.execute(quran_surah_stmt)).scalar() or 0
    quran_ayah_count = (await session.execute(quran_ayah_stmt)).scalar() or 0
    hadith_collection_count = (await session.execute(hadith_collection_stmt)).scalar() or 0
    hadith_count = (await session.execute(hadith_count_stmt)).scalar() or 0
    tafsir_count = (await session.execute(tafsir_book_stmt)).scalar() or 0
    tafsir_entry_count = (await session.execute(tafsir_entry_stmt)).scalar() or 0

    return LibraryStats(
        quran_surah_count=quran_surah_count,
        quran_ayah_count=quran_ayah_count,
        hadith_collection_count=hadith_collection_count,
        hadith_count=hadith_count,
        tafsir_count=tafsir_count,
        tafsir_entry_count=tafsir_entry_count,
    )
