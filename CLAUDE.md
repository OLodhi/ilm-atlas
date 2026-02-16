# Ilm Atlas

## Vision

LLM-powered encyclopaedic guide to Sunni Islam (Ahle-us-Sunnat). Provides accurate, source-backed knowledge grounded in the Quran, Sunnah, and consensus of the Sahaba and Tabi'un.

## Core Principles

### Source-First (No Hallucination)
- Every answer must be grounded in retrieved text via RAG
- Every answer must cite with Volume/Page/Surah/Ayah numbers
- The AI never invents or infers religious rulings

### Adab (Etiquette) Layer
- Respectful honorifics: SAW (Prophet), RA (Sahaba), RH (scholars)
- Never issues personal Fatwas
- Handles Ikhtilaf (scholarly differences) by presenting mainstream Sunni consensus
- This is enforced via the LLM system prompt

## Architecture

Modular monorepo with three layers:

```
ilm-atlas/
  frontend/    # Next.js 14 + Tailwind CSS + Shadcn/UI
  backend/     # Python FastAPI (orchestration layer)
  scripts/     # Data ingestion & pipeline scripts
```

### Frontend (Next.js 14)
- **UI Concept:** "The Research Bench" — split-view layout
  - Central query bar
  - Side panel showing actual source text (Arabic/English) alongside AI summary
- Tailwind CSS + Shadcn/UI for components
- Arabic typography: Amiri / Scheherazade fonts with full RTL support

### Backend (Python FastAPI)
- Orchestrates: Frontend <-> Qdrant <-> LLM
- Receives user query, embeds it, searches Qdrant, passes results to LLM, returns cited answer
- Must use Pydantic for validation, async for all I/O

### Vector Database (Qdrant Cloud)
- Stores chunked Quran and Hadith texts with rich metadata
- First collection: `quran-v1`

### LLM (Qwen 2.5 via OpenRouter)
- 72B or 32B parameter model
- Chosen for superior Arabic language handling

## Phase 1: Quran RAG Pipeline

This is the current focus. Steps:

1. **Data Ingestion** — Fetch Quran (Uthmani Script + English translation) from Tanzil.net or Quran.com API
2. **Chunking** — One chunk per Ayah, each containing:
   - Arabic text (Uthmani script)
   - English translation
   - Metadata: Surah name, Surah number, Ayah number
3. **Vectorization** — Embed chunks with a multilingual model (e.g. `text-embedding-3-small` or HuggingFace multilingual), upload to Qdrant collection `quran-v1`
4. **Query Endpoint** — FastAPI endpoint that:
   - Receives user query
   - Embeds the query
   - Searches Qdrant for top 5 relevant Ayahs
   - Passes Ayahs + query to Qwen 2.5 with the Adab system prompt
   - Returns answer + specific citations
5. **Frontend** — Basic Research Bench UI to query and display results

## Code Standards

- Python: async everywhere, Pydantic models for all request/response shapes
- Frontend: TypeScript strict mode, server components by default
- All secrets (API keys for OpenRouter, Qdrant) go in `.env` files (never committed)
- Production-ready code from the start — no throwaway prototypes

## Commands

- Backend: `cd backend && uvicorn main:app --reload`
- Frontend: `cd frontend && npm run dev`

## Project Constraints

- When restarting the server, do not set a timeout for it.
