# Kortex

**Enterprise Knowledge Reliability, Memory & Agent Intelligence Platform**

An AI-native platform that continuously ingests, structures, validates, scores, and maintains organizational knowledge — providing a shared, reliable memory layer for both AI agents and human teams.

> Most enterprise AI failures are not caused by weak models — they're caused by poor knowledge.

Kortex ingests data from multiple sources, extracts entities **and business rules — decisions, policies, processes, and their rationale (the "why")** — into a knowledge graph, scores every chunk for freshness / trust / conflict / hallucination-risk, serves graph-aware retrieval, a copilot, and a **business-logic reasoning endpoint**, and runs a persistent multi-agent memory layer — all proven by a before/after eval harness that now also measures *business understanding*, not just fact retrieval.

## Quick Start

```bash
# 1. Create .env with your API keys — ANTHROPIC_API_KEY and OPENAI_API_KEY are
#    required (see "Environment Variables" in CLAUDE.md for the full list).

# 2. Start all services (postgres, redis, qdrant, neo4j, api, worker, web)
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
- **Documents / Search / Graph / Observability / Chat / Agents**: linked from the dashboard nav
- **API docs**: http://localhost:8000/docs

## Eval Harness

The eval harness is the core proof-of-value. It runs 30 Q&A pairs against the seed corpus in two modes and compares results:

<!-- EVAL_TABLE_START -->
| Metric | Raw | Cleaned | Delta |
|--------|-----|---------|-------|
| Accuracy | — | — | run `make eval-report` |
| Faithfulness | — | — | |
| Hallucination Rate | — | — | |
| Explains Rationale (why) | — | — | |
| Conflicts Surfaced | — | — | |
<!-- EVAL_TABLE_END -->

> The table above is auto-populated. The `—` placeholders are filled in by a real
> run — see [Populating the table](#populating-the-table) below. No numbers are
> hardcoded.

The seed corpus contains deliberate conflicts (API docs v1 vs. v2 with contradictory authentication methods, rate limits, data retention policies, and SDK support). **Cleaned mode** filters out stale/conflicting chunks — the delta between raw and cleaned is the headline metric.

Beyond fact retrieval, the harness also scores **business understanding**: *Explains Rationale* (does the answer explain the *why* — the decision/policy behind a fact, not just the fact) and *Conflicts Surfaced* (of the seeded-conflict questions, how many answers explicitly call out the contradiction instead of silently picking a side).

### Populating the table

The numbers above are generated on your machine (requires Docker + real API keys —
they are never hardcoded in this repo). One-time prerequisites:

```bash
# set REAL ANTHROPIC_API_KEY + OPENAI_API_KEY in .env (the single config file)
make up                       # start postgres, redis, qdrant, neo4j, api, worker, web
make migrate                  # create the tables
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
Sources (Markdown · PDF · GitHub code+issues+PRs · Slack · Gmail · Notion)
    ↓ Ingestion (pipelines/ingestion/ — one connector per source)
    ↓ Extraction (Claude Haiku → entities + relationships AND business rules + rationale)
    ↓ Scoring (freshness + trust + conflict + hallucination risk + drift)
    ↓ Storage (PostgreSQL + Qdrant + Neo4j knowledge graph)
    ↓ Retrieval (semantic search with score filtering)
    ├─ Eval (30 Q&A × raw vs. cleaned × Claude judge — incl. business understanding)
    ├─ AI Copilot (graph-aware Q&A over the knowledge base)
    ├─ Reasoning (business-logic Q&A: explains the "why", cites rules, surfaces conflicts)
    ├─ Multi-Agent Memory Layer (LangGraph: orchestrator + knowledge + memory)
    ├─ Observability dashboard (coverage / staleness / conflicts / risk)
    └─ Autonomous maintenance (Celery beat: periodic re-scoring)
```

See [docs/architecture.md](docs/architecture.md) and [docs/data_model.md](docs/data_model.md) for details.

### How a document flows through the system

`POST /api/v1/documents` → DB `Document` record → Celery `ingest_document_task`
→ connector parses & chunks → OpenAI embeds → Qdrant upsert + `Chunk` records →
`score_document_chunks_task` (freshness/trust/conflict/hallucination-risk) →
entity & relationship extraction **plus business-rule extraction** (each rule
linked to the entities it governs) → Neo4j graph sync (entities, relationships,
`BusinessRule` nodes, `SUPERSEDES` + `GOVERNS` edges). A periodic
`maintenance_sweep` re-scores chunks as they age.

## Source Connectors

Each source has a connector under `pipelines/ingestion/`. Register a source via
`POST /api/v1/documents` or the dashboard's **Documents** page. Connectors whose
credentials are unset stay disabled (they raise a clear error if invoked).

| Source | `source_type` | What `source` is | Credentials (in `.env`) |
|--------|---------------|------------------|--------------------------|
| Markdown | `markdown` | file path, URL, or raw text | — |
| PDF | `pdf` | file path | — |
| GitHub | `github` | `owner/repo` or repo URL — ingests the **codebase + issues, pull requests & their comments** | `GITHUB_TOKEN` |
| Slack | `slack` | channel ID or `#channel` | `SLACK_BOT_TOKEN` |
| Gmail | `gmail` | Gmail search query (e.g. `newer_than:30d`) | `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH` |
| Notion | `notion` | page or database ID | `NOTION_TOKEN` |

GitHub, Slack, Gmail, and Notion are live-API integrations (PyGithub /
`slack_sdk` / Google API + OAuth2 / `notion-client`). Ingestion is hardened by a
shared `pipelines/ingestion/security.py` layer. See [CLAUDE.md](CLAUDE.md) →
*Adding a New Source Connector* to add more.

## Knowledge Health Scoring

Every chunk is scored on ingest (and re-scored periodically):

| Scorer | File | What it measures |
|--------|------|------------------|
| Freshness | `pipelines/scoring/freshness.py` | Age-based decay, per-source-type decay rates |
| Trust | `pipelines/scoring/trust.py` | Source-type base credibility |
| Conflict | `pipelines/scoring/conflict.py` | Cosine sim ≥ 0.85 + Claude Haiku judge → `Conflict` records |
| Hallucination Risk | `pipelines/scoring/hallucination_risk.py` | Rule-based blend of freshness / trust / conflict |
| Drift | `pipelines/scoring/drift.py` | Semantic + quality drift vs. a prior version of a chunk |

## Knowledge Graph

Entity & relationship extraction (`pipelines/extraction/entity_extractor.py`,
Claude Haiku NER) populates `Entity` and `EntityRelationship` records, which are
synced into **Neo4j** (`pipelines/graph/sync.py`). The graph also holds
`BusinessRule` nodes with `SUPERSEDES` edges (decision provenance) and `GOVERNS`
edges linking rules to the entities they constrain — so the decision graph and
the entity graph are one connected graph. It is served via `GET /api/v1/graph`
and visualized on the **Graph** page (React Flow). The AI copilot is graph-aware:
retrieved chunks are matched to known entities, whose relationships are injected
into the answer prompt.

## Business Logic Layer

Beyond *what* the knowledge base says, Kortex captures *why* — the decisions,
policies, processes, and constraints that govern the application, each with its
**rationale**. This is what separates business knowledge from raw knowledge.

- **Extraction** — `pipelines/extraction/business_extractor.py` (Claude Haiku)
  pulls `BusinessRule` records (`statement` = what, `rationale` = why, typed
  `decision` / `policy` / `process` / `constraint` / `metric`) alongside entity
  extraction during ingestion.
- **Decision provenance** — a rule can `supersede` an earlier one; these chains
  become `SUPERSEDES` edges in Neo4j (e.g. "OAuth supersedes API keys").
- **Rule → entity links** — each rule is linked to the entities mentioned in its
  source chunk (`BusinessRuleEntityLink`), synced as `GOVERNS` edges. This powers
  multi-hop reasoning: *chunk → entity → governing rule*.
- **Reasoning endpoint** — `POST /api/v1/reasoning/ask` retrieves chunks
  (deliberately keeping conflicting ones), gathers the relevant business rules
  (by provenance, keyword, **and** graph traversal) plus any open conflicts, and
  asks Claude to **explain the business logic, cite the governing rules, and
  explicitly surface contradictions** (preferring `active`/newer rules) rather
  than silently picking a side. Returns the answer plus `cited_rules` and
  `conflicts`.

## Multi-Agent Memory Layer

A LangGraph workflow (`agents/graph/workflow.py`) wires a linear 5-node graph:
`orchestrator_plan → memory_recall → knowledge_retrieve → orchestrator_synthesize
→ memory_write`. The persistent store (`agents/memory/store.py`) backs the
`AgentMemory` model.

The novel claim — **"Agent A learns → Agent B knows"** — is implemented via
`shared=True` memories: a fact written by one agent role becomes recallable by
any other role (`include_shared=True`). Memory reuse is tracked by stamping
`accessed_at` on recall. Exposed via `POST /api/v1/agents/query`,
`GET/POST /api/v1/agents/memory`, and the **Agents** page.

## AI Copilot

`POST /api/v1/chat` answers natural-language questions over the knowledge base
using score-filtered retrieval, grounded strictly in retrieved context
("I don't know" when context is insufficient), and enriched with knowledge-graph
relationships. Served on the **Chat** page.

## Autonomous Maintenance

A Celery beat schedule (`app.celery_app`) runs `maintenance_sweep` every
`MAINTENANCE_RESCORE_INTERVAL_MINUTES` (default 60), re-scoring chunks so
freshness/trust/conflict signals stay current as documents age. The sweep is
defensive — it degrades gracefully (logs + returns a degraded status) when
Postgres/Qdrant are unavailable.

## Phases

| Phase | Status | Outcome |
|-------|--------|---------|
| Phase 0: Foundation | ✅ Complete | Infra, models, API, CI |
| Phase 1: Verity Core | ✅ Complete | 6-source ingestion → scoring → retrieval → eval |
| Phase 2: Knowledge Graph + Observability | ✅ Complete | Neo4j graph + graph viz + observability dashboard + hallucination-risk scoring |
| Phase 3: Agent Memory | ✅ Complete | Persistent + shared multi-agent memory (LangGraph orchestrator + knowledge + memory) |
| Phase 4: Polish & Extend | ✅ Complete | AI copilot, graph-aware chat, autonomous maintenance, drift detection, Notion connector |
| Phase 5: Business Logic Layer | 🚧 In progress | Business-rule extraction (+ rationale), `SUPERSEDES`/`GOVERNS` graph edges, business-logic reasoning endpoint, GitHub issue/PR ingestion, business-understanding eval metrics |

## Data Model

9 SQLAlchemy 2.0 models (`apps/api/app/models/`): `Document`, `Chunk`,
`Entity`, `EntityRelationship`, `Conflict`, `LineageRecord`, `AgentMemory`,
`BusinessRule`, and `BusinessRuleEntityLink` (rule → entity `GOVERNS` link).
Every chunk carries a `LineageRecord` (source + timestamp chain). See
[docs/data_model.md](docs/data_model.md).

## Tech Stack

- **API**: FastAPI + Celery (+ beat) + PostgreSQL + Redis
- **Vector DB**: Qdrant
- **Graph DB**: Neo4j (knowledge graph: entities + relationships + business rules with `SUPERSEDES`/`GOVERNS` edges)
- **Agents**: LangGraph multi-agent workflow + persistent memory store
- **Connectors**: PyGithub, `slack_sdk`, Google API + OAuth2, `notion-client`
- **LLM**: Claude (claude-sonnet-4-6 for eval, claude-haiku-4-5 for extraction/conflict)
- **Embeddings**: OpenAI text-embedding-3-small
- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS + React Flow
- **Infra**: Docker Compose (6 services: postgres, redis, qdrant, neo4j, api, worker, web)
- **CI**: GitHub Actions (pytest + ruff)

## Development

```bash
make test         # pytest tests/  (unit tests — no Docker needed for scoring/agent tests)
make lint         # ruff check + format check
make format       # ruff auto-fix
make eval-report  # run eval (both modes) + auto-fill the metric table above
make logs         # docker compose logs -f
make shell-api    # bash into API container
make shell-db     # psql into PostgreSQL
```

Test suite covers scoring, extraction, business-rule extraction + reasoning, the
rule → entity (`GOVERNS`) links, business-understanding eval scoring, the agent
memory store + workflow, the knowledge graph, hallucination risk, ingestion
security, and each live connector (GitHub code+issues / Slack / Gmail). See
[CLAUDE.md](CLAUDE.md) for the full command reference and architecture notes.
