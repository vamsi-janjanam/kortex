"""Reusable knowledge retrieval for the agent layer.

Mirrors the logic of ``apps/api/app/api/v1/endpoints/search.py`` but returns a
plain dict suitable for feeding an LLM. Every external call is wrapped in
try/except so the function degrades gracefully (and is trivially unit-testable
with everything mocked).
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


def retrieve_context(query: str, *, top_k: int = 5, db: Session | None = None) -> dict:
    """Embed ``query``, search Qdrant, enrich hits from Postgres, pull entities.

    Returns ``{"chunks": [...], "entities": [...], "context_text": "..."}``.
    On any failure the relevant section is omitted and a note is recorded.
    """
    result: dict = {"chunks": [], "entities": [], "context_text": "", "notes": []}

    # 1. Embed the query.
    try:
        from openai import OpenAI

        oai = OpenAI(api_key=settings.openai_api_key)
        embedding_response = oai.embeddings.create(
            model=settings.embedding_model, input=query
        )
        query_vector = embedding_response.data[0].embedding
    except Exception:
        logger.exception("retrieve_context: embedding failed")
        result["notes"].append("embedding_unavailable")
        return result

    # 2. Vector search in Qdrant.
    try:
        from qdrant_client import QdrantClient

        qc = QdrantClient(url=settings.qdrant_url)
        hits = qc.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=top_k * 3,
        )
    except Exception:
        logger.exception("retrieve_context: vector search failed")
        result["notes"].append("vector_search_unavailable")
        return result

    # 3. Enrich each hit from Postgres.
    chunks: list[dict] = []
    if db is not None:
        try:
            from app.models import Chunk, Document

            for hit in hits:
                payload = getattr(hit, "payload", None) or {}
                raw_id = payload.get("chunk_id", "")
                if not raw_id:
                    continue
                try:
                    chunk_id = uuid.UUID(str(raw_id))
                except ValueError:
                    continue

                chunk = db.get(Chunk, chunk_id)
                if not chunk:
                    continue
                doc = db.get(Document, chunk.document_id)
                if not doc:
                    continue

                chunks.append(
                    {
                        "chunk_id": str(chunk.id),
                        "text": chunk.text,
                        "score": getattr(hit, "score", 0.0),
                        "freshness_score": chunk.freshness_score,
                        "conflict_risk": chunk.conflict_risk,
                        "document_title": doc.title,
                        "source_type": doc.source_type,
                    }
                )
                if len(chunks) >= top_k:
                    break
        except Exception:
            logger.exception("retrieve_context: postgres enrichment failed")
            result["notes"].append("metadata_enrichment_failed")

    result["chunks"] = chunks

    # 4. Optional graph context from Neo4j (best-effort).
    try:
        from app.core.neo4j_client import get_neo4j_driver

        driver = get_neo4j_driver()
        with driver.session() as ses:
            records = ses.run(
                "MATCH (e:Entity) RETURN e.name AS name, e.entity_type AS entity_type LIMIT 10"
            )
            result["entities"] = [
                {"name": r["name"], "entity_type": r["entity_type"]} for r in records
            ]
    except Exception:
        logger.debug("retrieve_context: neo4j unavailable, omitting graph context")
        result["entities"] = []

    # 5. Concatenate chunk texts for the LLM.
    result["context_text"] = "\n\n".join(c["text"] for c in chunks)
    return result
