"""Autonomous maintenance tasks.

Runs on a Celery beat schedule (see ``app.celery_app``). The sweep re-scores
chunks so freshness/trust stay current as documents age, and logs a summary of
what it scanned. All external/DB access is defensive so the worker degrades
gracefully when Postgres/Qdrant are unavailable (e.g. in tests).
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="maintenance_sweep")
def maintenance_sweep_task():
    """Periodic sweep: re-score stale chunks and log a summary.

    Delegates the actual re-scoring to ``rescore_all_chunks_task`` so the
    scoring logic lives in one place. Returns a summary dict with the number of
    chunks scanned/re-scored; on failure it logs and returns a degraded status
    instead of raising, so the beat schedule keeps running.
    """
    try:
        from app.tasks.scoring import rescore_all_chunks_task

        result = rescore_all_chunks_task.run()
        updated = (result or {}).get("updated", 0)
        logger.info("maintenance_sweep complete: %s chunks re-scored", updated)
        return {"status": "ok", "rescored": updated}
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("maintenance_sweep skipped: %s", exc)
        return {"status": "degraded", "error": str(exc)}
