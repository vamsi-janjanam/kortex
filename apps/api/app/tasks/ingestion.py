import uuid
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import Chunk, Document, LineageRecord, SourceType


@celery_app.task(name="ingest_document", bind=True, max_retries=3)
def ingest_document_task(self, document_id: str, file_path: str | None = None):
    """Ingest a document: extract text, chunk, embed, store in Qdrant."""
    db = SessionLocal()
    try:
        doc = db.get(Document, uuid.UUID(document_id))
        if not doc:
            return {"error": "Document not found"}

        source = file_path or doc.source_url
        source_type = doc.source_type

        if source_type == SourceType.PDF:
            from pipelines.ingestion.pdf import PDFConnector

            connector = PDFConnector()
        elif source_type in (SourceType.MARKDOWN, SourceType.GITHUB):
            from pipelines.ingestion.markdown import MarkdownConnector

            connector = MarkdownConnector()
        else:
            from pipelines.ingestion.markdown import MarkdownConnector

            connector = MarkdownConnector()

        raw_chunks = connector.ingest(source)

        from pipelines.scoring.freshness import FreshnessScorer
        from pipelines.scoring.trust import TrustScorer

        freshness_scorer = FreshnessScorer()
        trust_scorer = TrustScorer()

        from openai import OpenAI
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct

        oai = OpenAI(api_key=settings.openai_api_key)
        qc = QdrantClient(url=settings.qdrant_url)

        # Batch embed all chunks
        texts = [c["text"] for c in raw_chunks]
        embedding_resp = oai.embeddings.create(
            model=settings.embedding_model, input=texts
        )
        embeddings = [e.embedding for e in embedding_resp.data]

        points = []
        chunk_records = []

        for i, (raw_chunk, embedding) in enumerate(zip(raw_chunks, embeddings)):
            chunk_id = uuid.uuid4()
            embedding_id = str(chunk_id)

            freshness = freshness_scorer.score(doc.ingested_at, source_type)
            trust = trust_scorer.score(source_type)

            chunk = Chunk(
                id=chunk_id,
                document_id=doc.id,
                text=raw_chunk["text"],
                position=i,
                embedding_id=embedding_id,
                freshness_score=freshness,
                trust_score=trust,
            )
            db.add(chunk)

            lineage = LineageRecord(
                chunk_id=chunk_id,
                source_document_id=doc.id,
                source_owner=doc.source_url,
                timestamp_chain=[doc.ingested_at.isoformat()],
            )
            db.add(lineage)

            points.append(
                PointStruct(
                    id=embedding_id,
                    vector=embedding,
                    payload={
                        "chunk_id": str(chunk_id),
                        "document_id": str(doc.id),
                        "text": raw_chunk["text"][:200],
                    },
                )
            )
            chunk_records.append(chunk)

        qc.upsert(collection_name=settings.qdrant_collection, points=points)
        db.commit()

        # Run scoring task async
        score_document_chunks_task.delay(document_id)

        return {"document_id": document_id, "chunks_ingested": len(chunk_records)}

    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()


@celery_app.task(name="score_document_chunks", bind=True)
def score_document_chunks_task(self, document_id: str):
    """Run conflict detection across chunks of a document."""
    from pipelines.scoring.conflict import ConflictDetector
    from pipelines.scoring.hallucination_risk import HallucinationRiskScorer

    db = SessionLocal()
    try:
        detector = ConflictDetector()
        detector.detect_for_document(uuid.UUID(document_id), db)

        hallucination_scorer = HallucinationRiskScorer()
        chunks = (
            db.query(Chunk).filter(Chunk.document_id == uuid.UUID(document_id)).all()
        )
        for chunk in chunks:
            chunk.hallucination_risk = hallucination_scorer.score(
                chunk.freshness_score, chunk.trust_score, chunk.conflict_risk
            )
            chunk.scored_at = datetime.now(timezone.utc)

        db.commit()

        from app.tasks.extraction import extract_entities_task

        extract_entities_task.delay(document_id)

        return {"document_id": document_id, "status": "scored"}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        db.close()
