# Kortex — Architecture

## High-Level Flow

```
Sources (Markdown, PDF, Slack, GitHub, ...)
        ↓
Layer 1: Multi-Source Ingestion (pipelines/ingestion/)
  → BaseConnector per source type
  → Chunks via RecursiveCharacterTextSplitter
        ↓
Layer 2: Entity Extraction (pipelines/extraction/)
  → Claude Haiku NER → Entity + EntityRelationship tables
        ↓
Layer 3: Knowledge Health Scoring (pipelines/scoring/)
  → FreshnessScorer — age-based decay per source type
  → TrustScorer — base score per source type × consistency
  → ConflictDetector — cosine sim ≥ 0.85 + Claude judge
        ↓
Layer 4: Storage
  → PostgreSQL — Documents, Chunks, Entities, Conflicts, Lineage
  → Qdrant — embeddings (text-embedding-3-small, 1536 dims)
        ↓
Layer 5: Retrieval
  → POST /api/v1/search — Qdrant semantic search
  → Cleaned mode: filters by freshness_score + conflict_risk
        ↓
Layer 6: Eval Harness (pipelines/eval/harness.py)
  → 30 Q&A pairs × raw vs. cleaned retrieval
  → Claude as LLM judge (faithfulness, correctness, hallucination)
  → Before/after comparison table
```

## Services

| Service | Port | Technology |
|---------|------|-----------|
| API | 8000 | FastAPI + uvicorn |
| Worker | — | Celery + Redis |
| Web | 3000 | Next.js 15 |
| PostgreSQL | 5432 | postgres:16-alpine |
| Redis | 6379 | redis:7-alpine |
| Qdrant | 6333 | qdrant/qdrant |

## Async Processing

Document ingestion is async. `POST /api/v1/documents` creates the DB record and fires
`ingest_document_task` on Celery. The worker runs: extract → embed → store in Qdrant → run conflict detection.
