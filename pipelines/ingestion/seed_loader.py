"""
Loads the synthetic seed corpus into the database and vector store.
Run via: python -m pipelines.ingestion.seed_loader
"""

import sys
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "seed_corpus"

SEED_DOCUMENTS = [
    {"title": "Acme API Docs v1 (STALE)", "source_type": "markdown", "file": "api_docs_v1.md"},
    {"title": "Acme API Docs v2 (CURRENT)", "source_type": "markdown", "file": "api_docs_v2.md"},
    {"title": "System Architecture Guide", "source_type": "markdown", "file": "architecture_guide.md"},
]


def main():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "api"))

    from app.config import settings
    from app.database import SessionLocal
    from app.models import Document
    from app.tasks.ingestion import ingest_document_task
    from pipelines.ingestion.markdown import MarkdownConnector
    from pipelines.scoring.freshness import FreshnessScorer
    from pipelines.scoring.trust import TrustScorer
    from openai import OpenAI
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct
    import uuid as _uuid

    db = SessionLocal()
    oai = OpenAI(api_key=settings.openai_api_key)
    qc = QdrantClient(url=settings.qdrant_url)

    from app.models import Chunk, LineageRecord
    freshness_scorer = FreshnessScorer()
    trust_scorer = TrustScorer()
    connector = MarkdownConnector()

    for seed in SEED_DOCUMENTS:
        file_path = DATA_DIR / seed["file"]
        if not file_path.exists():
            print(f"  [skip] {seed['file']} not found")
            continue

        doc = Document(
            source_type=seed["source_type"],
            source_url=str(file_path),
            title=seed["title"],
        )
        db.add(doc)
        db.flush()

        raw_chunks = connector.ingest(str(file_path))
        texts = [c["text"] for c in raw_chunks]

        if not texts:
            print(f"  [skip] {seed['file']} produced no chunks")
            continue

        emb_resp = oai.embeddings.create(model=settings.embedding_model, input=texts)
        embeddings = [e.embedding for e in emb_resp.data]

        points = []
        for i, (rc, emb) in enumerate(zip(raw_chunks, embeddings)):
            chunk_id = _uuid.uuid4()
            freshness = freshness_scorer.score(doc.ingested_at, seed["source_type"])
            trust = trust_scorer.score(seed["source_type"])

            chunk = Chunk(
                id=chunk_id,
                document_id=doc.id,
                text=rc["text"],
                position=i,
                embedding_id=str(chunk_id),
                freshness_score=freshness,
                trust_score=trust,
            )
            db.add(chunk)
            db.add(LineageRecord(
                chunk_id=chunk_id,
                source_document_id=doc.id,
                source_owner=str(file_path),
                timestamp_chain=[doc.ingested_at.isoformat()],
            ))
            points.append(PointStruct(
                id=str(chunk_id),
                vector=emb,
                payload={"chunk_id": str(chunk_id), "document_id": str(doc.id), "text": rc["text"][:200]},
            ))

        qc.upsert(collection_name=settings.qdrant_collection, points=points)
        db.commit()
        print(f"  [ok] {seed['title']} — {len(points)} chunks")

    db.close()
    print("\nSeed corpus loaded. Run `make eval` to see the before/after comparison.")


if __name__ == "__main__":
    main()
