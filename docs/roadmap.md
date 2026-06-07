# Kortex — Roadmap

## Phase 0 — Foundation ✅ (Complete)
- [x] Repo structure
- [x] Docker Compose (Postgres, Redis, Qdrant, API, Worker, Web)
- [x] SQLAlchemy 2.0 data models (7 tables)
- [x] FastAPI with health, documents, search, stats endpoints
- [x] Celery worker setup
- [x] Alembic migrations
- [x] GitHub Actions CI (ruff + pytest + type-check)
- [x] Synthetic seed corpus

## Phase 1 — Verity Core ✅ (Complete)
- [x] BaseConnector + PDF + Markdown connectors
- [x] Claude-based entity extraction
- [x] Freshness scorer (age-based decay)
- [x] Trust scorer (source-type heuristics)
- [x] Conflict detector (cosine sim + Claude judge)
- [x] Qdrant vector store integration
- [x] Semantic search endpoint with score filtering
- [x] Eval harness (30 Q&A pairs, raw vs. cleaned, Claude judge)
- [x] Next.js dashboard (health, documents, search, eval pages)

## Phase 2 — Knowledge Graph + Observability (Next)
- [ ] Neo4j integration
- [ ] Entity/relationship graph visualization (React Flow)
- [ ] Knowledge Observability Dashboard (staleness %, conflict trend)
- [ ] Hallucination Risk Engine (rule-based + confidence heuristics)
- [ ] Airflow for scheduled ingestion pipelines

## Phase 3 — Agent Memory Layer
- [ ] Persistent memory store per agent role (AgentMemory table is ready)
- [ ] Shared memory propagation across agent roles
- [ ] LangGraph multi-agent orchestration (Orchestrator + Knowledge + Memory agents)

## Phase 4 — Polish & Extend
- [ ] AI Copilot (natural language Q&A over the knowledge graph)
- [ ] Autonomous maintenance triggers (PR merged → re-embed → re-score)
- [ ] Additional connectors: Notion, SharePoint, Confluence, Slack (live)
- [ ] Temporal knowledge graph (what was true on date X)
- [ ] Knowledge drift detection
