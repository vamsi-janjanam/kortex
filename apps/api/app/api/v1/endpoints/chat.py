import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.core.security import limiter
from app.models import Chunk, Document

logger = logging.getLogger(__name__)

router = APIRouter()

ANSWER_PROMPT = """You are Kortex, a helpful assistant answering questions about the user's knowledge base. \
Answer the question using ONLY the provided context. If the context doesn't contain enough information, say "I don't know."

Context:
{context}
{graph_section}
Question: {question}

Answer:"""

GRAPH_PREAMBLE = """
Knowledge graph relationships (use these to make your answer graph-aware, \
explaining how entities relate, e.g. "X relates to Y"):
{relationships}
"""


# Entities are global and name-keyed (no document/chunk link exists), so we
# resolve graph context by detecting which known entity names appear in the
# retrieved chunk text, then pulling their relationships from Neo4j.
MAX_GRAPH_ENTITIES = 15
MAX_GRAPH_RELATIONSHIPS = 30


def _fetch_graph_context(db: Session, chunk_texts: list[str]) -> dict | None:
    """Look up entities + RELATES_TO relationships mentioned in retrieved chunks.

    Entities are name-keyed and global: we substring-match known entity names
    (from Postgres) against the retrieved chunk content, then resolve their
    relationships from Neo4j by entity ``id``.

    Best-effort: any Postgres OR Neo4j failure returns ``None`` and the caller
    degrades to plain RAG. Mirrors the defensive guarding in
    ``endpoints/graph.py`` and ``agents/retrieval.py``.
    """
    if not chunk_texts:
        return None

    try:
        from sqlalchemy import select

        from app.models import Entity

        haystack = "\n".join(chunk_texts).lower()
        # Pull candidate entity names from Postgres (cheap, always available).
        matched: dict[str, str] = {}  # entity id -> name
        rows = db.execute(select(Entity.id, Entity.name)).all()
        for entity_id, name in rows:
            if name and name.lower() in haystack:
                matched[str(entity_id)] = name
            if len(matched) >= MAX_GRAPH_ENTITIES:
                break

        if not matched:
            return None
    except Exception:
        logger.warning("Entity lookup failed, falling back to plain RAG", exc_info=True)
        return None

    try:
        from app.core.neo4j_client import get_neo4j_driver

        driver = get_neo4j_driver()
        relationships: list[dict] = []
        entity_ids = list(matched.keys())
        with driver.session() as session:
            # Relationships where at least one endpoint is a mentioned entity.
            rel_records = session.run(
                "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
                "WHERE a.id IN $entity_ids OR b.id IN $entity_ids "
                "RETURN a.name AS source, b.name AS target, "
                "r.rel_type AS rel_type "
                "LIMIT $limit",
                entity_ids=entity_ids,
                limit=MAX_GRAPH_RELATIONSHIPS,
            )
            for record in rel_records:
                if record["source"] and record["target"]:
                    relationships.append(
                        {
                            "source": record["source"],
                            "target": record["target"],
                            "type": record["rel_type"] or "relates to",
                        }
                    )

        return {
            "entities": sorted(set(matched.values())),
            "relationships": relationships,
        }
    except Exception:
        logger.warning(
            "Graph context unavailable, falling back to plain RAG", exc_info=True
        )
        return None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=4000)
    history: list[ChatMessage] = []
    top_k: int = 5
    min_freshness: float = 0.3
    max_conflict_risk: float = 0.7

    @field_validator("history")
    @classmethod
    def _cap_history(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if len(v) > settings.max_chat_history_messages:
            raise ValueError(
                f"history exceeds maximum of {settings.max_chat_history_messages} messages"
            )
        return v


class ChatSource(BaseModel):
    chunk_id: uuid.UUID
    text: str
    score: float
    freshness_score: float
    trust_score: float
    conflict_risk: float
    hallucination_risk: float
    document_id: uuid.UUID
    document_title: str | None
    source_type: str
    source_url: str


class GraphEntity(BaseModel):
    name: str


class GraphRelationship(BaseModel):
    source: str
    target: str
    type: str


class GraphContext(BaseModel):
    entities: list[str]
    relationships: list[GraphRelationship]


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    graph_context: GraphContext | None = None


@router.post("", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(request: Request, payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        from openai import OpenAI
        from qdrant_client import QdrantClient

        oai = OpenAI(api_key=settings.openai_api_key)
        embedding_response = oai.embeddings.create(
            model=settings.embedding_model, input=payload.message
        )
        query_vector = embedding_response.data[0].embedding
    except Exception as e:
        logger.exception("Embedding service failed during chat")
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
        logger.exception("Vector search failed during chat")
        raise HTTPException(status_code=503, detail="Vector search unavailable") from e

    sources: list[ChatSource] = []
    for hit in hits:
        chunk_id = uuid.UUID(hit.payload.get("chunk_id", "")) if hit.payload else None
        if not chunk_id:
            continue

        chunk = db.get(Chunk, chunk_id)
        if not chunk:
            continue

        if chunk.freshness_score < payload.min_freshness:
            continue
        if chunk.conflict_risk > payload.max_conflict_risk:
            continue

        doc = db.get(Document, chunk.document_id)
        if not doc:
            continue

        sources.append(
            ChatSource(
                chunk_id=chunk.id,
                text=chunk.text,
                score=hit.score,
                freshness_score=chunk.freshness_score,
                trust_score=chunk.trust_score,
                conflict_risk=chunk.conflict_risk,
                hallucination_risk=chunk.hallucination_risk,
                document_id=doc.id,
                document_title=doc.title,
                source_type=doc.source_type,
                source_url=doc.source_url,
            )
        )

        if len(sources) >= payload.top_k:
            break

    if not sources:
        return ChatResponse(
            answer="I don't know (no relevant context found).", sources=[]
        )

    # Graph-aware step: fold entity-relationship context from Neo4j into the
    # prompt so answers can explain how entities relate. Best-effort — if Neo4j
    # is unavailable this returns None and we answer as plain RAG.
    graph = _fetch_graph_context(db, [s.text for s in sources])
    graph_context: GraphContext | None = None
    graph_section = ""
    if graph and graph["relationships"]:
        rel_lines = "\n".join(
            f"- {r['source']} {r['type']} {r['target']}" for r in graph["relationships"]
        )
        graph_section = GRAPH_PREAMBLE.format(relationships=rel_lines)
        graph_context = GraphContext(
            entities=graph["entities"],
            relationships=[GraphRelationship(**r) for r in graph["relationships"]],
        )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        context = "\n\n---\n\n".join(s.text for s in sources)
        messages = [{"role": m.role, "content": m.content} for m in payload.history]
        messages.append(
            {
                "role": "user",
                "content": ANSWER_PROMPT.format(
                    context=context,
                    graph_section=graph_section,
                    question=payload.message,
                ),
            }
        )
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=512,
            messages=messages,
        )
        answer = response.content[0].text.strip()
    except Exception as e:
        logger.exception("Answer generation failed during chat")
        raise HTTPException(
            status_code=503, detail="Answer generation unavailable"
        ) from e

    return ChatResponse(answer=answer, sources=sources, graph_context=graph_context)
