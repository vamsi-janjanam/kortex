from app.celery_app import celery_app
from app.database import SessionLocal


@celery_app.task(name="rescore_all_chunks")
def rescore_all_chunks_task():
    """Recalculate freshness scores for all chunks — run periodically."""
    from sqlalchemy import select

    from app.models import Chunk, Document
    from pipelines.scoring.freshness import FreshnessScorer
    from pipelines.scoring.trust import TrustScorer

    db = SessionLocal()
    try:
        freshness_scorer = FreshnessScorer()
        trust_scorer = TrustScorer()

        chunks = db.execute(select(Chunk)).scalars().all()
        updated = 0
        for chunk in chunks:
            doc = db.get(Document, chunk.document_id)
            if not doc:
                continue
            chunk.freshness_score = freshness_scorer.score(doc.ingested_at, doc.source_type)
            chunk.trust_score = trust_scorer.score(doc.source_type)
            updated += 1

        db.commit()
        return {"updated": updated}
    finally:
        db.close()
