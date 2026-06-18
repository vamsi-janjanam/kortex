# Phase 5 (v1): CODE↔BUSINESS LINKING + CODE-VS-DOC CONFLICT + EVAL

**Author:** Developer Agent B
**Status:** Design — no implementation in this doc
**Depends on:** Developer Agent A's structural code graph (BLOCKING — see §7)

This is the "understanding" layer on top of Developer A's structural code graph. A
gives us code `Entity` rows (MODULE/CLASS/FUNCTION) with file:line provenance and
DEFINES/CALLS/INHERITS edges. This doc designs (1) linking those code symbols to
**business** entities via a new `IMPLEMENTS` edge, (2) detecting drift between what
the **code** does and what the **docs** say, by extending the existing
`ConflictDetector`, (3) surfacing both in the copilot, and (4) proving it with eval.

The honest framing up front: **the IMPLEMENTS linker is the genuinely uncertain
part of this design.** Code-to-intent mapping is hard, docstrings are sparse, and a
wrong link produces a wrong conflict, which erodes trust in Kortex's centerpiece
feature. The design leans on a confidence threshold and a precision-favoring
posture to manage that risk; see §2 and §8.

---

## 1. Goal & the money demo

Kortex's existing centerpiece is conflict detection proven by eval (doc-vs-doc
contradictions between `api_docs_v1.md` and `api_docs_v2.md`, judged by Claude).
Phase 5 extends that narrative from **doc-vs-doc** to **code-vs-policy**.

**The launch demo:**

> User asks the copilot: *"What enforces our data-retention policy?"*
>
> Kortex answers with the actual implementing function and its location —
> e.g. `billing/retention.py::purge_expired_documents` (file:line) — because that
> FUNCTION `IMPLEMENTS` the business Rule "data retention policy". **And** it warns:
> the code deletes documents after **30 days**, while the v2 policy doc says **7
> years**. That is a code-vs-doc conflict.

This is strictly more valuable than doc-vs-doc drift: it catches the case where the
documentation has been updated but the implementation has not (or vice versa) — the
single most expensive class of knowledge drift in a real org. It reuses the exact
machinery the team already trusts (entity extraction → Claude; conflict detection →
cosine + Claude judge → `Conflict` records → eval harness).

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Developer A (structural graph — INPUT, fixed contract)                     │
│  code Entity: FUNCTION "repo:billing/retention.py::purge_expired_documents" │
│      file:line provenance ──── DEFINES/CALLS/INHERITS edges (PG + Neo4j)    │
└───────────────────────────────┬────────────────────────────────────────────┘
                                 │  this doc's scope ▼
        ┌────────────────────────┴────────────────────────────────┐
        │ (2) IMPLEMENTS linker  pipelines/extraction/code_linker.py│
        │   for each code symbol:                                    │
        │     a) cheap candidate gen (name/keyword vs Entity names)  │
        │     b) Claude Haiku confirm → IMPLEMENTS edge + confidence │
        └────────────────────────┬───────────────────────────────────┘
                                  ▼
   FUNCTION ──IMPLEMENTS(conf=0.91)──▶ Rule "data retention policy"
                                  │                       ▲
                                  ▼                       │ same Rule described by
        ┌─────────────────────────────────────────────┐  │ doc chunks
        │ (3) code-vs-doc ConflictDetector extension    │  │
        │   code "claim" text (docstring/comment/body)  │──┘
        │     vs doc chunk(s) for that Rule             │
        │     cosine ≥ 0.85 + Haiku judge → Conflict    │
        └────────────────────────┬──────────────────────┘
                                  ▼
        ┌─────────────────────────────────────────────┐
        │ (4) Surfacing: chat.py graph_context +         │
        │     code-vs-doc conflict warning + file:line   │
        │ (5) Eval: code-vs-doc Q&A pairs, drift P/R     │
        └─────────────────────────────────────────────┘
```

---

## 2. The IMPLEMENTS linker

**New file:** `pipelines/extraction/code_linker.py` (mirrors
`pipelines/extraction/entity_extractor.py`). **New relationship type:** `IMPLEMENTS`
(see §3.2 for the enum change). An `IMPLEMENTS` edge points **from** a code Entity
(FUNCTION/CLASS/MODULE) **to** a business Entity (Rule/Service/API/Concept), e.g.
FUNCTION `...::purge_expired_documents` IMPLEMENTS Rule "data retention policy".

The contract is reused verbatim: `EntityRelationship` already has `from_entity_id`,
`to_entity_id`, `rel_type` (string, `default=OTHER`), and `confidence: float`
(`relationship_record.py:34-37`). We do **not** add columns — `confidence` is the
threshold lever.

### 2.1 Why hybrid (cheap candidate gen → LLM confirm)

A naive approach (ask Claude, for every code symbol, "which business entity does
this implement?" against the full business-entity list) is both expensive at repo
scale and low-precision. Instead, two stages:

**Stage (a) — cheap candidate generation (no LLM).** For each code symbol, build a
candidate set of business Entities by lexical matching, with zero API cost:

- **Symbol-name tokens.** Split the symbol part of `repo:path::symbol` on snake/camel
  boundaries (`purge_expired_documents` → {purge, expired, documents}; `RetentionJob`
  → {retention, job}).
- **Docstring + leading comments.** A's provenance gives us file:line; we read the
  function/class docstring and the comment block immediately above the definition.
- **Match** those tokens against business `Entity.name` and `Entity.description`
  (already in Postgres) using a normalized token-overlap / substring score. Keep the
  top-K (K≈5) business entities above a low lexical floor.
- Symbols with **no** candidate above the floor are skipped — no LLM call, no edge.
  (This is the dominant cost saver: most utility functions implement no business
  rule.)

This mirrors how `chat.py:_fetch_graph_context` already resolves entities — by
substring-matching known `Entity.name`s against text (`chat.py:60-68`). We reuse
that exact "names are the join key" pattern, just inverted (code text → entity
names instead of chunk text → entity names).

**Stage (b) — Claude Haiku confirmation.** For each (code symbol, candidate set)
pair, one Haiku call confirms which candidate(s) the symbol actually implements and
assigns a confidence. This mirrors `EntityExtractor` exactly: same client
construction (`anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))`,
`entity_extractor.py:28`), same model string `claude-haiku-4-5-20251001`
(`entity_extractor.py:27`), same JSON-only prompt with markdown-fence stripping and
defensive `except → empty` fallback (`entity_extractor.py:48-62`).

> Note on model choice: Phase 5 deliberately keeps Haiku 4.5 (`claude-haiku-4-5-20251001`)
> to match the existing extractor and conflict judge — this is consistent with the
> rest of the codebase. If link precision proves too low in eval (§6), the
> confirmation pass is the one place worth trying a stronger model
> (`claude-opus-4-8`); flag this as a tuning lever, not a v1 default.

Prompt shape (new constant `CODE_LINK_PROMPT` in `code_linker.py`):

```
You are linking a CODE SYMBOL to the BUSINESS ENTITY it implements.

Code symbol: {namespaced_symbol}     (e.g. repo:billing/retention.py::purge_expired_documents)
Docstring/comments:
{docstring_and_comments}
Signature / first lines of body:
{code_snippet}

Candidate business entities:
{numbered_candidates_with_type_and_description}

Which candidate(s), if any, does this symbol IMPLEMENT (i.e. it is the code that
enforces or carries out that rule/service/concept)? Return ONLY valid JSON:
{"links": [{"entity_name": "...", "confidence": 0.0-1.0, "reason": "one sentence"}]}
Return an empty list if the symbol implements none of them.
```

`entity_name` must match a candidate's name (validated against the candidate set on
the way back, exactly as `entity_extractor` validates relationship `from`/`to`
against extracted entity names, `entity_extractor.py:14-15`).

### 2.2 Confidence threshold & precision/recall tradeoff

- Persist an `EntityRelationship(rel_type=IMPLEMENTS, confidence=...)` **only when
  confidence ≥ THRESHOLD**. Proposed v1 default **THRESHOLD = 0.7** (tunable in
  `app/config.py` as `code_link_min_confidence`).
- **We deliberately favor precision over recall.** A false `IMPLEMENTS` link feeds a
  false code-vs-doc conflict (§3), and false conflicts erode trust in the feature
  that is Kortex's entire value proposition. Missing a link is a silent gap; a wrong
  link is a visible, trust-destroying error. So the threshold is set high and the
  candidate floor is conservative.
- The threshold is the dial: raise it to suppress false links (higher precision,
  lower recall); lower it to catch more implementing symbols. §6 makes "linker
  precision" a tracked metric so this dial is data-driven, not guessed.

### 2.3 Where it runs

A new Celery task `link_code_to_business_task(repo_id)` runs **after** A's code
graph is built for a repo (sequenced in `apps/api/app/tasks/ingestion.py` alongside
the existing `score_document_chunks_task`). It iterates A's code Entities, runs
stages (a)/(b), and upserts IMPLEMENTS edges into Postgres and Neo4j (same dual
write A and the existing graph use). Idempotent on (from_entity_id, to_entity_id,
rel_type).

---

## 3. Code-vs-doc conflict detection

### 3.1 Extend, don't reinvent

The existing `ConflictDetector` (`pipelines/scoring/conflict.py`) already does:
fetch two chunks → cosine similarity from Qdrant (`_cosine_similarity_from_qdrant`,
`conflict.py:72-91`) → if ≥ `SIMILARITY_THRESHOLD` (0.85, `conflict.py:21`) →
Haiku judge (`_judge_conflict`, `conflict.py:93-108`) → write `Conflict` row + bump
`conflict_risk` on both chunks (`conflict.py:57-67`). We **reuse this whole path**.

The only new question is: *what are the two things we compare for code-vs-doc?*

- **Side A (the "doc" claim):** the doc `Chunk`(s) that describe the business Rule —
  i.e. chunks whose text mentions the Rule's `Entity.name` (the same substring-match
  join `chat.py` and the linker use).
- **Side B (the "code" claim):** the code symbol's behavioral text — its docstring,
  leading comments, and a short signature/body snippet (the same text the linker
  already extracted in §2 stage (a)).

The trigger is **structural, not similarity-first**: we only attempt a code-vs-doc
comparison where an `IMPLEMENTS(conf ≥ THRESHOLD)` edge already exists. That edge
tells us the code symbol and the Rule are *supposed to be about the same thing*, so
the comparison is meaningful even if surface wording differs. We still apply the
existing cosine ≥ 0.85 + Haiku-judge gate **on the code-claim text vs each candidate
doc chunk** to filter and to reuse the trusted judging machinery.

New method on `ConflictDetector`:

```
detect_code_vs_doc(implements_edge, db) -> list[dict]:
  code_claim_text  = build_code_claim(edge.from_entity)   # docstring+comments+snippet
  rule_entity      = edge.to_entity
  doc_chunks       = chunks whose text contains rule_entity.name   # the doc side
  for doc_chunk in doc_chunks:
      embed code_claim_text (or reuse a cached code-claim embedding),
        cosine vs doc_chunk's Qdrant vector            # reuse _cosine_similarity_*
      if cosine >= SIMILARITY_THRESHOLD:
          result = self._judge_conflict(code_claim_text, doc_chunk.text)  # SAME judge
          if result.is_conflict:  -> create a code-vs-doc Conflict (see §3.3)
```

`_judge_conflict` is reused unchanged — its prompt asks "do these two excerpts
contradict?" which works identically whether excerpt A is doc text or code-claim
text (`conflict.py:8-19`). No prompt change required for v1.

> Embedding note (UPDATED per Master integration decision, see
> `phase5_semantic_code.md` §10b): Developer A now emits the code-claim text and
> persists each code symbol as a `Chunk` under a `SourceType.CODE` document during
> `extract_code_graph_task`. So the code claim **does** have a stored `embedding_id`,
> and this detector reuses `_cosine_similarity_from_qdrant` **unchanged** (both sides
> are real chunks) — no on-the-fly embedding and no extension needed. v1 (B) consumes
> these chunks; it does not create them or re-parse source.

### 3.2 Enum additions (the shared-contract change)

In `apps/api/app/models/relationship_record.py`, add to `RelationshipType`:

```python
IMPLEMENTS = "implements"
```

(placed alongside the existing values, `relationship_record.py:12-19`). This is the
only enum change the linker strictly needs. `EntityType` already has `RULE` etc.
(`entity.py:12-19`) — no change there; A adds MODULE/FUNCTION/CLASS.

### 3.3 Representing a code-vs-doc Conflict (minimal change)

The current `Conflict` model is **chunk_a/chunk_b based** — both FKs are
`NOT NULL` to `chunks.id` (`conflict.py:24-29`). A code claim is *not* a `Chunk`.
Two options were considered; v1 picks the minimal one.

**Chosen (v1): represent the code side as a real `Chunk`.**
Per the Master integration decision (`phase5_semantic_code.md` §10b), **Developer A
persists each code claim as a `Chunk` row of a synthetic "code" document
(`source_type = SourceType.CODE`)** during `extract_code_graph_task` — text = the
code-claim text, with file:line stored and a real `embedding_id` in Qdrant. This
layer (B) **consumes** those chunks; it does not create them. A code-vs-doc
`Conflict` is then just `chunk_a = code chunk`, `chunk_b = doc chunk` — **zero schema
change to `Conflict`**, full reuse of the existing `conflict_risk` bumping, the
conflicts list UI, and the eval harness's existing conflict plumbing.

To distinguish a code-vs-doc conflict from a doc-vs-doc one without a new column:
the `chunk_a` document's `source_type` is a new `SourceType.CODE` value (add to
`apps/api/app/models/document.py`, exactly per the CLAUDE.md "Adding a New Source
Connector" recipe). The chat/UI layer reads `source_type == CODE` on either chunk's
document to render the code-vs-doc badge and the file:line citation. This keeps the
`Conflict` model untouched and the meaning recoverable.

**Rejected (deferred): a `conflict_kind` enum + nullable code-symbol FK on
`Conflict`.** Cleaner long-term (no synthetic chunks), but it's a real schema +
migration + harness change and touches the model the eval depends on. Not worth it
for v1; revisit if synthetic code chunks pollute search/retrieval (they're filtered
out of normal RAG by `source_type` in `chat.py`'s post-filter — note this as a
required guard so code chunks never surface as answer context).

---

## 4. Surfacing

### 4.1 Copilot (`apps/api/app/api/v1/endpoints/chat.py`)

`chat.py` already folds graph relationships into the prompt via
`_fetch_graph_context` (`chat.py:41-111`) → `GRAPH_PREAMBLE` (`chat.py:27-31`) and
returns a `GraphContext` in the response (`chat.py:160-168, 246-257`). We extend
both:

1. **IMPLEMENTS edges in graph_context.** In `_fetch_graph_context`, the Neo4j query
   already pulls `RELATES_TO` edges (`chat.py:84-92`), returning only
   `source`/`target`/`rel_type`. Extend that query to also return IMPLEMENTS edges
   where a matched business Entity is the target, carrying the code symbol's name and
   file:line. **Note:** file:line is not currently a queryable field on the edge or
   node — it lives inside `Entity.description` (`code: repo:path:line @ref`, A §5), so
   this extension must either parse it out of the synced `description` or wait for the
   provenance-columns promotion A flagged (§5/§11). These render in `GRAPH_PREAMBLE` as
   lines like
   `- <Rule> is implemented by <symbol> (path:line)` so the model can answer "what
   enforces X" with the actual function and location.

2. **Code-vs-doc conflict warning.** When a retrieved/relevant doc chunk (or the
   matched Rule's doc chunk) participates in a code-vs-doc `Conflict` (look up
   `Conflict` rows where one side's document is `source_type == CODE`), inject a
   warning block into the prompt and add it to the response so the answer says, e.g.,
   *"⚠️ The code (`...::purge_expired_documents`, retention.py:42) deletes after 30
   days, but the policy doc says 7 years."* Reuse the existing best-effort/degrade
   pattern (`chat.py:72-74, 107-111`): any PG/Neo4j failure → omit the warning, never
   500.

3. **Response shape.** Add `code_links: list[{rule, symbol, file, line, confidence}]`
   and `code_doc_conflicts: list[{symbol, file, line, doc_text, description,
   confidence}]` to `ChatResponse` (alongside `graph_context`, `chat.py:165-168`).
   The existing `conflict_risk` post-filter (`chat.py:212`) is unchanged for doc
   chunks; code chunks are excluded from answer context (§3.3 guard).

### 4.2 Graph page (`apps/web/src/app/`)

The Graph page already renders entity relationships. Add:

- A distinct visual style for `IMPLEMENTS` edges (code → business), with code nodes
  badged by file:line and clickable to the source location.
- A "drift" indicator on any business entity that has an open code-vs-doc `Conflict`,
  linking into the existing conflicts view. This makes the demo's "policy says 7y,
  code does 30d" visible on the graph, not just in chat.

---

## 5. Eval

### 5.1 Approach

The seed corpus's conflicts (auth, rate limits, data retention, PDF, SDKs) are
**doc-vs-doc** today. For Phase 5 we **seed CODE that contradicts the v2 doc** so the
same conflicts become code-vs-policy. Concretely: add small synthetic Python files to
the seed corpus (e.g. `data/seed_corpus/code/`) whose docstrings/behavior contradict
`api_docs_v2.md`, plus business Rule entities they implement. Ingest them via the new
`SourceType.CODE` path so the linker + code-vs-doc detector run over them.

### 5.2 Proposed eval Q&A pairs

These follow the exact `qa_pairs.json` shape (`data/eval_qa_pairs/qa_pairs.json`)
with `has_seeded_conflict: true`. Add to the same file so the existing harness picks
them up.

```json
[
  {
    "id": "q031",
    "question": "What enforces our data-retention policy, and does the code match the policy?",
    "reference_answer": "purge_expired_documents (retention.py) implements the data-retention policy but deletes documents after 30 days, contradicting the v2 policy of 7 years.",
    "has_seeded_conflict": true,
    "notes": "code-vs-doc: seeded retention.py uses 30 days; api_docs_v2 says 7 years"
  },
  {
    "id": "q032",
    "question": "How does the code authenticate API requests?",
    "reference_answer": "The auth middleware still validates static API keys, which contradicts the v2 docs requiring OAuth 2.0 JWT bearer tokens.",
    "has_seeded_conflict": true,
    "notes": "code-vs-doc: seeded auth.py checks api_key; v2 doc says OAuth 2.0 JWT"
  },
  {
    "id": "q033",
    "question": "What rate limit does the code enforce for the Pro tier?",
    "reference_answer": "The rate limiter hard-codes 50 req/min for all tiers, contradicting the v2 docs (1,000 req/min for Pro).",
    "has_seeded_conflict": true,
    "notes": "code-vs-doc: seeded ratelimit.py uses 50/min; v2 doc tiers differ"
  },
  {
    "id": "q034",
    "question": "Does the upload handler support PDF documents?",
    "reference_answer": "The upload handler rejects PDF (allows only text/markdown), contradicting v2 docs which add PDF support.",
    "has_seeded_conflict": true,
    "notes": "code-vs-doc: seeded uploads.py whitelist excludes pdf; v2 doc adds PDF"
  },
  {
    "id": "q035",
    "question": "Which SDKs does the client factory actually build?",
    "reference_answer": "The client factory only constructs the Python SDK, contradicting v2 docs which list 4 official SDKs.",
    "has_seeded_conflict": true,
    "notes": "code-vs-doc: seeded sdk_factory.py builds python only; v2 doc lists 4"
  }
]
```

### 5.3 Headline metric

Define **code-vs-doc drift detection precision/recall** as the new headline metric,
parallel to the existing conflict eval:

- **Recall** = (seeded code-vs-doc conflicts correctly flagged) / (total seeded
  code-vs-doc conflicts). The 5 pairs above are the labeled positive set.
- **Precision** = (correctly flagged) / (all flagged). Add code-vs-doc-clean pairs
  (code that *agrees* with the docs) as the negative set to measure false positives —
  critical given the false-positive risk in §8.

The harness already compares raw vs. cleaned retrieval and uses Claude as judge
(`pipelines/eval/harness.py`); extend its conflict-counting to read the new
code-vs-doc `Conflict`s (identifiable via `source_type == CODE`, §3.3) and report
the drift P/R alongside the existing table.

---

## 6. Success metrics

1. **Linker precision** — of sampled IMPLEMENTS edges (conf ≥ threshold), fraction
   that are correct on manual/eval spot-check. Primary trust gate; target high
   (favor precision, §2.2).
2. **Code-vs-doc conflict precision/recall** — §5.3 headline; the launch number.
3. **Rule coverage** — % of business Rules that have ≥1 IMPLEMENTS edge to a code
   symbol. Measures how much of the policy surface is grounded in code (recall-side
   health of the linker).
4. **Demo integrity** — the data-retention question returns the correct function +
   file:line AND the 30d-vs-7y warning, deterministically.

---

## 7. Dependencies & sequencing

**BLOCKED on Developer A's structural code graph.** From A, this design requires:

- Code `Entity` rows of type MODULE/FUNCTION/CLASS, named `repo:path::symbol`, in
  Postgres (so the linker can iterate them and so IMPLEMENTS FKs resolve).
- **file:line provenance** per code Entity (needed to read docstrings/comments for
  the candidate gen + code-claim text, and to cite locations in chat/graph).
- The same dual Postgres+Neo4j write pattern for edges, so IMPLEMENTS edges land in
  both stores like DEFINES/CALLS/INHERITS.
- A's confirmation that adding `RelationshipType.IMPLEMENTS` (§3.2) is the agreed
  shared contract (A stated it is ours to design — this doc fixes its value to
  `"implements"`).

**Sequencing within Phase 5 (after A lands):**

1. Add `IMPLEMENTS` enum + `SourceType.CODE` + config `code_link_min_confidence`.
2. Build `code_linker.py` (candidate gen → Haiku confirm → edges).
3. Extend `ConflictDetector` with `detect_code_vs_doc`.
4. Wire `link_code_to_business_task` into ingestion sequencing.
5. Surface in `chat.py` + Graph page.
6. Seed contradicting code + add q031–q035; extend harness reporting.

---

## 8. Risks & open questions

- **Linker precision is the core uncertainty.** Code→intent is genuinely hard. A
  function named `cleanup()` may implement retention with no lexical signal; a
  function named `validate_retention()` may just be a helper. The candidate-floor +
  Haiku-confirm + high threshold mitigate but don't eliminate this. **This is the
  part most likely to need iteration after first eval.**
- **False conflicts erode trust.** A wrong IMPLEMENTS link → a confident-but-wrong
  code-vs-doc conflict on Kortex's flagship feature. Precision-first posture (§2.2),
  a negative eval set (§5.3), and conservative thresholds are the defenses.
- **Docstring/comment sparsity.** Real code often has no docstring. With only a
  symbol name and signature, both candidate gen and the judge degrade. Open question:
  fall back to a body-snippet summary, or simply skip (no link) when signal is below
  a floor? v1 skips (favors precision); revisit.
- **LLM cost at repo scale.** One Haiku call per (symbol with candidates). The
  candidate-floor skip keeps the call count to symbols that plausibly implement a
  rule, but a large repo could still be thousands of calls. Mitigations to consider:
  batch candidates per symbol into one call (already the design), cache by symbol
  content hash, and only re-link changed symbols on re-ingest.
- **Synthetic code chunks in the vector store** (the §3.3 v1 choice) must be excluded
  from RAG answer context, or the copilot could quote raw code claims as if they were
  docs. Required guard; flagged.
- **Embedding of code-claim text — RESOLVED** (Master decision, see §3.1/§3.3):
  Developer A persists code claims as `SourceType.CODE` chunks with stored Qdrant
  vectors, so this layer reuses `_cosine_similarity_from_qdrant` unchanged — no
  on-the-fly embedding. (Left here only to note the earlier open question is closed.)

---

## 9. Scope cut

**v1 IN:**
- Python only.
- `IMPLEMENTS` linking (candidate gen + Haiku confirm + confidence threshold).
- Code-vs-doc conflict detection extending `ConflictDetector` (cosine + same Haiku
  judge), represented via synthetic code `Chunk` + `SourceType.CODE` (no `Conflict`
  schema change).
- Surfacing in `chat.py` (IMPLEMENTS + drift warning + file:line) and the Graph page.
- 5 code-vs-doc eval pairs (q031–q035) + drift precision/recall headline metric.

**v1 OUT (explicitly deferred):**
- Multi-language linking (JS/TS/Go/etc.).
- Full semantic-equivalence checking (proving code *correctly* implements a rule,
  not just whether its stated claims contradict the doc). v1 only compares *claims*
  (docstring/comment/snippet text vs doc text), not actual runtime behavior.
- `conflict_kind` enum + first-class code-symbol FK on `Conflict` (the cleaner
  representation; deferred to avoid a schema/migration/harness change in v1).
- Auto-resolution / suggesting which side (code or doc) is correct.
- Linking to non-Rule business entities beyond best-effort (Service/API/Concept are
  candidate-eligible but the demo and metrics center on Rules).
```
