import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Chunk, Document

router = APIRouter()


class DocumentCreate(BaseModel):
    source_type: str
    source_url: str
    title: str | None = None
    extra_metadata: dict | None = None
    trigger_ingest: bool = True


class DocumentResponse(BaseModel):
    id: uuid.UUID
    source_type: str
    source_url: str
    title: str | None
    ingested_at: datetime
    chunk_count: int = 0

    model_config = {"from_attributes": True}


@router.get("", response_model=list[DocumentResponse])
def list_documents(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    docs = db.execute(select(Document).offset(skip).limit(limit)).scalars().all()
    result = []
    for doc in docs:
        chunk_count = db.execute(
            select(func.count()).where(Chunk.document_id == doc.id)
        ).scalar_one()
        result.append(
            DocumentResponse(
                id=doc.id,
                source_type=doc.source_type,
                source_url=doc.source_url,
                title=doc.title,
                ingested_at=doc.ingested_at,
                chunk_count=chunk_count,
            )
        )
    return result


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    doc = Document(
        source_type=payload.source_type,
        source_url=payload.source_url,
        title=payload.title,
        extra_metadata=payload.extra_metadata,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    if payload.trigger_ingest:
        from app.tasks.ingestion import ingest_document_task

        ingest_document_task.delay(str(doc.id))

    return DocumentResponse(
        id=doc.id,
        source_type=doc.source_type,
        source_url=doc.source_url,
        title=doc.title,
        ingested_at=doc.ingested_at,
        chunk_count=0,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunk_count = db.execute(
        select(func.count()).where(Chunk.document_id == doc.id)
    ).scalar_one()
    return DocumentResponse(
        id=doc.id,
        source_type=doc.source_type,
        source_url=doc.source_url,
        title=doc.title,
        ingested_at=doc.ingested_at,
        chunk_count=chunk_count,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
