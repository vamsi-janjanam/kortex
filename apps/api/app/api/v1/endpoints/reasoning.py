import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.core.security import limiter
from app.models import BusinessRule, BusinessRuleEntityLink, Chunk, Conflict, Entity

logger = logging.getLogger(__name__)

router = APIRouter()

REASONING_PROMPT = """You are Kortex, a reasoning assistant that explains the \
*business logic* behind the user's knowledge base. Do not just retrieve facts — \
explain the WHY: which business rules apply, the rationale behind them, and how \
they lead to the answer. Cite the business rules that support your answer by name. \
If conflicting information exists, you MUST explicitly call out the conflict rather \
than hiding it — prefer rules with status "active" and newer information over \
superseded or stale ones, and say so. If nothing relevant is provided, say "I don't know."

Context:
{context}

Business rules:
{rules}

Known conflicts:
{conflicts}

Question: {question}

Answer:"""

# Cap on how many business rules we surface into the prompt / response.
MAX_BUSINESS_RULES = 10
# Words shorter than this are treated as noise for ILIKE matching.
MIN_KEYWORD_LENGTH = 4


def _significant_words(question: str) -> list[str]:
    """Pull longer alphabetic tokens from the question for ILIKE matching."""
    words = re.findall(r"[A-Za-z]{%d,}" % MIN_KEYWORD_LENGTH, question)
    # De-dupe while preserving order; lowercase for stable matching.
    seen: dict[str, None] = {}
    for word in words:
        seen.setdefault(word.lower(), None)
    return list(seen.keys())


def _fetch_business_rules(
    db: Session, chunk_ids: list[uuid.UUID], question: str
) -> list[BusinessRule]:
    """Find business rules tied to the retrieved chunks or matching the question.

    Combines provenance (rules whose ``source_chunk_id`` is among the retrieved
    chunks) with keyword recall (rules whose ``name``/``statement`` ILIKE any
    significant word of the question), de-duped and capped at
    :data:`MAX_BUSINESS_RULES`.
    """
    conditions = []
    if chunk_ids:
        conditions.append(BusinessRule.source_chunk_id.in_(chunk_ids))
    for word in _significant_words(question):
        pattern = f"%{word}%"
        conditions.append(BusinessRule.name.ilike(pattern))
        conditions.append(BusinessRule.statement.ilike(pattern))

    if not conditions:
        return []

    rows = db.execute(select(BusinessRule).where(or_(*conditions))).scalars().all()

    # De-dupe (a rule can match on multiple conditions) and cap.
    deduped: dict[uuid.UUID, BusinessRule] = {}
    for rule in rows:
        deduped.setdefault(rule.id, rule)
        if len(deduped) >= MAX_BUSINESS_RULES:
            break
    return list(deduped.values())


def _fetch_governed_rules(db: Session, chunk_texts: list[str]) -> list[BusinessRule]:
    """Multi-hop: chunk -> entity -> governing business rule.

    Substring-matches known entity names (from Postgres) against the retrieved
    chunk text, then pulls every :class:`BusinessRule` linked to a matched
    entity via :class:`BusinessRuleEntityLink`. This surfaces rules that govern
    entities mentioned in the chunks even when no rule was provenance- or
    keyword-matched directly.

    Best-effort: any lookup failure returns ``[]`` and the caller degrades to
    the directly-matched rules. Mirrors ``chat.py:_fetch_graph_context``.
    """
    if not chunk_texts:
        return []

    try:
        haystack = "\n".join(chunk_texts).lower()
        matched_ids: list[uuid.UUID] = []
        rows = db.execute(select(Entity.id, Entity.name)).all()
        for entity_id, name in rows:
            if name and name.lower() in haystack:
                matched_ids.append(entity_id)

        if not matched_ids:
            return []

        rules = (
            db.execute(
                select(BusinessRule)
                .join(
                    BusinessRuleEntityLink,
                    BusinessRuleEntityLink.business_rule_id == BusinessRule.id,
                )
                .where(BusinessRuleEntityLink.entity_id.in_(matched_ids))
            )
            .scalars()
            .all()
        )

        deduped: dict[uuid.UUID, BusinessRule] = {}
        for rule in rules:
            deduped.setdefault(rule.id, rule)
            if len(deduped) >= MAX_BUSINESS_RULES:
                break
        return list(deduped.values())
    except Exception:
        logger.warning(
            "Governed-rule lookup failed, falling back to direct rules", exc_info=True
        )
        return []


def _fetch_conflicts(db: Session, chunk_ids: list[uuid.UUID]) -> list[Conflict]:
    """Find open conflicts touching any of the retrieved chunks.

    For reasoning we *want* to surface conflicts, so we keep conflicted chunks
    and pull every open :class:`Conflict` where either endpoint is among the
    retrieved chunk ids.
    """
    if not chunk_ids:
        return []
    return (
        db.execute(
            select(Conflict).where(
                or_(
                    Conflict.chunk_a_id.in_(chunk_ids),
                    Conflict.chunk_b_id.in_(chunk_ids),
                ),
                Conflict.status == "open",
            )
        )
        .scalars()
        .all()
    )


class ReasoningRequest(BaseModel):
    question: str = Field(..., max_length=4000)
    top_k: int = 5
    min_freshness: float = 0.3


class CitedRule(BaseModel):
    name: str
    rule_type: str
    statement: str
    rationale: str | None
    status: str


class ConflictNote(BaseModel):
    description: str | None
    confidence: float


class ReasoningResponse(BaseModel):
    answer: str
    cited_rules: list[CitedRule]
    conflicts: list[ConflictNote]


@router.post("/ask", response_model=ReasoningResponse)
@limiter.limit("20/minute")
def ask(request: Request, payload: ReasoningRequest, db: Session = Depends(get_db)):
    try:
        from openai import OpenAI
        from qdrant_client import QdrantClient

        oai = OpenAI(api_key=settings.openai_api_key)
        embedding_response = oai.embeddings.create(
            model=settings.embedding_model, input=payload.question
        )
        query_vector = embedding_response.data[0].embedding
    except Exception as e:
        logger.exception("Embedding service failed during reasoning")
        raise HTTPException(
            status_code=503, detail="Embedding service unavailable"
        ) from e

    try:
        qc = QdrantClient(url=settings.qdrant_url)
        hits = qc.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=payload.top_k * 3,  # oversample for post-filtering
        )
    except Exception as e:
        logger.exception("Vector search failed during reasoning")
        raise HTTPException(status_code=503, detail="Vector search unavailable") from e

    # Resolve chunks; filter on freshness only — we deliberately KEEP conflicted
    # chunks so the reasoning step can surface the conflict.
    chunks: list[Chunk] = []
    for hit in hits:
        chunk_id = uuid.UUID(hit.payload.get("chunk_id", "")) if hit.payload else None
        if not chunk_id:
            continue

        chunk = db.get(Chunk, chunk_id)
        if not chunk:
            continue

        if chunk.freshness_score < payload.min_freshness:
            continue

        chunks.append(chunk)

        if len(chunks) >= payload.top_k:
            break

    if not chunks:
        return ReasoningResponse(
            answer="I don't know (no relevant context found).",
            cited_rules=[],
            conflicts=[],
        )

    chunk_ids = [c.id for c in chunks]
    rules = _fetch_business_rules(db, chunk_ids, payload.question)

    # Multi-hop: fold in rules governing entities mentioned in the chunks,
    # de-duped against the directly-matched rules and capped overall.
    governed = _fetch_governed_rules(db, [c.text for c in chunks])
    merged: dict[uuid.UUID, BusinessRule] = {r.id: r for r in rules}
    for rule in governed:
        if len(merged) >= MAX_BUSINESS_RULES:
            break
        merged.setdefault(rule.id, rule)
    rules = list(merged.values())

    conflicts = _fetch_conflicts(db, chunk_ids)

    cited_rules = [
        CitedRule(
            name=r.name,
            rule_type=r.rule_type,
            statement=r.statement,
            rationale=r.rationale,
            status=r.status,
        )
        for r in rules
    ]
    conflict_notes = [
        ConflictNote(description=c.description, confidence=c.confidence_score)
        for c in conflicts
    ]

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        context = "\n\n---\n\n".join(c.text for c in chunks)
        if rules:
            rules_section = "\n".join(
                f"- {r.name} — {r.statement}"
                + (f" (why: {r.rationale})" if r.rationale else "")
                + f" [status: {r.status}]"
                for r in rules
            )
        else:
            rules_section = "(none found)"
        if conflicts:
            conflicts_section = "\n".join(
                f"- {c.description or 'conflicting information'}" for c in conflicts
            )
        else:
            conflicts_section = "(none found)"

        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": REASONING_PROMPT.format(
                        context=context,
                        rules=rules_section,
                        conflicts=conflicts_section,
                        question=payload.question,
                    ),
                }
            ],
        )
        answer = response.content[0].text.strip()
    except Exception as e:
        logger.exception("Answer generation failed during reasoning")
        raise HTTPException(
            status_code=503, detail="Answer generation unavailable"
        ) from e

    return ReasoningResponse(
        answer=answer, cited_rules=cited_rules, conflicts=conflict_notes
    )
