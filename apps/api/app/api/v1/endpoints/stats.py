from datetime import date, datetime, timedelta, timezone

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
    avg_hallucination_risk: float
    coverage_pct: float


@router.get("", response_model=KnowledgeStats)
def get_stats(db: Session = Depends(get_db)):
    doc_count = db.execute(select(func.count()).select_from(Document)).scalar_one()
    chunk_count = db.execute(select(func.count()).select_from(Chunk)).scalar_one()
    conflict_count = db.execute(
        select(func.count()).where(Conflict.status == ConflictStatus.OPEN)
    ).scalar_one()

    if chunk_count > 0:
        avg_freshness = (
            db.execute(select(func.avg(Chunk.freshness_score))).scalar_one() or 0.0
        )
        avg_trust = db.execute(select(func.avg(Chunk.trust_score))).scalar_one() or 0.0
        avg_conflict_risk = (
            db.execute(select(func.avg(Chunk.conflict_risk))).scalar_one() or 0.0
        )
        avg_hallucination_risk = (
            db.execute(select(func.avg(Chunk.hallucination_risk))).scalar_one() or 0.0
        )
    else:
        avg_freshness = avg_trust = avg_conflict_risk = avg_hallucination_risk = 0.0

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
        avg_hallucination_risk=round(float(avg_hallucination_risk), 3),
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


class ConflictTrendPoint(BaseModel):
    date: str
    detected: int
    closed: int


class ConflictTrendResponse(BaseModel):
    days: int
    data: list[ConflictTrendPoint]


@router.get("/conflicts/trend", response_model=ConflictTrendResponse)
def get_conflicts_trend(days: int = 30, db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)

    detected_rows = db.execute(
        select(func.date(Conflict.detected_at), func.count())
        .where(func.date(Conflict.detected_at) >= start_date)
        .group_by(func.date(Conflict.detected_at))
    ).all()
    closed_rows = db.execute(
        select(func.date(Conflict.resolved_at), func.count())
        .where(
            Conflict.resolved_at.is_not(None),
            func.date(Conflict.resolved_at) >= start_date,
        )
        .group_by(func.date(Conflict.resolved_at))
    ).all()

    detected_by_date: dict[date, int] = {}
    for d, count in detected_rows:
        d = d if isinstance(d, date) else datetime.fromisoformat(str(d)).date()
        detected_by_date[d] = count

    closed_by_date: dict[date, int] = {}
    for d, count in closed_rows:
        d = d if isinstance(d, date) else datetime.fromisoformat(str(d)).date()
        closed_by_date[d] = count

    data = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        data.append(
            ConflictTrendPoint(
                date=d.isoformat(),
                detected=detected_by_date.get(d, 0),
                closed=closed_by_date.get(d, 0),
            )
        )

    return ConflictTrendResponse(days=days, data=data)


class QualityBySourceItem(BaseModel):
    source_type: str
    chunk_count: int
    avg_freshness_score: float
    avg_trust_score: float
    avg_conflict_risk: float


class QualityBySourceResponse(BaseModel):
    data: list[QualityBySourceItem]


@router.get("/quality/by-source", response_model=QualityBySourceResponse)
def get_quality_by_source(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            Document.source_type,
            func.count(Chunk.id),
            func.avg(Chunk.freshness_score),
            func.avg(Chunk.trust_score),
            func.avg(Chunk.conflict_risk),
        )
        .join(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.source_type)
        .order_by(Document.source_type.asc())
    ).all()

    data = [
        QualityBySourceItem(
            source_type=str(source_type),
            chunk_count=chunk_count,
            avg_freshness_score=round(float(avg_freshness or 0.0), 3),
            avg_trust_score=round(float(avg_trust or 0.0), 3),
            avg_conflict_risk=round(float(avg_conflict_risk or 0.0), 3),
        )
        for source_type, chunk_count, avg_freshness, avg_trust, avg_conflict_risk in rows
    ]

    return QualityBySourceResponse(data=data)


DISTRIBUTION_BUCKETS = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]


def _bucket_for_score(score: float) -> str:
    if score >= 0.8:
        return "0.8-1.0"
    if score >= 0.6:
        return "0.6-0.8"
    if score >= 0.4:
        return "0.4-0.6"
    if score >= 0.2:
        return "0.2-0.4"
    return "0.0-0.2"


class DistributionBucket(BaseModel):
    bucket: str
    count: int


class QualityDistributionResponse(BaseModel):
    freshness: list[DistributionBucket]
    trust: list[DistributionBucket]
    hallucination: list[DistributionBucket]


@router.get("/quality/distribution", response_model=QualityDistributionResponse)
def get_quality_distribution(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Chunk.freshness_score, Chunk.trust_score, Chunk.hallucination_risk)
    ).all()

    freshness_counts = {bucket: 0 for bucket in DISTRIBUTION_BUCKETS}
    trust_counts = {bucket: 0 for bucket in DISTRIBUTION_BUCKETS}
    hallucination_counts = {bucket: 0 for bucket in DISTRIBUTION_BUCKETS}

    for freshness_score, trust_score, hallucination_risk in rows:
        freshness_counts[_bucket_for_score(freshness_score)] += 1
        trust_counts[_bucket_for_score(trust_score)] += 1
        hallucination_counts[_bucket_for_score(hallucination_risk)] += 1

    return QualityDistributionResponse(
        freshness=[
            DistributionBucket(bucket=bucket, count=freshness_counts[bucket])
            for bucket in DISTRIBUTION_BUCKETS
        ],
        trust=[
            DistributionBucket(bucket=bucket, count=trust_counts[bucket])
            for bucket in DISTRIBUTION_BUCKETS
        ],
        hallucination=[
            DistributionBucket(bucket=bucket, count=hallucination_counts[bucket])
            for bucket in DISTRIBUTION_BUCKETS
        ],
    )


AGE_BUCKETS = ["0-30d", "30-90d", "90-180d", "180-365d", "365d+"]


def _bucket_for_age(age_days: float) -> str:
    if age_days < 30:
        return "0-30d"
    if age_days < 90:
        return "30-90d"
    if age_days < 180:
        return "90-180d"
    if age_days < 365:
        return "180-365d"
    return "365d+"


class StalenessByAgeItem(BaseModel):
    age_bucket: str
    chunk_count: int
    avg_freshness_score: float


class StalenessByAgeResponse(BaseModel):
    data: list[StalenessByAgeItem]


@router.get("/staleness/by-age", response_model=StalenessByAgeResponse)
def get_staleness_by_age(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = db.execute(select(Chunk.created_at, Chunk.freshness_score)).all()

    bucket_counts = {bucket: 0 for bucket in AGE_BUCKETS}
    bucket_sums = {bucket: 0.0 for bucket in AGE_BUCKETS}

    for created_at, freshness_score in rows:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_days = (now - created_at).total_seconds() / 86400
        bucket = _bucket_for_age(age_days)
        bucket_counts[bucket] += 1
        bucket_sums[bucket] += freshness_score

    data = []
    for bucket in AGE_BUCKETS:
        count = bucket_counts[bucket]
        avg_freshness = round(bucket_sums[bucket] / count, 3) if count > 0 else 0.0
        data.append(
            StalenessByAgeItem(
                age_bucket=bucket,
                chunk_count=count,
                avg_freshness_score=avg_freshness,
            )
        )

    return StalenessByAgeResponse(data=data)


class HallucinationRiskTrendPoint(BaseModel):
    date: str
    avg_hallucination_risk: float
    chunk_count: int


class HallucinationRiskTrendResponse(BaseModel):
    days: int
    data: list[HallucinationRiskTrendPoint]


@router.get("/hallucination-risk/trend", response_model=HallucinationRiskTrendResponse)
def get_hallucination_risk_trend(days: int = 30, db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)

    rows = db.execute(
        select(
            func.date(Chunk.created_at),
            func.avg(Chunk.hallucination_risk),
            func.count(),
        )
        .where(func.date(Chunk.created_at) >= start_date)
        .group_by(func.date(Chunk.created_at))
    ).all()

    by_date: dict[date, tuple[float, int]] = {}
    for d, avg_risk, count in rows:
        d = d if isinstance(d, date) else datetime.fromisoformat(str(d)).date()
        by_date[d] = (float(avg_risk or 0.0), count)

    data = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        avg_risk, count = by_date.get(d, (0.0, 0))
        data.append(
            HallucinationRiskTrendPoint(
                date=d.isoformat(),
                avg_hallucination_risk=round(avg_risk, 3),
                chunk_count=count,
            )
        )

    return HallucinationRiskTrendResponse(days=days, data=data)
