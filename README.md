# Kortex

**Enterprise Knowledge Reliability, Memory & Agent Intelligence Platform**

An AI-native platform that continuously ingests, structures, validates, scores, and maintains organizational knowledge — providing a shared, reliable memory layer for both AI agents and human teams.

> Most enterprise AI failures are not caused by weak models — they're caused by poor knowledge.

## Quick Start

```bash
# 1. Create .env with your API keys — ANTHROPIC_API_KEY and OPENAI_API_KEY are
#    required (see "Environment Variables" in CLAUDE.md for the full list).

# 2. Start all services
make up

# 3. Run database migrations
make migrate

# 4. Load the synthetic seed corpus
make seed

# 5. Run the eval harness (the money shot)
make eval
```

Then open:
- **Dashboard**: http://localhost:3000
- **API docs**: http://localhost:8000/docs

## Eval Harness

The eval harness is the core proof-of-value. It runs 30 Q&A pairs against the seed corpus in two modes and compares results:

<!-- EVAL_TABLE_START -->
| Metric | Raw | Cleaned | Delta |
|--------|-----|---------|-------|
| Accuracy | — | — | run `make eval-report` |
| Faithfulness | — | — | |
| Hallucination Rate | — | — | |
<!-- EVAL_TABLE_END -->

> The table above is auto-populated. The `—` placeholders are filled in by a real
> run — see [Populating the table](#populating-the-table) below. No numbers are
> hardcoded.

The seed corpus contains deliberate conflicts (API docs v1 vs. v2 with contradictory authentication methods, rate limits, data retention policies, and SDK support). **Cleaned mode** filters out stale/conflicting chunks — the delta between raw and cleaned is the headline metric.

### Populating the table

The numbers above are generated on your machine (requires Docker + real API keys —
they are never hardcoded in this repo). One-time prerequisites:

```bash
# set REAL ANTHROPIC_API_KEY + OPENAI_API_KEY in .env (the single config file)
make up                       # start postgres, redis, qdrant, api, worker, web
make migrate                  # create the 7 tables
make seed                     # ingest the synthetic seed corpus
```

Then run a single command to evaluate and fill in the table:

```bash
make eval-report
```

This runs the harness in both modes, writes `results.json`, and rewrites the
metric table in this README between the `<!-- EVAL_TABLE_START -->` /
`<!-- EVAL_TABLE_END -->` markers. It is idempotent — re-run any time to refresh.

## Architecture

```
Sources (Markdown, PDF, Slack, ...)
    ↓ Ingestion (pipelines/ingestion/)
    ↓ Entity Extraction (Claude Haiku NER)
    ↓ Scoring (freshness + trust + conflict detection)
    ↓ Storage (PostgreSQL + Qdrant)
    ↓ Retrieval (semantic search with score filtering)
    ↓ Eval (30 Q&A × raw vs. cleaned × Claude judge)
```

See [docs/architecture.md](docs/architecture.md) for details.

## Phases

| Phase | Status | Outcome |
|-------|--------|---------|
| Phase 0: Foundation | ✅ Complete | Infra, models, API, CI |
| Phase 1: Verity Core | ✅ Complete | Ingestion → scoring → retrieval → eval |
| Phase 2: Knowledge Graph | 🔜 Next | Neo4j + graph viz + observability dashboard |
| Phase 3: Agent Memory | 🔜 Planned | Persistent multi-agent memory (LangGraph) |

## Tech Stack

- **API**: FastAPI + Celery + PostgreSQL + Redis
- **Vector DB**: Qdrant
- **LLM**: Claude (claude-sonnet-4-6 for eval, claude-haiku-4-5 for extraction)
- **Embeddings**: OpenAI text-embedding-3-small
- **Frontend**: Next.js 15 + Tailwind CSS
- **Infra**: Docker Compose

## Development

```bash
make test      # pytest
make lint      # ruff check + format check
make logs      # docker compose logs -f
make shell-api # bash into API container
make shell-db  # psql into PostgreSQL
```
