import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.models import Chunk, Document

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    min_freshness: float = 0.0
    max_conflict_risk: float = 1.0
    source_types: list[str] | None = None


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    text: str
    score: float
    freshness_score: float
    trust_score: float
    conflict_risk: float
    document_id: uuid.UUID
    document_title: str | None
    source_type: str
    source_url: str


@router.post("", response_model=list[SearchResult])
def search(payload: SearchRequest, db: Session = Depends(get_db)):
    try:
        from openai import OpenAI
        from qdrant_client import QdrantClient

        oai = OpenAI(api_key=settings.openai_api_key)
        embedding_response = oai.embeddings.create(
            model=settings.embedding_model, input=payload.query
        )
        query_vector = embedding_response.data[0].embedding
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Embedding service unavailable: {e}") from e

    try:
        qc = QdrantClient(url=settings.qdrant_url)
        hits = qc.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=payload.top_k * 3,  # oversample for post-filtering
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Vector search unavailable: {e}") from e

    results = []
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
        if payload.source_types and doc.source_type not in payload.source_types:
            continue

        results.append(SearchResult(
            chunk_id=chunk.id,
            text=chunk.text,
            score=hit.score,
            freshness_score=chunk.freshness_score,
            trust_score=chunk.trust_score,
            conflict_risk=chunk.conflict_risk,
            document_id=doc.id,
            document_title=doc.title,
            source_type=doc.source_type,
            source_url=doc.source_url,
        ))

        if len(results) >= payload.top_k:
            break

    return results
