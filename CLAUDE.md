# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make up           # start all 6 Docker services (postgres, redis, qdrant, api, worker, web)
make down         # stop all services
make migrate      # run alembic migrations (creates all 7 tables)
make seed         # ingest synthetic seed corpus into Qdrant + PostgreSQL
make eval         # run eval harness: raw baseline then cleaned pipeline, prints comparison table
make test         # pytest tests/ (unit tests — no Docker needed for scoring tests)
make lint         # ruff check + ruff format --check on apps/api/
make format       # ruff auto-fix on apps/api/
make logs         # docker compose logs -f
make shell-api    # bash into API container
make shell-db     # psql into PostgreSQL
```

### Running a single test
```bash
cd apps/api && python -m pytest ../../tests/test_scoring.py -v
```

### Running the eval harness locally (not in Docker)
```bash
cd apps/api && python -m pipelines.eval.harness --mode both --output results.json
```

## Architecture

**6 Docker services**: postgres:16, redis:7, qdrant, FastAPI API (port 8000), Celery worker (same image as API), Next.js web (port 3000).

**API and Worker share one Docker image** (`apps/api/Dockerfile`). The worker runs `celery -A app.celery_app worker` instead of uvicorn. No code is duplicated.

**Ingestion flow**: `POST /api/v1/documents` → DB record → Celery `ingest_document_task` → connector (PDF/Markdown) → chunk → OpenAI embed → Qdrant upsert + Chunk DB record → `score_document_chunks_task` → conflict detection.

**Pipelines** (`pipelines/`) are Python packages mounted into both the API and worker containers via Docker volume. They import from `app.*` (which is on PYTHONPATH).

**Eval harness** (`pipelines/eval/harness.py`) is the most important component — it proves value by comparing raw vs. cleaned retrieval across 30 Q&A pairs using Claude as the judge.

## Key Files

| Path | Purpose |
|------|---------|
| `apps/api/app/models/` | 7 SQLAlchemy 2.0 models (Document, Chunk, Entity, EntityRelationship, Conflict, LineageRecord, AgentMemory) |
| `apps/api/app/main.py` | FastAPI app, CORS, Qdrant collection creation on startup |
| `apps/api/app/config.py` | `Settings` (pydantic-settings) — all env vars |
| `apps/api/app/tasks/ingestion.py` | `ingest_document_task`, `score_document_chunks_task` |
| `pipelines/ingestion/base.py` | `BaseConnector` + `_split_text` (512 tok, 50 overlap) |
| `pipelines/scoring/freshness.py` | `FreshnessScorer` — age-based decay, per-source-type decay days |
| `pipelines/scoring/trust.py` | `TrustScorer` — source-type base scores |
| `pipelines/scoring/conflict.py` | `ConflictDetector` — cosine sim ≥ 0.85 + Claude Haiku judge |
| `pipelines/eval/harness.py` | Eval CLI: embed → retrieve → generate → judge → print comparison |
| `data/seed_corpus/` | Synthetic docs: api_docs_v1 (stale) vs. api_docs_v2 (current) + Slack export |
| `data/eval_qa_pairs/qa_pairs.json` | 30 Q&A pairs; 10 have `has_seeded_conflict: true` |
| `apps/web/src/app/` | Next.js pages: dashboard, documents, search, eval |

## Seeded Conflicts (for eval)

The seed corpus deliberately contains contradictions between `api_docs_v1.md` and `api_docs_v2.md`:
- Authentication: v1 says API keys, v2 says OAuth 2.0 JWT
- Rate limits: v1 says 50 req/min all tiers, v2 says 100–10,000 req/min by tier
- Data retention: v1 says 30 days, v2 says 7 years
- PDF support: v1 says not supported, v2 adds PDF
- SDKs: v1 says Python only, v2 has 4 official SDKs

The eval harness detects these via `has_seeded_conflict: true` in `qa_pairs.json`.

## Adding a New Source Connector

1. Create `pipelines/ingestion/myconnector.py` extending `BaseConnector`
2. Implement `ingest(source: str) -> list[RawChunk]`
3. Add the new `SourceType` value to `apps/api/app/models/document.py`
4. Handle the new type in `apps/api/app/tasks/ingestion.py`

## Environment Variables

Required in `.env` (copy from `.env.example`):
- `ANTHROPIC_API_KEY` — Claude (extraction, conflict detection, eval judge)
- `OPENAI_API_KEY` — embeddings (text-embedding-3-small)

Optional (have defaults for Docker Compose):
- `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`, `QDRANT_COLLECTION`
