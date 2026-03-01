# Ilm Atlas Deployment — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy Ilm Atlas to a Hetzner VPS with Docker Compose, migrate embeddings from local bge-m3 to Voyage AI cloud API, and set up GitHub Actions CI/CD.

**Architecture:** Single VPS (Hetzner CX22, 4GB RAM) running five Docker containers — Caddy (reverse proxy + auto-SSL), Next.js frontend, FastAPI backend, PostgreSQL, and Qdrant. Voyage AI replaces local bge-m3 for query embeddings. GitHub Actions builds Docker images and deploys via SSH.

**Tech Stack:** Docker, Caddy, Voyage AI API, GitHub Actions, ghcr.io

**Design doc:** `docs/plans/2026-03-01-deployment-design.md`

---

## Phase 1: Embedding Migration

### Task 1: Add Voyage AI config fields

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Add new settings to the `Settings` class**

In `backend/app/config.py`, add these fields after the existing `embedding_model` field:

```python
    # Embedding provider ("local" for bge-m3, "voyageai" for Voyage AI API)
    embedding_provider: str = "local"
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3-large"
```

**Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add Voyage AI config fields for embedding provider switch"
```

---

### Task 2: Implement Voyage AI embedding provider

**Files:**
- Modify: `backend/app/services/embedding.py`
- Modify: `backend/requirements.txt`

**Step 1: Add `voyageai` to requirements.txt**

Add after the `# Embedding (bge-m3)` section:

```
# Embedding (Voyage AI cloud)
voyageai>=0.3.2
```

**Step 2: Install the new dependency**

Run: `cd backend && pip install voyageai`

**Step 3: Modify `embedding.py` to support both providers**

Replace the entire `embed_texts` function and add a Voyage AI path. The key changes:

1. `embed_texts()` checks `settings.embedding_provider`
2. If `"voyageai"` → call Voyage AI API (async-compatible via `asyncio.to_thread` since the SDK's sync client is simpler)
3. If `"local"` → existing bge-m3 code (unchanged)

Add at the top of the file, after the existing imports:

```python
from app.config import settings
```

(This import already exists — no change needed.)

Add a new `_voyage_client` global and loader after the existing `_model` global:

```python
_voyage_client = None


def _get_voyage_client():
    global _voyage_client
    if _voyage_client is None:
        import voyageai
        _voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
        logger.info("Voyage AI client initialized (model: %s)", settings.voyage_model)
    return _voyage_client
```

Replace the existing `embed_texts` function:

```python
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Routes to Voyage AI (cloud) or bge-m3 (local) based on config.
    Returns a list of float vectors (1024-dim).
    """
    if settings.embedding_provider == "voyageai":
        return _embed_voyage(texts)

    # Local bge-m3 path (existing behavior)
    model_info = _load_model()

    if model_info[0] == "onnx":
        return _embed_onnx(texts, model_info[1], model_info[2])
    else:
        model = model_info[1]
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()
```

Add the Voyage AI embedding function after `_embed_onnx`:

```python
def _embed_voyage(texts: list[str]) -> list[list[float]]:
    """Embed texts using Voyage AI API.

    Handles batching internally — Voyage AI accepts up to 128 texts per call.
    """
    client = _get_voyage_client()
    all_embeddings: list[list[float]] = []
    batch_size = 128

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = client.embed(texts=batch, model=settings.voyage_model)
        all_embeddings.extend(result.embeddings)

    return all_embeddings
```

**Step 4: Commit**

```bash
git add backend/app/services/embedding.py backend/requirements.txt
git commit -m "feat: add Voyage AI embedding provider with config-based routing"
```

---

### Task 3: Test Voyage AI embedding integration

**Files:**
- Create: `backend/tests/test_embedding.py`

**Step 1: Write the test**

```python
from unittest.mock import MagicMock, patch


def test_embed_texts_routes_to_voyage_when_configured():
    """Verify embed_texts calls Voyage AI when provider is set."""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1] * 1024, [0.2] * 1024]

    mock_client = MagicMock()
    mock_client.embed.return_value = mock_result

    with patch("app.services.embedding.settings") as mock_settings, \
         patch("app.services.embedding._get_voyage_client", return_value=mock_client):
        mock_settings.embedding_provider = "voyageai"
        mock_settings.voyage_model = "voyage-3-large"

        from app.services.embedding import embed_texts
        result = embed_texts(["hello", "world"])

    assert len(result) == 2
    assert len(result[0]) == 1024
    mock_client.embed.assert_called_once_with(
        texts=["hello", "world"], model="voyage-3-large"
    )


def test_embed_texts_batches_large_inputs():
    """Verify Voyage AI path batches inputs of >128 texts."""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1] * 1024]

    mock_client = MagicMock()
    mock_client.embed.return_value = mock_result

    with patch("app.services.embedding.settings") as mock_settings, \
         patch("app.services.embedding._get_voyage_client", return_value=mock_client):
        mock_settings.embedding_provider = "voyageai"
        mock_settings.voyage_model = "voyage-3-large"

        from app.services.embedding import embed_texts
        # 200 texts should result in 2 API calls (128 + 72)
        texts = [f"text {i}" for i in range(200)]
        mock_result.embeddings = [[0.1] * 1024] * 128
        embed_texts(texts)

    assert mock_client.embed.call_count == 2
```

**Step 2: Run the tests**

Run: `cd backend && python -m pytest tests/test_embedding.py -v`

Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_embedding.py
git commit -m "test: add Voyage AI embedding provider tests"
```

---

### Task 4: Write re-indexing script

**Files:**
- Create: `scripts/reindex_embeddings.py`

This script scrolls all points from Qdrant, reconstructs embeddable text from payloads, re-embeds via Voyage AI, and upserts back with new vectors (same IDs + payloads).

**Step 1: Create the script**

```python
"""Re-index all Qdrant vectors using Voyage AI embeddings.

Scrolls through every point in the ilm-atlas-v1 collection, re-embeds the
text content via Voyage AI, and upserts the updated vectors back (preserving
point IDs and payloads).

Usage:
    Set EMBEDDING_PROVIDER=voyageai and VOYAGE_API_KEY in backend/.env
    Run: cd backend && python ../scripts/reindex_embeddings.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
logger = logging.getLogger(__name__)

from app.config import settings
from app.services.embedding import embed_texts
from app.services.vector_store import get_client, COLLECTION_NAME

# Windows asyncio compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_embeddable_text(payload: dict) -> str:
    """Reconstruct the text that should be embedded from a Qdrant payload."""
    parts = []
    if payload.get("text_arabic"):
        parts.append(payload["text_arabic"])
    if payload.get("text_english"):
        parts.append(payload["text_english"])
    return " ".join(parts) if parts else ""


async def reindex():
    if settings.embedding_provider != "voyageai":
        logger.error("EMBEDDING_PROVIDER must be 'voyageai'. Current: %s", settings.embedding_provider)
        sys.exit(1)

    client = get_client()

    # Get collection info
    info = await client.get_collection(COLLECTION_NAME)
    total_points = info.points_count
    logger.info("Collection %s has %d points to re-index", COLLECTION_NAME, total_points)

    processed = 0
    skipped = 0
    batch_size = 64  # Voyage AI batch + Qdrant scroll batch
    offset = None

    while True:
        # Scroll through points
        points, next_offset = await client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            break

        # Extract texts
        ids = []
        texts = []
        payloads = []
        for point in points:
            text = get_embeddable_text(point.payload or {})
            if not text.strip():
                skipped += 1
                continue
            ids.append(point.id)
            texts.append(text)
            payloads.append(point.payload)

        if texts:
            # Re-embed via Voyage AI
            vectors = embed_texts(texts)

            # Upsert back with same IDs and payloads
            from qdrant_client.models import PointStruct
            upsert_points = [
                PointStruct(id=pid, vector=vec, payload=pay)
                for pid, vec, pay in zip(ids, vectors, payloads)
            ]

            await client.upsert(collection_name=COLLECTION_NAME, points=upsert_points)
            processed += len(texts)

        logger.info("Progress: %d / %d processed (%d skipped)", processed, total_points, skipped)

        if next_offset is None:
            break
        offset = next_offset

    logger.info("Re-indexing complete. %d points updated, %d skipped.", processed, skipped)


if __name__ == "__main__":
    asyncio.run(reindex())
```

**Step 2: Run the re-indexing**

Before running, set in `backend/.env`:
```
EMBEDDING_PROVIDER=voyageai
VOYAGE_API_KEY=<your-voyage-api-key>
```

Run: `cd backend && python ../scripts/reindex_embeddings.py`

Expected: Processes ~76,000 points in batches of 64. Takes ~15-20 minutes (API rate limits).

**Step 3: Verify by running a test query**

Run: `cd backend && uvicorn app.main:app --reload`
Then test a query through the frontend or curl to confirm results look correct.

**Step 4: Commit**

```bash
git add scripts/reindex_embeddings.py
git commit -m "feat: add Voyage AI re-indexing script for embedding migration"
```

---

### Task 5: Split requirements into prod and dev

**Files:**
- Modify: `backend/requirements.txt` (production — remove ML packages)
- Create: `backend/requirements-dev.txt` (local dev — adds ML packages)

**Step 1: Create `requirements-dev.txt`**

```
# Local development extras (GPU/CPU embedding, OCR)
-r requirements.txt

# Embedding (bge-m3 local)
sentence-transformers>=4.0

# OCR (surya brings pillow + pypdfium2)
surya-ocr>=0.17.1

# PDF extraction
pdfplumber>=0.11.4

# Testing
pytest>=8.0
```

**Step 2: Remove ML-only packages from `requirements.txt`**

Remove these lines from `requirements.txt`:
```
# Embedding (bge-m3)
sentence-transformers>=4.0

# OCR (surya brings pillow + pypdfium2)
surya-ocr>=0.17.1

# PDF extraction
pdfplumber>=0.11.4
```

The production `requirements.txt` keeps: FastAPI, SQLAlchemy, Qdrant client, httpx, auth packages, Resend, voyageai, etc.

**Step 3: Commit**

```bash
git add backend/requirements.txt backend/requirements-dev.txt
git commit -m "refactor: split requirements into prod and dev (remove ML deps from prod)"
```

---

## Phase 2: Dockerization

### Task 6: Backend Dockerfile

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/entrypoint.sh`
- Create: `backend/.dockerignore`

**Step 1: Create `backend/.dockerignore`**

```
__pycache__
*.pyc
.env
.env.*
uploads/
tests/
.pytest_cache/
*.egg-info/
.venv/
```

**Step 2: Create `backend/entrypoint.sh`**

```bash
#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

**Step 3: Create `backend/Dockerfile`**

```dockerfile
# --- Builder stage ---
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# --- Runtime stage ---
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
```

**Step 4: Test the build locally**

Run: `cd backend && docker build -t ilmatlas-backend .`

Expected: Builds successfully. Image size ~300MB (vs ~2GB+ with ML packages).

**Step 5: Commit**

```bash
git add backend/Dockerfile backend/entrypoint.sh backend/.dockerignore
git commit -m "feat: add backend Dockerfile with multi-stage build"
```

---

### Task 7: Frontend Dockerfile

**Files:**
- Modify: `frontend/next.config.mjs`
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`

**Step 1: Enable standalone output in `next.config.mjs`**

Replace contents of `frontend/next.config.mjs`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
};

export default nextConfig;
```

**Step 2: Create `frontend/.dockerignore`**

```
node_modules
.next
.env.local
```

**Step 3: Create `frontend/Dockerfile`**

```dockerfile
# --- Dependencies stage ---
FROM node:20-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- Build stage ---
FROM node:20-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time env var (overridden at runtime via docker-compose)
ARG NEXT_PUBLIC_API_URL=https://api.ilmatlas.com
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# --- Runtime stage ---
FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=production

# Copy standalone output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
```

**Step 4: Test the build locally**

Run: `cd frontend && docker build -t ilmatlas-frontend .`

Expected: Builds successfully. Image size ~150MB.

**Step 5: Commit**

```bash
git add frontend/next.config.mjs frontend/Dockerfile frontend/.dockerignore
git commit -m "feat: add frontend Dockerfile with standalone Next.js build"
```

---

### Task 8: Caddyfile

**Files:**
- Create: `Caddyfile` (project root)

**Step 1: Create the Caddyfile**

```
ilmatlas.com {
    reverse_proxy frontend:3000
}

api.ilmatlas.com {
    reverse_proxy backend:8000
}
```

That's it. Caddy automatically provisions and renews TLS certificates via Let's Encrypt. No extra configuration needed.

**Step 2: Commit**

```bash
git add Caddyfile
git commit -m "feat: add Caddyfile for reverse proxy with auto-SSL"
```

---

### Task 9: Production docker-compose.yml

**Files:**
- Rename: `docker-compose.yml` → `docker-compose.dev.yml` (existing dev config)
- Create: `docker-compose.yml` (production config)

**Step 1: Rename existing dev compose file**

Run: `git mv docker-compose.yml docker-compose.dev.yml`

**Step 2: Create production `docker-compose.yml`**

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"  # HTTP/3
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - frontend
      - backend
    networks:
      - ilmatlas

  frontend:
    image: ghcr.io/${GHCR_OWNER:-ilmatlas}/frontend:latest
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-https://api.ilmatlas.com}
    restart: unless-stopped
    expose:
      - "3000"
    networks:
      - ilmatlas

  backend:
    image: ghcr.io/${GHCR_OWNER:-ilmatlas}/backend:latest
    build:
      context: ./backend
    restart: unless-stopped
    expose:
      - "8000"
    env_file:
      - .env
    volumes:
      - uploads:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    networks:
      - ilmatlas

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-ilmatlas}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
      POSTGRES_DB: ${POSTGRES_DB:-ilmatlas}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-ilmatlas}"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - ilmatlas

  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:6333/healthz"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - ilmatlas

volumes:
  caddy_data:
  caddy_config:
  postgres_data:
  qdrant_data:
  uploads:

networks:
  ilmatlas:
```

Key differences from dev:
- No ports published for postgres/qdrant (Docker-internal only)
- Caddy fronts everything on 80/443
- Backend reads from `.env` file
- Healthchecks with dependency ordering
- ghcr.io image references for CI/CD pull-based deploys
- `build:` directives for local `docker compose build` fallback

**Step 3: Commit**

```bash
git add docker-compose.yml docker-compose.dev.yml
git commit -m "feat: add production docker-compose with Caddy, healthchecks, and security"
```

---

### Task 10: Production .env template

**Files:**
- Create: `.env.production.template`

**Step 1: Create the template**

```bash
# ── Database ──────────────────────────────────────────────
POSTGRES_USER=ilmatlas
POSTGRES_PASSWORD=          # Generate: openssl rand -base64 32
POSTGRES_DB=ilmatlas
DATABASE_URL=postgresql+asyncpg://ilmatlas:${POSTGRES_PASSWORD}@postgres:5432/ilmatlas

# ── Qdrant ────────────────────────────────────────────────
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=             # Optional for internal Docker network

# ── Embedding (Voyage AI) ────────────────────────────────
EMBEDDING_PROVIDER=voyageai
VOYAGE_API_KEY=             # From dashboard.voyageai.com
VOYAGE_MODEL=voyage-3-large

# ── LLM (OpenRouter) ─────────────────────────────────────
OPENROUTER_API_KEY=         # From openrouter.ai/keys

# ── Auth ──────────────────────────────────────────────────
JWT_SECRET_KEY=             # Generate: openssl rand -hex 32
FRONTEND_URL=https://ilmatlas.com

# ── Email (Resend) ───────────────────────────────────────
RESEND_API_KEY=             # From resend.com/api-keys
EMAIL_FROM=noreply@ilmatlas.com

# ── Docker image owner (for ghcr.io) ─────────────────────
GHCR_OWNER=                 # Your GitHub username or org
```

**Step 2: Ensure `.env` is gitignored**

Check that `.gitignore` contains `.env` (it should already). If not, add it.

**Step 3: Commit**

```bash
git add .env.production.template
git commit -m "docs: add production .env template with all required secrets"
```

---

### Task 11: Test full stack locally with Docker Compose

**No files to create** — this is a verification step.

**Step 1: Create a local `.env` from the template**

Copy `.env.production.template` to `.env` and fill in your real API keys. Set:
```bash
DATABASE_URL=postgresql+asyncpg://ilmatlas:localdev@postgres:5432/ilmatlas
POSTGRES_PASSWORD=localdev
QDRANT_URL=http://qdrant:6333
FRONTEND_URL=http://localhost:3000
```

**Step 2: Build and start all services**

Run: `docker compose build && docker compose up`

Expected: All 5 services start. Caddy will fail SSL (no real domain locally) — that's expected. Verify:
- `curl http://localhost:8000/health` → `{"status":"ok","version":"0.1.0"}`
- Frontend accessible at `http://localhost:3000` (via Caddy port or direct)

**Step 3: Tear down**

Run: `docker compose down`

If everything works, no commit needed (no file changes).

---

## Phase 3: CI/CD

### Task 12: GitHub Actions deploy workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

**Step 1: Create the workflow**

```yaml
name: Build & Deploy

on:
  push:
    branches: [master]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Lint backend
        run: |
          pip install ruff
          ruff check backend/

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Lint frontend
        run: |
          cd frontend
          npm ci
          npm run lint
          npx tsc --noEmit

  build-and-push:
    needs: lint
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    strategy:
      matrix:
        service: [backend, frontend]
    steps:
      - uses: actions/checkout@v4

      - name: Log in to ghcr.io
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: ./${{ matrix.service }}
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ github.repository_owner }}/${{ matrix.service }}:latest
            ${{ env.REGISTRY }}/${{ github.repository_owner }}/${{ matrix.service }}:${{ github.sha }}
          build-args: |
            NEXT_PUBLIC_API_URL=${{ matrix.service == 'frontend' && 'https://api.ilmatlas.com' || '' }}

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: deploy
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/ilmatlas
            docker compose pull backend frontend
            docker compose up -d --no-build
            docker image prune -f
```

**Step 2: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/deploy.yml
git commit -m "feat: add GitHub Actions CI/CD pipeline for build and deploy"
```

---

## Phase 4: VPS Setup

### Task 13: Server provisioning checklist

**Files:**
- Create: `docs/server-setup.md`

This documents the one-time manual VPS setup steps. Not automated — these run once when provisioning.

**Step 1: Create the guide**

```markdown
# Ilm Atlas — Server Setup

One-time setup for a fresh Hetzner CX22 VPS (Ubuntu 24.04).

## 1. Initial server hardening

```bash
# SSH in as root
ssh root@<VPS_IP>

# Create deploy user
adduser deploy
usermod -aG sudo deploy

# Set up SSH key auth for deploy user
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh

# Disable password auth
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# Firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

## 2. Install Docker

```bash
# As deploy user
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
# Log out and back in for group change
```

## 3. Deploy the application

```bash
cd /opt
sudo mkdir ilmatlas && sudo chown deploy:deploy ilmatlas
cd ilmatlas

# Clone repo
git clone https://github.com/<your-username>/ilm-atlas.git .

# Create .env from template
cp .env.production.template .env
nano .env  # Fill in all secrets

# Start services
docker compose up -d
```

## 4. DNS

Point these records to the VPS IP:

| Record | Type | Value |
|--------|------|-------|
| ilmatlas.com | A | <VPS_IP> |
| api.ilmatlas.com | A | <VPS_IP> |

Wait for DNS propagation (~5-30 minutes), then Caddy auto-provisions SSL.

## 5. Email DNS (Resend)

Add the DNS records from Resend dashboard for `ilmatlas.com`:
- SPF (TXT record)
- DKIM (CNAME records)
- Return-Path (CNAME record)

## 6. Create admin user

```bash
cd /opt/ilmatlas
docker compose exec backend python -c "
import asyncio
from app.database import async_session
from app.models.db import User
from passlib.hash import bcrypt

async def create():
    async with async_session() as s:
        user = User(
            email='admin@ilmatlas.com',
            password_hash=bcrypt.hash('CHANGE_THIS_PASSWORD'),
            role='admin',
            email_verified=True,
        )
        s.add(user)
        await s.commit()
        print(f'Admin created: {user.id}')

asyncio.run(create())
"
```

## 7. Migrate Qdrant data

Option A — Re-run ingestion scripts on the server:
```bash
docker compose exec backend python ../scripts/ingest_quran.py
# etc.
```

Option B — Snapshot from local Qdrant and restore:
```bash
# On local machine: create snapshot
curl -X POST http://localhost:6333/collections/ilm-atlas-v1/snapshots

# Download snapshot, upload to VPS, restore
# See: https://qdrant.tech/documentation/concepts/snapshots/
```
```

**Step 2: Commit**

```bash
git add docs/server-setup.md
git commit -m "docs: add VPS provisioning and setup guide"
```

---

### Task 14: Backup and monitoring scripts

**Files:**
- Create: `scripts/backup-db.sh`
- Create: `scripts/healthcheck.sh`

**Step 1: Create `scripts/backup-db.sh`**

```bash
#!/bin/bash
# Daily PostgreSQL backup — run via cron
# Crontab: 0 3 * * * /opt/ilmatlas/scripts/backup-db.sh

BACKUP_DIR="/opt/ilmatlas/backups"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

docker compose -f /opt/ilmatlas/docker-compose.yml exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-ilmatlas}" "${POSTGRES_DB:-ilmatlas}" \
    | gzip > "$BACKUP_DIR/ilmatlas_$TIMESTAMP.sql.gz"

# Prune old backups
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$KEEP_DAYS -delete

echo "Backup complete: ilmatlas_$TIMESTAMP.sql.gz"
```

**Step 2: Create `scripts/healthcheck.sh`**

```bash
#!/bin/bash
# Health check — run via cron every 5 minutes
# Crontab: */5 * * * * /opt/ilmatlas/scripts/healthcheck.sh

API_URL="http://localhost:8000/health"

status=$(curl -sf -o /dev/null -w "%{http_code}" "$API_URL" 2>/dev/null)

if [ "$status" != "200" ]; then
    echo "[$(date)] Health check FAILED (status: $status). Restarting..." >> /opt/ilmatlas/logs/healthcheck.log
    docker compose -f /opt/ilmatlas/docker-compose.yml restart backend
else
    echo "[$(date)] OK" >> /opt/ilmatlas/logs/healthcheck.log
fi
```

**Step 3: Commit**

```bash
git add scripts/backup-db.sh scripts/healthcheck.sh
git commit -m "feat: add backup and health check scripts for production"
```

---

## Summary of all files

| Action | File | Phase |
|--------|------|-------|
| Modify | `backend/app/config.py` | 1 |
| Modify | `backend/app/services/embedding.py` | 1 |
| Modify | `backend/requirements.txt` | 1 |
| Create | `backend/requirements-dev.txt` | 1 |
| Create | `backend/tests/test_embedding.py` | 1 |
| Create | `scripts/reindex_embeddings.py` | 1 |
| Create | `backend/Dockerfile` | 2 |
| Create | `backend/entrypoint.sh` | 2 |
| Create | `backend/.dockerignore` | 2 |
| Modify | `frontend/next.config.mjs` | 2 |
| Create | `frontend/Dockerfile` | 2 |
| Create | `frontend/.dockerignore` | 2 |
| Create | `Caddyfile` | 2 |
| Rename | `docker-compose.yml` → `docker-compose.dev.yml` | 2 |
| Create | `docker-compose.yml` (production) | 2 |
| Create | `.env.production.template` | 2 |
| Create | `.github/workflows/deploy.yml` | 3 |
| Create | `docs/server-setup.md` | 3 |
| Create | `scripts/backup-db.sh` | 4 |
| Create | `scripts/healthcheck.sh` | 4 |
