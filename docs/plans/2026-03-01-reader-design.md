# Reader Feature Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create the implementation plan from this design.

**Goal:** Allow users to read Quran, Hadith, and Tafsir source material in full through a dedicated, publicly accessible reader interface.

**Architecture:** Library-style reader with dedicated routes per source type, sidebar navigation, and stacked Arabic/English text layout. Backend serves content from PostgreSQL (no vector search). Tafsir integrates into Quran reader as expandable per-ayah panels.

**Tech Stack:** Next.js 14 App Router, Tailwind CSS, Shadcn/UI, FastAPI, SQLAlchemy async, PostgreSQL.

---

## 1. Route Structure

```
/read                                    → Library landing (source type grid)
/read/quran                              → Surah list (114 surahs)
/read/quran/[surahNumber]                → Full surah reading view
/read/hadith                             → Collection list (6 collections)
/read/hadith/[collection]                → Books within a collection
/read/hadith/[collection]/[bookNumber]   → Hadiths in that book
/read/tafsir                             → Available tafsirs list
/read/tafsir/[tafsirSlug]/[surahNumber]  → Tafsir commentary for a surah
```

All routes are public (no authentication required).

## 2. Navigation

### Header
Add "Read" link to existing header alongside "Chat":
```
Ilm Atlas    [Chat]  [Read]     [👤]
```

### Sidebar
Contextual sidebar adapts to current source type:
- **Quran:** 114 surahs listed with Arabic/English names and ayah counts. Active surah highlighted.
- **Hadith:** Breadcrumb-driven. Top level shows collections, drilling into a collection shows its books.
- **Tafsir:** Lists available tafsirs, then surahs when a tafsir is selected.

On mobile: sidebar becomes a slide-out drawer triggered by a menu button.

### Breadcrumbs
Every reader page shows breadcrumbs:
```
Read > Quran > Surah Al-Baqarah
Read > Hadith > Sahih Bukhari > Book 1: Revelation
Read > Tafsir > Ibn Kathir > Surah Al-Fatihah
```

### Prev/Next Navigation
Bottom of each reading view shows prev/next chapter navigation:
```
[← Al-Fatihah]                    [Ali 'Imran →]
```

## 3. Reading Pane Layouts

### Quran Reading View

Per-ayah stacked layout (following quran.com pattern):
1. Arabic text — Amiri font, 1.5rem, RTL, line-height 2.25
2. English translation below — Inter font, 1rem, LTR, line-height 1.6
3. Ayah number badge — right-aligned, muted color
4. "View Tafsir" expandable button
5. Thin separator between ayahs

Tafsir expansion:
- Inline panel with violet left border (matching existing tafsir color)
- Tabs to switch between available tafsirs (Ibn Kathir, Tabari, Qurtubi, Jalalayn, etc.)
- Tafsir data loaded on demand (not pre-fetched with the surah)
- API call: `GET /read/quran/surahs/{number}/ayahs/{ayah}/tafsir`

### Hadith Reading View

Per-hadith card layout (following sunnah.com pattern):
1. English translation first (primary reading language)
2. Arabic text below — Amiri font, RTL
3. Reference line: collection name, book number, hadith number
4. Amber left border (matching existing hadith color)
5. Card-style separation between hadiths

Chapter headers display as section dividers between groups of hadiths.

### Tafsir Reading View

Commentary-first layout:
1. Referenced ayah shown as a header quote block (emerald border)
   - Arabic text + English translation of the ayah
2. Tafsir commentary text below
3. Separator, then next ayah with its commentary

### Library Landing Page

Grid of three source type cards:
- **Quran** — "114 Surahs, 6,236 Ayahs" with emerald accent
- **Hadith** — "6 Collections, ~34,000 Hadiths" with amber accent
- **Tafsir** — "5 Tafsirs, ~36,000 Entries" with violet accent

Each card links to the respective source type listing.

## 4. Typography Controls

Settings bar at the top of the reading pane:
```
[A-] [A+]  [☀ Light ▼]
```

- Independent Arabic/English font size controls
- Theme toggle: Light, Dark, Sepia
- Persisted to `localStorage` (no auth needed)

Default sizes:
- Arabic: 1.5rem (Quran variant: 1.5rem)
- English: 1rem
- Step size: 0.125rem per click

## 5. Backend API

### New Router: `/read`

All endpoints are public, no authentication. Rate limited at 60 req/min.

```
GET /read/quran/surahs
  → SurahSummary[] (number, name_arabic, name_english, ayah_count, revelation_type)

GET /read/quran/surahs/{number}
  → { surah: SurahSummary, ayahs: AyahResponse[] }
  → AyahResponse: number, text_arabic, text_english, juz, ruku

GET /read/quran/surahs/{number}/ayahs/{ayah}/tafsir
  → TafsirForAyah[] (tafsir_name, tafsir_slug, text_arabic, text_english)

GET /read/hadith/collections
  → CollectionSummary[] (slug, name, hadith_count, book_count)

GET /read/hadith/collections/{slug}/books
  → HadithBookSummary[] (number, name_arabic, name_english, hadith_range)

GET /read/hadith/collections/{slug}/books/{number}
  → { book: HadithBookSummary, hadiths: HadithResponse[] }
  → HadithResponse: number, text_arabic, text_english, chapter

GET /read/tafsir
  → TafsirSummary[] (slug, name, author, surah_count)

GET /read/tafsir/{slug}/surahs/{number}
  → { tafsir: TafsirSummary, entries: TafsirEntryResponse[] }
  → TafsirEntryResponse: ayah_number, text_arabic, text_english
```

### Data Source

All endpoints query **PostgreSQL only** (chunks table + books/sources joins). No Qdrant vector search needed for sequential reading.

Query strategy uses `metadata_json` JSONB field for structural navigation:
- Quran chunks: `metadata_json->>'surah_number'`, `metadata_json->>'ayah_number'`
- Hadith chunks: `metadata_json->>'hadith_number'`, `section` field for book/chapter
- Tafsir chunks: `metadata_json->>'surah_number'`, `metadata_json->>'ayah_number'`

### Response Schemas (Pydantic)

```python
class SurahSummary(BaseModel):
    number: int
    name_arabic: str
    name_english: str
    ayah_count: int
    revelation_type: str  # "meccan" or "medinan"

class AyahResponse(BaseModel):
    number: int
    text_arabic: str | None
    text_english: str | None
    juz: int | None
    ruku: int | None

class CollectionSummary(BaseModel):
    slug: str
    name: str
    hadith_count: int
    book_count: int

class HadithBookSummary(BaseModel):
    number: int
    name_arabic: str | None
    name_english: str | None
    hadith_range: str  # e.g. "1-56"

class HadithResponse(BaseModel):
    number: int
    text_arabic: str | None
    text_english: str | None
    chapter: str | None

class TafsirSummary(BaseModel):
    slug: str
    name: str
    author: str
    surah_count: int

class TafsirEntryResponse(BaseModel):
    ayah_number: int
    text_arabic: str | None
    text_english: str | None

class TafsirForAyah(BaseModel):
    tafsir_name: str
    tafsir_slug: str
    text_arabic: str | None
    text_english: str | None
```

## 6. Responsive Design

- **Desktop (lg+):** Sidebar (280px) + Reading pane (fluid)
- **Tablet (md):** Collapsible sidebar overlay
- **Mobile (sm):** Full-width reading pane, sidebar as slide-out drawer, bottom prev/next nav

Mobile reading pane uses slightly smaller fonts but maintains the stacked Arabic/English layout.

## 7. Scope

### V1 (This Implementation)
- Library landing page with source type cards
- Quran reader with surah list + full surah reading view
- Hadith reader with collection list + book list + hadiths per book
- Tafsir reader with tafsir list + per-surah tafsir reading view
- Per-ayah tafsir expansion in Quran reader
- Typography controls (font size, theme)
- Sidebar navigation + breadcrumbs + prev/next
- Responsive design (mobile-first)
- Public access (no auth)
- Backend browse endpoints (PostgreSQL-based)
- Deep-linkable URLs

### Deferred (V2+)
- Bookmarks (requires auth)
- Reading progress tracking (requires auth)
- Audio playback
- Word-by-word translation
- Full-text search within reader
- Mushaf mode (traditional page layout)
- Cross-reference links between sources
- Share buttons
