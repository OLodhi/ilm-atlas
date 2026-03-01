# Ilm Atlas — Production Deployment Design

**Date**: 2026-03-01
**Status**: Approved

## Summary

Deploy Ilm Atlas to a single Hetzner VPS running all services in Docker Compose, with Caddy for automatic HTTPS, Voyage AI for cloud embeddings, and GitHub Actions for CI/CD.

## Constraints

- Budget: ~$5/month (Hetzner CX22)
- Scale: Small community (100-1000 users)
- Domain: ilmatlas.com (owned)
- Sole developer, no ops team

## Architecture

```
Internet → Caddy (:443) → ilmatlas.com     → Next.js (:3000)
                         → api.ilmatlas.com → FastAPI (:8000)

Docker Compose (Hetzner CX22 — 2 vCPU, 4GB RAM, 40GB SSD, ~€3.29/mo):
  ├── caddy       (reverse proxy + auto-SSL via Let's Encrypt)
  ├── frontend    (Next.js 14 standalone build)
  ├── backend     (FastAPI + uvicorn)
  ├── postgres    (PostgreSQL 16)
  └── qdrant      (Qdrant latest)
```

### RAM Budget (~1.3GB of 4GB available)

| Service | Estimated RAM |
|---------|---------------|
| PostgreSQL | ~150MB |
| Qdrant (76k vectors) | ~400MB |
| FastAPI + uvicorn (2 workers) | ~300MB |
| Next.js (standalone) | ~200MB |
| Caddy | ~30MB |
| OS overhead | ~200MB |

## Dockerization

### Backend Dockerfile (multi-stage)

1. **Builder**: `python:3.12-slim`, install deps into venv
2. **Runtime**: Copy venv + app code, no build tools
3. Entrypoint: run Alembic migrations, then start uvicorn
4. No embedding model baked in (using Voyage AI API)

### Frontend Dockerfile (multi-stage)

1. **Deps**: `node:20-alpine`, `npm ci`
2. **Build**: `npm run build` with `output: 'standalone'` in next.config
3. **Runtime**: Copy standalone output only (~30MB vs ~500MB node_modules)

### Production docker-compose.yml

- All services on shared `ilmatlas` network
- Caddy: only service with published ports (80, 443)
- Persistent volumes: postgres_data, qdrant_data, caddy_data, uploads
- `.env` file for secrets (never committed)
- Backend depends_on postgres + qdrant with healthchecks
- Restart policy: `unless-stopped`

## Embedding Migration

**From**: BAAI/bge-m3 (local ONNX+DirectML, 1024-dim)
**To**: Voyage AI `voyage-3-large` (cloud API, 1024-dim native)

### Why Voyage AI

- Native 1024-dim output (no dimension reduction needed)
- Excellent Arabic/multilingual performance
- Cheaper than OpenAI (~$0.06 per 1M tokens)
- Generous free tier (200M tokens — covers full re-indexing)

### Migration Strategy

1. Add Voyage AI embedding service alongside existing bge-m3
2. Write re-indexing script:
   - Read all chunks from PostgreSQL
   - Embed in batches via Voyage AI API
   - Upsert new vectors to Qdrant (overwriting bge-m3 embeddings)
3. Switch backend config to Voyage AI embedder
4. Remove bge-m3/sentence-transformers/ONNX from requirements.txt
5. Keep bge-m3 code behind config flag for local dev fallback

### Cost

- Re-indexing 76k chunks: free (within Voyage AI free tier)
- Runtime (~100 queries/day): negligible

## CI/CD — GitHub Actions

**Trigger**: Push to `master`

### Pipeline

1. **Lint & type-check**: `ruff check` (backend), `npm run lint` + `tsc --noEmit` (frontend)
2. **Build Docker images**: Multi-stage builds on GitHub Actions runner
3. **Push to ghcr.io**: GitHub Container Registry (free, private images)
4. **Deploy via SSH**: Pull images + `docker compose up -d` on VPS

### GitHub Secrets

- `VPS_HOST` — VPS IP address
- `VPS_SSH_KEY` — SSH private key for deployment
- Production app secrets stay in `.env` on VPS (not in GitHub)

### Why build on GitHub, not on VPS

- GitHub runners are faster than a 2-vCPU VPS
- VPS just pulls pre-built images — deployment takes seconds
- No build tools needed on production server

## DNS Configuration

| Record | Type | Value |
|--------|------|-------|
| ilmatlas.com | A | `<VPS_IP>` |
| api.ilmatlas.com | A | `<VPS_IP>` |

Caddy handles routing based on hostname.

## Production Hardening

1. **Secrets**: Strong `JWT_SECRET_KEY` (64 chars), unique DB password, production API keys
2. **CORS**: `FRONTEND_URL=https://ilmatlas.com`
3. **Cookies**: `secure=True`, `samesite=strict` (already conditional in code)
4. **Rate limiting**: 10/min per endpoint, 50 queries/day per user (existing config)
5. **Firewall**: UFW — allow 22 (SSH), 80, 443 only. All other ports Docker-internal
6. **Email DNS**: SPF + DKIM records for `ilmatlas.com` (Resend deliverability)
7. **Monitoring**: Health check cron script, basic alerting

## Backups

- **PostgreSQL**: Daily `pg_dump` via cron (stored on VPS)
- **Qdrant**: Reconstructible from PostgreSQL chunks (Postgres is source of truth)
- **Optional**: Hetzner backup snapshots (+20% of VPS cost, ~€0.66/mo)

## Cost Summary

| Item | Monthly Cost |
|------|-------------|
| Hetzner CX22 | ~€3.29 ($3.50) |
| Voyage AI embeddings | ~$0 (free tier) |
| OpenRouter LLM | Existing spend |
| Resend email | $0 (100/day free) |
| Domain renewal | ~$1/mo amortized |
| **Total** | **~$5/mo** |
