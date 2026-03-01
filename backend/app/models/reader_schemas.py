from pydantic import BaseModel


# --- Quran ---


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


# --- Hadith ---


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


# --- Tafsir ---


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


# --- Library Stats ---


class LibraryStats(BaseModel):
    quran_surah_count: int
    quran_ayah_count: int
    hadith_collection_count: int
    hadith_count: int
    tafsir_count: int
    tafsir_entry_count: int
