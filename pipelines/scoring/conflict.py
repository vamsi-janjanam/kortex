import json
import os
import uuid

import anthropic
import numpy as np

CONFLICT_JUDGE_PROMPT = """You are a knowledge conflict detector. Given two text excerpts from different documents, determine if they contradict each other.

Excerpt A:
{text_a}

Excerpt B:
{text_b}

Do these excerpts contain contradictory information? Answer with JSON:
{{"is_conflict": true/false, "confidence": 0.0-1.0, "description": "brief explanation"}}

Return ONLY valid JSON."""

SIMILARITY_THRESHOLD = 0.85


class ConflictDetector:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    def detect_for_document(self, document_id: uuid.UUID, db) -> list[dict]:
        from sqlalchemy import select

        from app.models import Chunk, Conflict

        new_chunks = (
            db.execute(select(Chunk).where(Chunk.document_id == document_id))
            .scalars()
            .all()
        )
        all_chunks = db.execute(select(Chunk)).scalars().all()

        detected = []
        for new_chunk in new_chunks:
            for existing_chunk in all_chunks:
                if existing_chunk.id == new_chunk.id:
                    continue
                if existing_chunk.document_id == new_chunk.document_id:
                    continue

                # Only compare chunks that have embeddings we can fetch
                similarity = self._cosine_similarity_from_qdrant(
                    new_chunk.embedding_id, existing_chunk.embedding_id
                )
                if similarity is None or similarity < SIMILARITY_THRESHOLD:
                    continue

                result = self._judge_conflict(new_chunk.text, existing_chunk.text)
                if result and result.get("is_conflict"):
                    conflict = Conflict(
                        chunk_a_id=new_chunk.id,
                        chunk_b_id=existing_chunk.id,
                        description=result.get("description"),
                        confidence_score=result.get("confidence", 0.5),
                    )
                    db.add(conflict)

                    # Flag both chunks with conflict risk
                    new_chunk.conflict_risk = max(new_chunk.conflict_risk, result.get("confidence", 0.5))
                    existing_chunk.conflict_risk = max(existing_chunk.conflict_risk, result.get("confidence", 0.5))
                    detected.append(result)

        return detected

    def _cosine_similarity_from_qdrant(self, id_a: str | None, id_b: str | None) -> float | None:
        if not id_a or not id_b:
            return None
        try:
            from qdrant_client import QdrantClient
            from app.config import settings

            qc = QdrantClient(url=settings.qdrant_url)
            points = qc.retrieve(
                collection_name=settings.qdrant_collection,
                ids=[id_a, id_b],
                with_vectors=True,
            )
            if len(points) < 2:
                return None
            vec_a = np.array(points[0].vector)
            vec_b = np.array(points[1].vector)
            return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))
        except Exception:
            return None

    def _judge_conflict(self, text_a: str, text_b: str) -> dict | None:
        try:
            message = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": CONFLICT_JUDGE_PROMPT.format(text_a=text_a[:1500], text_b=text_b[:1500]),
                }],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            return json.loads(raw)
        except Exception:
            return None
