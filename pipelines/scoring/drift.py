"""Semantic drift detection.

Drift is distinct from *staleness*: a stale chunk is simply old (handled by
``FreshnessScorer``), whereas a *drifted* chunk's meaning has moved away from
prior versions of the same logical document/source, or its quality metrics
(freshness / conflict) are trending adversely.

``DriftDetector.compute_drift`` is pure: it takes the inputs it needs and
returns a 0..1 drift score plus a human-readable reason. Any DB / embedding
access lives in separate, guarded helpers so the core scorer stays trivially
unit-testable with no external dependencies.
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# Above this semantic distance (1 - cosine similarity) we consider the content
# to have meaningfully changed from its prior version.
SEMANTIC_DRIFT_THRESHOLD = 0.25

# Weights blending the two drift signals into a single score.
SEMANTIC_WEIGHT = 0.7
QUALITY_WEIGHT = 0.3


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float | None:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return None
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return None
    return dot / (norm_a * norm_b)


class DriftDetector:
    def compute_drift(
        self,
        *,
        current_embedding: list[float] | None = None,
        prior_embedding: list[float] | None = None,
        current_freshness: float | None = None,
        prior_freshness: float | None = None,
        current_conflict_risk: float | None = None,
        prior_conflict_risk: float | None = None,
    ) -> dict:
        """Return ``{"drift_score": 0..1, "reason": str, "signals": {...}}``.

        ``drift_score`` blends two signals when both are available:

        * **semantic** — cosine distance between the current chunk embedding and
          the embedding of a prior version of the same logical document.
        * **quality** — adverse movement in freshness (dropping) or conflict
          risk (rising) versus the prior version.

        Missing inputs are simply skipped; with no inputs the score is 0.0.
        """
        signals: dict[str, float] = {}
        reasons: list[str] = []

        # 1. Semantic drift from embedding comparison.
        semantic_drift: float | None = None
        similarity = _cosine_similarity(current_embedding or [], prior_embedding or [])
        if similarity is not None:
            semantic_drift = max(0.0, min(1.0, 1.0 - similarity))
            signals["semantic_drift"] = round(semantic_drift, 4)
            if semantic_drift >= SEMANTIC_DRIFT_THRESHOLD:
                reasons.append(
                    f"content shifted {round(semantic_drift * 100)}% from prior version"
                )

        # 2. Quality-metric drift (adverse trend only).
        quality_drift: float | None = None
        quality_components: list[float] = []
        if current_freshness is not None and prior_freshness is not None:
            # Freshness dropping is adverse.
            drop = max(0.0, prior_freshness - current_freshness)
            quality_components.append(drop)
            if drop >= 0.2:
                reasons.append(f"freshness fell {round(drop * 100)}%")
        if current_conflict_risk is not None and prior_conflict_risk is not None:
            # Conflict risk rising is adverse.
            rise = max(0.0, current_conflict_risk - prior_conflict_risk)
            quality_components.append(rise)
            if rise >= 0.2:
                reasons.append(f"conflict risk rose {round(rise * 100)}%")
        if quality_components:
            quality_drift = max(0.0, min(1.0, max(quality_components)))
            signals["quality_drift"] = round(quality_drift, 4)

        # 3. Blend available signals.
        if semantic_drift is not None and quality_drift is not None:
            drift_score = (
                SEMANTIC_WEIGHT * semantic_drift + QUALITY_WEIGHT * quality_drift
            )
        elif semantic_drift is not None:
            drift_score = semantic_drift
        elif quality_drift is not None:
            drift_score = quality_drift
        else:
            drift_score = 0.0

        drift_score = max(0.0, min(1.0, round(drift_score, 4)))
        reason = "; ".join(reasons) if reasons else "no significant drift"
        return {"drift_score": drift_score, "reason": reason, "signals": signals}

    def embedding_for(self, embedding_id: str | None) -> list[float] | None:
        """Fetch a stored embedding vector from Qdrant. Guarded — returns None on failure."""
        if not embedding_id:
            return None
        try:
            from qdrant_client import QdrantClient

            from app.config import settings

            qc = QdrantClient(url=settings.qdrant_url)
            points = qc.retrieve(
                collection_name=settings.qdrant_collection,
                ids=[embedding_id],
                with_vectors=True,
            )
            if not points or points[0].vector is None:
                return None
            return list(points[0].vector)
        except Exception:
            logger.warning("DriftDetector: embedding fetch failed", exc_info=True)
            return None
