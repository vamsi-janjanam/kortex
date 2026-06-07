from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Chunk, Conflict, ConflictStatus, Document

router = APIRouter()


class KnowledgeStats(BaseModel):
    document_count: int
    chunk_count: int
    open_conflict_count: int
    avg_freshness_score: float
    avg_trust_score: float
    avg_conflict_risk: float
    coverage_pct: float


@router.get("", response_model=KnowledgeStats)
def get_stats(db: Session = Depends(get_db)):
    doc_count = db.execute(select(func.count()).select_from(Document)).scalar_one()
    chunk_count = db.execute(select(func.count()).select_from(Chunk)).scalar_one()
    conflict_count = db.execute(
        select(func.count()).where(Conflict.status == ConflictStatus.OPEN)
    ).scalar_one()

    if chunk_count > 0:
        avg_freshness = db.execute(select(func.avg(Chunk.freshness_score))).scalar_one() or 0.0
        avg_trust = db.execute(select(func.avg(Chunk.trust_score))).scalar_one() or 0.0
        avg_conflict_risk = db.execute(select(func.avg(Chunk.conflict_risk))).scalar_one() or 0.0
    else:
        avg_freshness = avg_trust = avg_conflict_risk = 0.0

    # Simple coverage heuristic: ratio of chunks with trust_score >= 0.7
    if chunk_count > 0:
        high_quality = db.execute(
            select(func.count()).where(Chunk.trust_score >= 0.7)
        ).scalar_one()
        coverage_pct = round(high_quality / chunk_count * 100, 1)
    else:
        coverage_pct = 0.0

    return KnowledgeStats(
        document_count=doc_count,
        chunk_count=chunk_count,
        open_conflict_count=conflict_count,
        avg_freshness_score=round(float(avg_freshness), 3),
        avg_trust_score=round(float(avg_trust), 3),
        avg_conflict_risk=round(float(avg_conflict_risk), 3),
        coverage_pct=coverage_pct,
    )


@router.get("/conflicts")
def list_conflicts(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    from app.models import Conflict
    from sqlalchemy import select

    conflicts = (
        db.execute(
            select(Conflict)
            .where(Conflict.status == ConflictStatus.OPEN)
            .order_by(Conflict.confidence_score.desc())
            .offset(skip)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(c.id),
            "chunk_a_id": str(c.chunk_a_id),
            "chunk_b_id": str(c.chunk_b_id),
            "description": c.description,
            "confidence_score": c.confidence_score,
            "detected_at": c.detected_at.isoformat(),
        }
        for c in conflicts
    ]
