# Phase 5 — Structural Code Graph (v0.1)

**Status:** Design • **Author:** Developer Agent A • **Scope:** v0.1 structural layer ONLY
**Consumed by:** Developer Agent B (code↔business linking + conflict layer — out of scope here)

---

## 1. Problem & Goal

Kortex ingests GitHub repositories through `pipelines/ingestion/github.py`, which decodes each
allowlisted source file and emits opaque **text** `RawChunk`s (512-token splits) for embedding and
retrieval. This gives us semantic *text* search over code, but no **structural** understanding: we
cannot answer "what calls `process_refund`?", "what does the `BillingService` class define?", or
"which functions inherit from `BaseConnector`?". Those are graph questions, and we already own the
graph substrate (Entity / EntityRelationship → Neo4j).

The goal of v0.1 is to add a **parallel, additive** pass that parses source files into a structural
graph of `MODULE` / `CLASS` / `FUNCTION` entities connected by `DEFINES` / `CALLS` / `INHERITS`
edges, reusing the existing entity/relationship tables and Neo4j sync verbatim. **The existing
text-chunk path is unchanged** — code is still embedded and retrievable as text. This is an
*additional* projection of the same files, not a replacement.

---

## 2. Approach — tree-sitter parsing

We parse source files with **tree-sitter** (`tree-sitter` + per-language grammar packages, e.g.
`tree-sitter-python`). v0.1 ships **Python only**; the design leaves a clean path to the other
languages already allowlisted in `github.py` (`.js/.ts/.tsx/.go/.rs/.java/.rb/...`,
`_ALLOWED_EXTENSIONS` at `pipelines/ingestion/github.py:16`).

**Why tree-sitter over the alternatives:**

- **vs. regex** — regex cannot reliably distinguish a definition from a call, a method from a
  module-level function, or handle nesting/decorators/multiline signatures. It produces noisy,
  unmaintainable edges.
- **vs. Python's stdlib `ast`** — `ast` is Python-only. We'd need a *different* parser library per
  language and a *different* node-visitor implementation each time. tree-sitter gives us **one
  parsing API and one query language (S-expression queries)** across every grammar, so adding a
  language in v0.2 is "add the grammar package + a query file", not "write a new visitor".
- tree-sitter is **error-tolerant** (parses files with syntax errors, common in a real repo
  snapshot) and **fast** (incremental C parsers), which matters for the per-repo scale limits in §9.

The trade-off: tree-sitter gives us **lexical/structural** facts cheaply but does **not** do type
inference or import resolution. Call-edge resolution is therefore best-effort (see §11). That is an
acceptable v0.1 boundary — structure first, precision later.

---

## 3. New Component — `pipelines/extraction/code_graph.py`

**Responsibility:** parse a *single source file* into structural Entity nodes and EntityRelationship
edges. It is the code-graph analogue of `pipelines/extraction/entity_extractor.py`, but
deterministic (tree-sitter), not an LLM call.

### Input contract

It receives exactly the fields a `github.py` `RawChunk.metadata` already carries
(`pipelines/ingestion/github.py:161`), plus the **full file text** (not the 512-token split — we
need the whole file to parse it):

```python
def extract(self, file_text: str, *, repo: str, file_path: str, ref: str) -> CodeGraphResult: ...
```

- `file_text` — full UTF-8 decoded file content.
- `repo` — e.g. `"acme/billing"` (the normalized `owner/repo` from `RawChunk.metadata["repo"]`).
- `file_path` — repo-relative path, e.g. `"src/refund.py"` (`metadata["file_path"]`).
- `ref` — branch/commit, e.g. `"main"` (`metadata["ref"]`). Carried through for provenance.

The connector splits files for embedding, but the code-graph pass needs the whole file. See §6 for
how the task fetches full text (it re-decodes from the same source the connector used; it does **not**
reconstruct from chunks).

### Output contract

```python
class CodeEntity(TypedDict):
    name: str          # namespaced symbol, e.g. "acme/billing:src/refund.py::process_refund"
    type: str          # EntityType.MODULE | CLASS | FUNCTION (the string value)
    description: str    # provenance string, see §5
    # internal-only, NOT persisted as columns — used to resolve edges:
    local_name: str     # bare symbol, e.g. "process_refund"
    file_line: int      # 1-based definition line

class CodeEdge(TypedDict):
    from_name: str     # namespaced source symbol
    to_name: str       # namespaced target symbol (may be a same-file local; cross-file = best effort)
    type: str          # EntityType-relationship: DEFINES | CALLS | INHERITS
    confidence: float   # 1.0 for DEFINES/INHERITS within file; <1.0 for unresolved CALLS

class CodeGraphResult(TypedDict):
    entities: list[CodeEntity]
    edges: list[CodeEdge]
```

Emitted nodes/edges per file:
- one `MODULE` entity for the file itself.
- one `CLASS` entity per class definition; one `FUNCTION` entity per function/method definition.
- `DEFINES` edges: module→(top-level class/function), class→(method/nested class).
- `INHERITS` edges: class→base class (intra-file resolved; cross-file emitted by name, resolved
  best-effort in §11).
- `CALLS` edges: function→called symbol (intra-file resolved by name; cross-file best-effort).

This shape mirrors the `{"entities": [...], "relationships": [...]}` shape that
`entity_extractor.extract()` already returns (`pipelines/extraction/entity_extractor.py:31`), so the
persistence/upsert code that consumes it is nearly identical.

---

## 4. Data Model Changes

### Enum additions (exact edits)

**`apps/api/app/models/entity.py:12`** — add to `EntityType`:

```python
    MODULE = "Module"
    FUNCTION = "Function"
    CLASS = "Class"
```

**`apps/api/app/models/relationship_record.py:12`** — add to `RelationshipType`:

```python
    DEFINES = "defines"
```

`CALLS`, `INHERITS`, `REFERENCES` already exist (`relationship_record.py:16-18`) and are reused as-is.
`IMPLEMENTS` (code→business) is **Developer B's** addition — noted here only so B knows it does not
yet exist; we do not add it.

### No new tables

Code entities and edges are stored in the **existing** `entities` and `entity_relationships` tables.
No new table, no new model.

### Migration: none required (clarification)

`entity_type` and `rel_type` are `String(50)` columns holding **app-level string values**
(`entity.py:29`, `relationship_record.py:34`) — they are **not** PostgreSQL `ENUM` types. The repo
creates schema via `Base.metadata.create_all` (per CLAUDE.md), and the column type is unchanged.
Therefore adding enum *members* is a **pure Python change with zero schema impact — no Alembic
migration is needed.** (If these were native PG enums, we'd need `ALTER TYPE ... ADD VALUE`; they are
not, so we don't.)

---

## 5. Provenance (`file:line`)

Code entities must carry where they came from (`repo`, `file_path`, `ref`, definition line) so the
Graph viz and Developer B's linker can point a user at the source. We have **no spare columns** on
`Entity` (only `name`, `entity_type`, `description`, timestamps — `entity.py:28-38`).

**v0.1 decision: encode provenance in `Entity.description`** as a stable, machine-parseable prefix:

```
description = "code: acme/billing:src/refund.py:42 @main"   # repo:path:line @ref
```

- Pro: zero schema change, fully reuses `GraphSyncer` which already copies `description` to Neo4j
  (`pipelines/graph/sync.py:22-27`) — provenance lands on the Neo4j node for free.
- Con: it's an unstructured string; consumers must parse it. The `name` field *also* carries
  `repo:path` (§8), so the only thing unique to `description` is the **line number** and `ref`.

**Flagged tradeoff (deferred, not done in v0.1):** a dedicated `Entity.source_ref` /
`Entity.source_line` column pair would be cleaner and queryable, but it touches the shared model and
the Neo4j sync, and the parallel Developer-B work also reads `Entity`. To avoid a schema collision
across two concurrent agents, v0.1 stays column-free and uses `description`. **Open question for the
Master Agent: promote provenance to real columns in a follow-up once both Phase-5 agents merge.**

---

## 6. Ingestion Flow Integration

Today the chain is (CLAUDE.md + `tasks/ingestion.py`):

```
ingest_document_task → score_document_chunks_task → extract_entities_task → (graph sync)
```

`score_document_chunks_task` fires `extract_entities_task`
(`apps/api/app/tasks/ingestion.py:161`), and **today the graph sync is triggered from *inside*
`extract_entities_task`** (`sync_graph_task.delay()` at `apps/api/app/tasks/extraction.py:88`), not as
a separate downstream step. We add a **sibling** task, `extract_code_graph_task`, fired alongside
`extract_entities_task` from `score_document_chunks_task`, **only for GitHub documents**. Both
text-entity extraction and code-graph extraction independently write Entity/EntityRelationship rows.
Because `GraphSyncer.sync_all` re-syncs the whole graph, the code-graph task must also call
`sync_graph_task.delay()` on completion (or the implementation can rely on the next global sync) so its
rows reach Neo4j — the diagram below shows the intended end state, not the current single trigger.

```
                         ┌───────────────────────────────┐
ingest_document_task ──▶ score_document_chunks_task       │
 (github.py: text                  │                       │
  RawChunks, embed)                ├──▶ extract_entities_task ──┐  (LLM text entities)
                                   │                            ├──▶ sync_graph_task ──▶ Neo4j
                                   └──▶ extract_code_graph_task ┘  (tree-sitter MODULE/
                                        (NEW, GitHub only)          CLASS/FUNCTION + edges)
```

`extract_code_graph_task(document_id)`:
1. Loads the `Document`; if `source_type != SourceType.GITHUB`, returns a no-op (guard, mirroring the
   connector dispatch at `tasks/ingestion.py:30-33`).
2. Re-reads the repo's allowlisted **Python** files from the same source the connector used (reusing
   `GitHubConnector` traversal + `_is_allowed_path` + `_MAX_FILE_BYTES` — see §9), getting full file
   text per file rather than 512-token splits.
3. For each file calls `CodeGraphExtractor.extract(file_text, repo=…, file_path=…, ref=…)`.
4. Upserts `CodeEntity` → `entities` and `CodeEdge` → `entity_relationships` using the same
   get-or-create-by-name pattern as text extraction, but **keyed on the namespaced name** (§8).
5. Triggers `sync_graph_task` (the same sync `extract_entities_task` already calls at
   `extraction.py:88`) so the new code rows reach Neo4j.

This keeps the embedding/scoring path completely untouched; the code-graph pass is strictly additive
and isolated behind a source-type guard.

---

## 7. Reuse (the substrate already exists)

Explicitly **reused unchanged**:

- **`pipelines/graph/sync.py`** — `GraphSyncer.sync_all` MERGEs every `Entity` by UUID `id` and every
  `EntityRelationship` as `RELATES_TO {rel_type}` (`sync.py:18-41`). Code entities are just more
  `Entity` rows with new `entity_type` strings and new `rel_type` strings; **no sync change needed.**
- **The Graph page visualization** — it renders Neo4j `Entity` nodes / `RELATES_TO` edges; new node
  types appear automatically (styling by `entity_type` is a nice-to-have, not required for v0.1).
- **The copilot's graph context** — any tool that queries the Neo4j graph now also sees code
  structure, with no change to the retrieval code.
- **`entities` / `entity_relationships` tables** — no schema change (§4).
- **`github.py` traversal helpers** — `_normalize_source`, `_is_allowed_path`, `_MAX_FILE_BYTES`
  reused by the code-graph task.

The deliberate point of this design: we are adding a *parser and a task*, and nothing else. Storage,
graph sync, and visualization are pre-existing.

---

## 8. Namespacing & Dedup

**Scheme (FIXED):** every code Entity `name` is `repo:path::symbol`, e.g.
`acme/billing:src/refund.py::process_refund`. The MODULE node is `repo:path` (no `::symbol`).

**Why this is required.** The existing entity dedup convention is **global and lowercased-name**:
text extraction (`entity_extractor.py`) de-duplicates entities by their bare name across the *entire*
corpus. If code symbols used bare names, then `process_refund` defined in `billing/refund.py` and an
unrelated `process_refund` in `payments/legacy.py` (and any prose mention of "process_refund") would
**collapse into one node**, fusing unrelated `CALLS`/`DEFINES` edges and producing a meaningless
graph. Functions named `__init__`, `handler`, `main`, `run`, `get` would become massive false hubs.

Prefixing with `repo:path::` makes each symbol's dedup key **globally unique per definition site**,
so same-named symbols in different files stay distinct, while a re-ingest of the same file at the same
path correctly **idempotently merges** (same name → same node). This relies on no change to the dedup
logic — it just feeds it unique keys.

Cross-file edge targets are emitted with their best-resolved namespaced name when known; unresolved
references are recorded at reduced confidence (§11) rather than guessed into the wrong node.

---

## 9. Perf / Scale Bounding

A large repo can explode the graph (thousands of files × tens of symbols each). v0.1 limits:

1. **Reuse `_MAX_FILE_BYTES` (1 MB)** at the file level (already enforced in `github.py:57,132,143`)
   *and* introduce a **per-file symbol cap** (e.g. skip emitting beyond N=500 symbols/file — a file
   with more is generated/minified and not worth graphing). This is "the `_MAX_FILE_BYTES` idea at
   symbol granularity".
2. **Per-repo symbol cap** (e.g. 50k entities) — stop and log a truncation warning rather than
   unbounded growth.
3. **Skip vendored/generated dirs** — a deny-list applied before parsing: `node_modules/`, `vendor/`,
   `dist/`, `build/`, `.venv/`, `__pycache__/`, `migrations/`, `*.min.js`, `*_pb2.py`, generated
   protobuf/openapi. (v0.1 ships a default deny-list; later configurable per repo.)
4. **v0.1 parses Python only**, so non-`.py` allowlisted files are skipped by the code-graph pass
   entirely (they still take the text path), naturally bounding work.
5. **Batch DB writes** per file and commit per repo, matching the existing task's commit style.

---

## 10. The Contract Handed to v1 (Developer B)

> **What the code↔business linker receives.**
>
> After `extract_code_graph_task` completes, the `entities` table contains code `Entity` rows where:
>
> - `entity_type ∈ {Module, Class, Function}`.
> - `name` is the **namespaced symbol** `repo:path::symbol` (Module = `repo:path`).
> - `description` carries provenance `code: repo:path:line @ref` (parseable for `file:line`, §5).
> - structural edges already exist in `entity_relationships`: `defines`, `calls`, `inherits`.
>
> Developer B builds the **v1 linking + conflict layer on top of these rows**: matching code entities
> to business entities (Service/API/Team/Rule/Concept) and adding **`IMPLEMENTS`** edges
> (B's new `RelationshipType`, not added here). B reads code entities by `entity_type` and parses
> provenance from `description`/`name`; B does not need to re-parse source. **`IMPLEMENTS` and any
> code↔business conflict detection are entirely out of scope for this doc.**

---

## 10b. Integration Decision (Master) — code-claim emission

Resolved during Phase-4 integration review, reconciling this doc with the v1
linking/conflict doc (`phase5_code_business_linking.md`):

**Developer A's parser additionally emits and persists the "code-claim text" for
each `FUNCTION`/`CLASS` symbol** — the docstring + the leading comment block +
the signature/first-body-line snippet. The tree-sitter pass already has the full
AST and file text, so A is the cheapest, single producer; v1 (B) must NOT re-parse
source.

How it is persisted: each code symbol is also written as a `Chunk` row under a
synthetic per-repo document of `source_type = SourceType.CODE` (the value B
introduces). The chunk text = the code-claim text; it carries `file:line`. This:

- gives the code claim a real `embedding_id` in Qdrant, which **resolves B's §3.1
  "code-claim text has no embedding_id" issue** — the code-vs-doc conflict pass can
  reuse `_cosine_similarity_from_qdrant` unchanged instead of embedding on the fly;
- makes B's §3.3 "represent the code side as a real Chunk" fall out for free
  (B consumes these chunks rather than creating them);
- **requires the guard B flagged**: `SourceType.CODE` chunks MUST be excluded from
  normal RAG answer context (filter in `chat.py`) so raw code claims are never
  quoted back as documentation.

Ownership: A creates the `SourceType.CODE` document + code-claim Chunks during
`extract_code_graph_task`. B consumes them (linking + conflict). The
`SourceType.CODE` enum value is added once (B's doc §3.3 owns the enum edit; A
depends on it existing). This is the only cross-doc coupling beyond the entity/rel
enums.

## 11. Risks & Open Questions

- **Call-resolution accuracy.** tree-sitter sees lexical call sites, not types. Dynamic dispatch
  (`obj.method()`), getattr, decorators, and re-exports cannot be resolved structurally. v0.1
  resolves **intra-file** calls by name (high confidence) and emits cross-file/ambiguous calls at
  **reduced confidence**, or drops them. *Open: confidence threshold + whether to keep unresolved
  edges as dangling-by-name nodes.*
- **Cross-file edges (imports/inheritance).** A class inheriting from an imported base needs import
  resolution we don't have in v0.1. Plan: a lightweight import-map per file (`from x import Y`) to
  rewrite local names to `repo:path::symbol` before edge emission — feasible but deferred if it
  threatens scope.
- **Language coverage.** Python-only in v0.1; the grammar-per-language plan (§2) is the path, but
  query files for JS/TS/Go/etc. are real work and unwritten.
- **Graph bloat / false hubs.** Mitigated by namespacing (§8) and caps (§9), but very large monorepos
  may still need pruning heuristics.
- **Stale graph on re-ingest.** Namespaced names merge idempotently, but **deleted** symbols are not
  garbage-collected (the node lingers). *Open: a per-(repo,ref) reconciliation/delete pass — deferred
  to a later phase.*
- **Provenance as a string** (§5) — flagged for promotion to real columns post-merge.

---

## 12. v0.1 Scope Cut

**IN (this doc / Developer A):**
- tree-sitter **Python** structural parser → `pipelines/extraction/code_graph.py`.
- `MODULE` / `CLASS` / `FUNCTION` entities; `DEFINES` (new) + `CALLS` / `INHERITS` (existing) edges.
- `repo:path::symbol` namespacing; provenance in `description`.
- `extract_code_graph_task` wired parallel to `extract_entities_task`, GitHub-only.
- Reuse of `graph/sync.py`, Neo4j, Graph viz, copilot graph context — unchanged.
- Scale guards (§9).

**OUT (explicitly):**
- Code↔business linking and the `IMPLEMENTS` edge — **Developer B**.
- Code conflict detection — **Developer B**.
- Non-Python languages — **later phase** (path defined in §2).
- Provenance columns, deleted-symbol GC, configurable deny-lists — **later**.
```
