# Kortex — Data Model

All tables use UUID primary keys and live in the default PostgreSQL schema.

## Document
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| source_type | VARCHAR(50) | pdf, markdown, github, slack, etc. |
| source_url | TEXT | file path or URL |
| title | TEXT | nullable |
| raw_content_ref | TEXT | S3 key or file path to raw content |
| extra_metadata | JSONB | arbitrary key-value |
| ingested_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

## Chunk
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| document_id | UUID FK → documents | cascade delete |
| text | TEXT | chunk content (≈512 tokens) |
| position | INT | order within document |
| embedding_id | TEXT | Qdrant point ID |
| freshness_score | FLOAT | 0–1 (1=freshest) |
| trust_score | FLOAT | 0–1 |
| completeness_score | FLOAT | 0–1 |
| conflict_risk | FLOAT | 0–1 (0=no risk) |
| created_at | TIMESTAMPTZ | |
| scored_at | TIMESTAMPTZ | |

## Entity
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| name | TEXT | |
| entity_type | VARCHAR(50) | Service, API, Team, Person, Rule, Concept |
| description | TEXT | nullable |
| created_at, updated_at | TIMESTAMPTZ | |

## EntityRelationship
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| from_entity_id | UUID FK → entities | |
| to_entity_id | UUID FK → entities | |
| rel_type | VARCHAR(50) | owns, uses, depends_on, calls, etc. |
| confidence | FLOAT | 0–1 |

## Conflict
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| chunk_a_id | UUID FK → chunks | |
| chunk_b_id | UUID FK → chunks | |
| description | TEXT | Claude's explanation |
| confidence_score | FLOAT | 0–1 |
| status | VARCHAR(20) | open, resolved, dismissed |
| detected_at | TIMESTAMPTZ | |
| resolved_at | TIMESTAMPTZ | nullable |

## LineageRecord
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| chunk_id | UUID FK → chunks | |
| source_document_id | UUID FK → documents | |
| source_owner | TEXT | source URL or owner |
| timestamp_chain | JSONB | array of ISO timestamps |

## AgentMemory (Phase 3)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| agent_role | VARCHAR(100) | architect, backend, qa, etc. |
| memory_type | VARCHAR(20) | episodic, semantic, procedural |
| content | TEXT | |
| extra_metadata | JSONB | |
| shared | BOOLEAN | whether other agents can access |
| created_at, accessed_at | TIMESTAMPTZ | |
