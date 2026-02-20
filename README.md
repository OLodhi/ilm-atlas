# Ilm Atlas

**An AI-powered research tool for exploring authentic Islamic sources** — grounded in the Quran, Sunnah, and scholarly consensus of Ahle-us-Sunnah wal Jama'ah.

Ilm Atlas uses Retrieval-Augmented Generation (RAG) to answer questions about Islam by searching a curated knowledge base of over 76,000 primary source texts and synthesizing answers with full citations. Every response is traceable back to its original source — no hallucinations, no invented rulings.

---

## What It Does

**Ask a question in plain English (or Arabic), and Ilm Atlas will:**

1. Search across the Quran, six major Hadith collections, and five classical Tafsir works
2. Retrieve the most relevant primary source texts
3. Generate a well-structured answer grounded entirely in those sources
4. Present numbered citations you can click to see the original Arabic and English text

### Example Questions

- *"What does Islam say about patience?"*
- *"What are the rights of a wife in Islam?"*
- *"How many times is Prophet Isa mentioned in the Quran?"*
- *"What is Surah Al-Kahf about?"*
- *"Explain the conditions of Zakat"*

---

## Features

### Multi-Turn Chat with Streaming
Conversations maintain full context. Ask follow-up questions naturally — the system rewrites them into standalone queries for better retrieval. Responses stream in real-time token by token, so you see the answer forming within seconds.

### Source-First Answers
Every answer is backed by retrieved source texts. Numbered citations like **[1]**, **[2]** link directly to the original passages. The AI never invents or infers religious rulings beyond what the sources say.

### Arabic + English Side by Side
Source citations display the original Arabic text (in Uthmani script) alongside the English translation. Arabic text renders with proper RTL layout and traditional typography.

### Intelligent Search
- **Query classification** — detects whether you're asking a semantic question, counting something, looking up metadata, or requesting a list
- **Query expansion** — breaks complex questions into sub-topics for broader coverage
- **Hybrid search** — combines vector similarity with keyword matching for exhaustive results
- **Category detection** — automatically focuses on Quran, Hadith, or Tafsir based on the question
- **Auto-translation** — Arabic-only citations are automatically translated to English via the LLM

### Adab (Etiquette) Layer
- Proper honorifics throughout: &#xFDFA; for the Prophet, RA for Companions, RH for scholars
- Never issues personal fatwas or religious rulings
- Presents scholarly differences (_ikhtilaf_) fairly, defaulting to mainstream Sunni positions
- Maintains the source hierarchy: Quran first, then Hadith

### Research Bench
A split-view interface showing the AI answer on the left and the actual source texts on the right. Filter results by madhab (Hanafi, Shafi'i, Maliki, Hanbali) or category (Quran, Hadith, Fiqh, Aqeedah).

### Admin Panel
Upload and manage source texts (PDF, images with OCR, plain text). Track ingestion status and browse the books inventory.

---

## Knowledge Base

| Source | Texts | Description |
|--------|------:|-------------|
| **Quran** | 6,236 | Every ayah in Uthmani script + Sahih International English translation |
| **Sahih Bukhari** | 7,276 | The most authentic Hadith collection |
| **Sahih Muslim** | 7,564 | Second most authentic Hadith collection |
| **Jami' Al-Tirmidhi** | 3,956 | Known for grading narrations |
| **Sunan Abu Dawood** | 5,274 | Focused on legal rulings |
| **Sunan Ibn Majah** | 4,341 | Covers unique narrations |
| **Sunan An-Nasa'i** | 5,761 | Rigorous authentication standards |
| **Tafsir Ibn Kathir** | 8,100 | Arabic + abridged English (classical exegesis) |
| **Ma'arif al-Qur'an** | 3,037 | Mufti Shafi Usmani's Hanafi commentary |
| **Tafsir Al-Sa'di** | 6,177 | Accessible modern commentary |
| **Tafsir Al-Qurtubi** | 6,235 | Comprehensive legal exegesis |
| **Tafsir Al-Jalalayn** | 12,472 | Arabic + English (concise classical tafsir) |
| | **~76,000** | **Total indexed passages** |

---

## Architecture

```
ilm-atlas/
  frontend/     Next.js 14  ·  Tailwind CSS  ·  Shadcn/UI
  backend/      FastAPI  ·  SQLAlchemy  ·  Qdrant  ·  OpenRouter
  scripts/      Data ingestion pipelines
```

### How a Query Works

```
User question
  │
  ├─ Classify intent (semantic / counting / metadata / listing)
  ├─ Expand into 5-8 sub-topic search phrases
  ├─ Embed with BAAI/bge-m3 (1024-dim vectors)
  │
  ├─ Vector search ──────┐
  ├─ Keyword search ─────┤  Qdrant (76k passages)
  ├─ Metadata lookup ────┘
  │
  ├─ Merge, deduplicate, diversify sources
  ├─ Group Quranic ayahs by ruku (passage-level context)
  │
  ├─ Stream to LLM (Qwen 2.5 via OpenRouter)
  │   with system prompt enforcing adab + citation rules
  │
  ├─ Build numbered citations [1], [2], ...
  ├─ Auto-translate Arabic-only citations
  │
  └─ SSE stream → user sees tokens in real-time
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Shadcn/UI |
| **Backend** | FastAPI, Python 3.13, async/await throughout |
| **Database** | PostgreSQL (via SQLAlchemy async + asyncpg) |
| **Vector Store** | Qdrant (1024-dim COSINE, collection: `ilm-atlas-v1`) |
| **Embeddings** | BAAI/bge-m3 (local — ONNX+DirectML on GPU, PyTorch CPU fallback) |
| **LLM** | Qwen 2.5 via OpenRouter API |
| **OCR** | Surya (for scanned PDFs and images) |
| **Streaming** | Server-Sent Events (SSE) with token-level delivery |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for PostgreSQL + Qdrant)
- An [OpenRouter](https://openrouter.ai/) API key

### 1. Clone and configure

```bash
git clone https://github.com/OLodhi/ilm-atlas.git
cd ilm-atlas
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://ilmatlas:ilmatlas@localhost:5432/ilmatlas
QDRANT_URL=http://localhost:6333
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=qwen/qwen3-max
EMBEDDING_MODEL=BAAI/bge-m3
UPLOAD_DIR=./uploads
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts PostgreSQL (port 5432) and Qdrant (port 6333).

### 3. Set up the backend

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head          # Run database migrations
uvicorn app.main:app --reload # Start the API server
```

The API is now at `http://localhost:8000`. Check `http://localhost:8000/docs` for the interactive API documentation.

### 4. Ingest data

From the project root:

```bash
python scripts/ingest_quran.py     # ~6,236 ayahs
python scripts/ingest_hadith.py    # ~34k hadiths (run from backend/ dir)
python scripts/ingest_tafsir.py    # ~36k tafsir chunks
```

> Hadith ingestion requires a [HadithAPI](https://hadithapi.com/) key set as `HADITH_API_KEY` in your `.env`.

### 5. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` and start asking questions.

---

## API Endpoints

### Chat (Multi-turn)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat/sessions` | Create a new chat session |
| `GET` | `/chat/sessions` | List all sessions |
| `GET` | `/chat/sessions/{id}` | Get session with message history |
| `POST` | `/chat/sessions/{id}/messages` | Send message (returns full response) |
| `POST` | `/chat/sessions/{id}/messages/stream` | Send message (SSE streaming response) |
| `PATCH` | `/chat/sessions/{id}` | Rename session |
| `DELETE` | `/chat/sessions/{id}` | Delete session |

### Research (One-shot)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/query` | One-shot RAG query with citations |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/admin/upload` | Upload a source file (PDF, image, text) |
| `GET` | `/admin/sources` | List uploaded sources and ingestion status |
| `GET` | `/admin/books` | List all books in the knowledge base |

---

## Project Structure

```
backend/
  app/
    routers/          API endpoints (chat, query, admin)
    services/         Core logic (RAG, embedding, LLM, search, OCR, ingestion)
    models/           SQLAlchemy ORM models + Pydantic schemas
    prompts/          LLM system prompts (adab, query rewrite, expansion, translation)
  alembic/            Database migrations

frontend/
  src/
    app/              Next.js pages (home, chat, admin)
    components/       UI components (chat, research, admin, shared)
    hooks/            React hooks (useChat, useChatSessions, useQueryResearch)
    lib/              API client, types, constants

scripts/              Data ingestion (Quran, Hadith, Tafsir)
```

---

## License

This project is for educational and research purposes. The Islamic source texts are publicly available from their respective APIs ([alquran.cloud](https://alquran.cloud/), [api.quran.com](https://api.quran.com/), [hadithapi.com](https://hadithapi.com/)).
