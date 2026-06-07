# Kortex — Build Specification

> **Purpose of this document:** This is a build-ready spec meant to drive implementation (by you, or by an AI coding agent). It defines WHAT we're building, WHY, WHO it's for, WHEN each piece gets built, WHERE it runs, and HOW each component works. Follow the phases in order — each phase produces something demoable on its own.

---

## 1. Elevator Pitch

**Kortex** is an AI-native platform that continuously ingests, structures, validates, scores, and maintains organizational knowledge — and provides a shared, reliable memory layer for both AI agents and human teams.

> Most enterprise AI failures are not caused by weak models — they are caused by poor knowledge.

Think of it as: **Data Observability + Knowledge Graph + Agent Memory + RAG Reliability Platform**, built incrementally so that every phase ships something real and demoable.

---

## 2. WHY — Problem Statement

Enterprise AI systems suffer from four compounding problems:

1. **Data Entropy** — Documentation says v1, production runs v2, the wiki is 8 months stale, and the Jira ticket has the real answer. AI retrieves whatever it finds first — often the wrong thing.
2. **Context Fragmentation** — Knowledge is scattered across PDFs, Slack, Jira, Confluence, GitHub, databases, emails, and meeting recordings. No single source of truth exists.
3. **Agent Memory Loss** — Every new agent session re-learns the architecture, the database, the business logic — burning tokens, money, time, and accuracy.
4. **Retrieval Reliability** — RAG systems answer incorrectly because the underlying knowledge is stale, duplicated, contradictory, or poorly chunked.

**The bet:** the bottleneck in enterprise AI has shifted left — from "is the model good enough" to "is the knowledge good enough." This platform attacks the second question directly.

---

## 3. WHO — Target Users & Personas

**Primary users (the people who'd configure/operate it):**
- AI Engineers, Platform Engineers, Data Engineers, Enterprise Architects

**Secondary users (the people who'd consume its outputs):**
- Product Managers, Knowledge Management Teams, Engineering Managers

**Target organizations (who'd buy/deploy it):**
- Banks, Healthcare, Insurance, SaaS companies, Consulting firms, Government agencies

**For your build:** simulate one persona concretely — e.g., "a platform engineer at a mid-size SaaS company who needs their internal AI assistant to stop giving stale answers about API versions." Build toward that one scenario; generalize later.

---

## 4. WHAT — Scope, Defined in Phases

This is the most important section. **Do not attempt to build all of this at once** — the full vision is a 12–18 month, funded-team-scale platform. Instead, build it as four phases, where **each phase is a complete, demoable product on its own**, and later phases build on top of earlier ones.

### Phase 0 — Foundation (Weeks 1–2)
Set up repo, infra, CI, base data models, and a tiny seed corpus (don't wait for "real" data).

### Phase 1 — "Verity Core" (Weeks 3–6) — *the credibility engine*
A focused ingestion → validation → retrieval → eval pipeline for **2–3 source types** (recommended: PDFs + GitHub repo docs + Slack export, or PDFs + Confluence + Jira). This phase alone produces your headline metric: *"cleaning + scoring improved retrieval accuracy by X% and cut hallucination rate by Y%."*

Deliverables:
- Multi-source ingestion (2–3 sources)
- Entity/structure extraction & normalization
- Conflict detection + freshness/confidence scoring
- Lineage tracking (source + timestamp on every chunk)
- Vector store + retrieval layer
- **Eval harness** comparing raw vs. cleaned retrieval (THE centerpiece)

### Phase 2 — Knowledge Graph + Observability (Weeks 7–10)
Layer a knowledge graph on top of Phase 1's extracted entities, and expose everything via a dashboard.

Deliverables:
- Entity/relationship extraction → graph DB (Neo4j)
- Graph visualization (React Flow / Cytoscape)
- Knowledge Observability Dashboard (coverage %, staleness %, contradiction count, hallucination-risk trend)
- Hallucination Risk Engine (a scoring model, not a full predictor — start simple: rule-based + confidence heuristics)

### Phase 3 — Agent Memory Layer (Weeks 11–14)
The most novel, most difficult part — attempt this only after Phases 1–2 are solid.

Deliverables:
- Persistent memory store per agent role (architect, backend, QA, etc.)
- Shared memory propagation ("Agent A learns something → Agent B knows it")
- Simple multi-agent orchestration (orchestrator + 2–3 specialist agents, via LangGraph)

### Phase 4 — Polish & Extend (Weeks 15+, optional / stretch)
- AI Copilot (natural language Q&A over the knowledge graph)
- Autonomous maintenance triggers (PR merged → re-embed → re-score)
- Additional source connectors (Notion, SharePoint, Teams, video transcripts)
- Temporal knowledge graph ("what was true on Jan 1 vs. today")
- Knowledge drift detection

> **Rule of thumb:** If you only ever finish Phases 0–1, you still have a complete, demoable, metric-backed project. Everything past that is upside, not a requirement to "have something to show."

---

## 5. WHEN — Suggested Timeline

| Phase | Duration | Cumulative | Outcome if you stop here |
|---|---|---|---|
| Phase 0: Foundation | 2 weeks | Week 2 | Repo + infra ready |
| Phase 1: Verity Core | 4 weeks | Week 6 | **A complete, demoable tool with a real before/after metric** ✅ |
| Phase 2: Graph + Observability | 4 weeks | Week 10 | A platform with visual knowledge mapping + health dashboard |
| Phase 3: Agent Memory | 4 weeks | Week 14 | The "innovative" differentiator — persistent multi-agent memory |
| Phase 4: Polish/Extend | Open-ended | Week 15+ | Copilot, more connectors, temporal reasoning |

Adjust pacing to your available hours/week — but preserve the *order*. Each phase is a checkpoint where you have something complete to show, talk about, and put on a resume — even if you stop there.

---

## 6. WHERE — Architecture & Infrastructure

### 6.1 High-Level Architecture

```
Sources (Phase 1: 2-3 → Phase 4: 20+)
   PDFs · Slack · Jira · Confluence · GitHub · Databases · Videos · Emails
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 1: Multi-Source Ingestion                │  (Phase 1, expand later)
│  → connector per source: auth, parsing,        │
│    scheduling, rate limits                      │
└──────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 2: Entity & Relationship Extraction       │  (Phase 1 basic → Phase 2 full)
│  → NER / LLM extraction of entities & relations │
└──────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 3: Knowledge Graph (Neo4j)                │  (Phase 2)
└──────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 4: Knowledge Health Engines               │  (Phase 1: scoring basics)
│  ├─ Freshness Engine                            │  (Phase 2: full dashboard)
│  ├─ Conflict / Contradiction Detection          │
│  └─ Quality / Trust / Completeness Scoring       │
└──────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 5: Retrieval & Reliability Layer          │  (Phase 1)
│  → Vector store + hybrid search/reranking        │
│  → Pre-LLM scoring (freshness/trust/conflict)    │
│  → Hallucination Risk Engine                     │  (Phase 2)
└──────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 6: Agent Memory Layer                      │  (Phase 3)
│  → persistent + shared memory across agents      │
└──────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 7: Multi-Agent Orchestration (LangGraph)  │  (Phase 3)
└──────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 8: Autonomous Maintenance (event-driven)  │  (Phase 4)
└──────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────┐
│ LAYER 9: Observability Dashboard + AI Copilot   │  (Phase 2 dashboard, Phase 4 copilot)
└──────────────────────────────────────────────┘
        ↓
   Reliable AI Applications / Agents
```

### 6.2 Deployment / Where It Runs

- **Local development:** Docker Compose (Postgres, Redis, Qdrant, Neo4j, the API, the worker)
- **Demo/portfolio hosting:** a single cloud VM (e.g., AWS EC2 / DigitalOcean droplet) running the Docker Compose stack, OR deploy services individually to free/low-cost tiers (Render, Railway, Fly.io for backend; Vercel for frontend; managed Qdrant Cloud + Neo4j Aura free tiers)
- **Source data location:** start with a local seed corpus (sample PDFs, a public GitHub repo's docs, a sample Slack export) stored in an S3-compatible bucket (MinIO locally, S3 in cloud)
- **CI/CD:** GitHub Actions for tests + linting; optional auto-deploy to your hosting target

---

## 7. HOW — Tech Stack & Implementation Details

### 7.1 Stack (by layer)

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js + TypeScript + Tailwind CSS | Dashboard, graph viz, copilot UI |
| Graph Visualization | React Flow / Cytoscape / D3.js | For Phase 2 graph explorer |
| API Layer | FastAPI (Python) | Core backend, async endpoints |
| Async Processing | Celery + Redis | Background ingestion/scoring jobs |
| Orchestration | Apache Airflow | Scheduled ingestion & maintenance pipelines |
| Relational DB | PostgreSQL | Metadata, scores, lineage records |
| Vector DB | Qdrant | Embeddings + semantic search |
| Graph DB | Neo4j | Entities & relationships (Phase 2+) |
| Cache | Redis | Hot queries, session state |
| LLMs | Claude / GPT-5 / Gemini (pick ONE primary, others optional) | Extraction, scoring, copilot |
| Embeddings | OpenAI Embeddings or BGE Large (open-source, self-hostable) | Chunk embeddings |
| Agent Framework | LangGraph + Pydantic AI | Multi-agent orchestration (Phase 3) |
| Eval Framework | RAGAS or DeepEval, or a custom LLM-as-judge harness | THE most important tool — build this early |

> **Stack advice:** Don't install everything on day one. Phase 1 needs: FastAPI, Postgres, Qdrant, Redis, one embedding model, one LLM, and a basic Next.js frontend (or even just a CLI/notebook). Add Neo4j in Phase 2, LangGraph in Phase 3, Airflow whenever ingestion scheduling actually gets complex enough to need it.

### 7.2 Multi-Agent Architecture (Phase 3 detail)

| Agent | Responsibility |
|---|---|
| Orchestrator Agent | Planning, task routing, quality checks |
| Knowledge Agent | Build, update, maintain the knowledge graph |
| Freshness Agent | Detect stale content, trigger refresh |
| Conflict Agent | Detect contradictions, validate sources |
| Retrieval Agent | Hybrid search, reranking |
| Memory Agent | Long-term memory, agent memory management |

> Build the **Orchestrator + Knowledge + Memory** agents first — that trio alone demonstrates the "shared memory across agents" story, which is the most novel claim in the whole pitch.

### 7.3 Core Data Model (sketch — refine as you build)

```
Document
  id, source_type, source_url, ingested_at, raw_content_ref

Chunk
  id, document_id, text, embedding_ref, position,
  freshness_score, trust_score, completeness_score, conflict_risk

Entity
  id, name, type (Service/API/Team/Person/Rule...), source_chunk_ids

Relationship
  id, from_entity_id, to_entity_id, type (owns/uses/depends_on...), confidence

Conflict
  id, chunk_a_id, chunk_b_id, description, confidence_score, status (open/resolved)

LineageRecord
  id, chunk_id, source_document_id, source_owner, timestamp_chain

AgentMemory
  id, agent_role, memory_type (episodic/semantic), content, created_at, shared (bool)
```

### 7.4 The Eval Harness — Build This FIRST, Not Last

This is the single most important component because it's what turns "I built a pipeline" into "I proved my pipeline works." Recommended approach:

1. Assemble ~30–50 realistic Q&A pairs against your seed corpus (some with known stale/conflicting source data baked in deliberately).
2. Run retrieval against the **raw, uncleaned** corpus → record accuracy, hallucination rate (use LLM-as-judge scoring), and citation correctness.
3. Run the same queries against your **cleaned, scored, deduplicated** corpus → record the same metrics.
4. Plot the before/after comparison. This chart is your single most valuable artifact — it belongs on the README, in interviews, and in your portfolio writeup.

---

## 8. Success Metrics (How You'll Know It Worked)

- **Retrieval accuracy improvement**: cleaned vs. raw corpus (target: meaningful double-digit % improvement)
- **Hallucination rate reduction**: measured via LLM-as-judge or RAGAS faithfulness score
- **Conflict detection precision/recall**: against a labeled set of deliberately-seeded contradictions
- **Freshness scoring correctness**: spot-check against known stale/fresh documents
- **(Phase 3) Memory reuse rate**: how often Agent B successfully reuses Agent A's learned context instead of re-deriving it

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Scope creep — trying to build all 9 layers at once | Hard phase gates — do not start Phase N+1 until Phase N is demoable |
| No real enterprise data to test on | Build a deliberately messy seed corpus: mix real public docs (e.g., a popular OSS project's docs + issues + Slack-style chat export) with synthetic conflicts/staleness you inject yourself |
| Knowledge graph complexity balloons | Start with a small, fixed entity/relationship schema (5 entity types, 5 relationship types) — expand only if needed |
| Agent memory layer has no proven design pattern to copy | Start minimal: a shared key-value memory store with role-based namespaces; prove "Agent A learns → Agent B knows" with the simplest possible mechanism before adding sophistication |
| Eval harness feels like "extra work" so it gets deprioritized | Build it FIRST (Section 7.4) — it's the proof, not the garnish |

---

## 10. Suggested Repo Structure

```
kortex/
├── README.md                  ← include the before/after eval chart prominently
├── docker-compose.yml
├── infra/                     ← Terraform/IaC if you containerize for cloud
├── apps/
│   ├── api/                   ← FastAPI backend
│   ├── worker/                ← Celery tasks (ingestion, scoring, embeddings)
│   ├── web/                   ← Next.js frontend (dashboard, graph viz, copilot)
│   └── agents/                ← LangGraph multi-agent system (Phase 3)
├── pipelines/
│   ├── ingestion/             ← per-source connectors
│   ├── extraction/            ← entity/relationship extraction
│   ├── scoring/               ← freshness, trust, conflict, completeness
│   └── eval/                  ← THE eval harness — build early, keep central
├── data/
│   ├── seed_corpus/           ← your curated messy sample data
│   └── eval_qa_pairs/         ← your 30-50 test Q&A pairs
├── docs/
│   ├── architecture.md
│   ├── data_model.md
│   └── roadmap.md
└── tests/
```

---

## 11. Resume / Portfolio Framing (once built)

**Title:** *Kortex — Enterprise Knowledge Reliability, Memory & Agent Intelligence Platform*

**Description draft:**
> Built an AI-native knowledge operations platform that ingests enterprise data from multiple sources, constructs a validated knowledge graph, maintains shared multi-agent memory, detects knowledge conflicts and staleness, and measurably reduces RAG hallucination rates through automated knowledge scoring and observability — demonstrated with a before/after evaluation harness showing a [X]% improvement in retrieval accuracy.

> Adjust the bracketed claim to match what you actually measured — a real, modest number beats an inflated, vague one in any technical conversation.

---

## 12. Immediate Next Steps (Start Here)

1. [ ] Set up the repo using the structure in Section 10
2. [ ] Stand up Docker Compose with Postgres, Redis, Qdrant (defer Neo4j/Airflow until Phase 2)
3. [ ] Curate a seed corpus: pick 2-3 source types, gather ~50-100 documents, deliberately inject some conflicts and stale data so your eval has something real to detect
4. [ ] Build the eval harness skeleton FIRST — even before the cleaning pipeline exists, so you can measure your "raw" baseline
5. [ ] Build ingestion + extraction for source #1, get it flowing end-to-end into the vector store
6. [ ] Add validation/conflict detection + scoring
7. [ ] Run the eval harness again — compare against your baseline — that's your Phase 1 finish line 🎯

---

*Document generated as a build companion — refine the bracketed/estimated details (timelines, metrics, stack choices) as you learn more during implementation.*
