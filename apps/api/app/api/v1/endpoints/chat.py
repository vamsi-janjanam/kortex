import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.models import Chunk, Document

router = APIRouter()

ANSWER_PROMPT = """You are Kortex, a helpful assistant answering questions about the user's knowledge base. \
Answer the question using ONLY the provided context. If the context doesn't contain enough information, say "I don't know."

Context:
{context}

Question: {question}

Answer:"""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    top_k: int = 5
    min_freshness: float = 0.3
    max_conflict_risk: float = 0.7


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


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        from openai import OpenAI
        from qdrant_client import QdrantClient

        oai = OpenAI(api_key=settings.openai_api_key)
        embedding_response = oai.embeddings.create(
            model=settings.embedding_model, input=payload.message
        )
        query_vector = embedding_response.data[0].embedding
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Embedding service unavailable: {e}"
        ) from e

    try:
        qc = QdrantClient(url=settings.qdrant_url)
        hits = qc.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=payload.top_k * 3,  # oversample for post-filtering
        )
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Vector search unavailable: {e}"
        ) from e

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

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        context = "\n\n---\n\n".join(s.text for s in sources)
        messages = [{"role": m.role, "content": m.content} for m in payload.history]
        messages.append(
            {
                "role": "user",
                "content": ANSWER_PROMPT.format(
                    context=context, question=payload.message
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
        raise HTTPException(
            status_code=503, detail=f"Answer generation unavailable: {e}"
        ) from e

    return ChatResponse(answer=answer, sources=sources)
