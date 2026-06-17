from celery import Celery

from app.config import settings

celery_app = Celery(
    "kortex",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ingestion",
        "app.tasks.scoring",
        "app.tasks.extraction",
        "app.tasks.graph",
        "app.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Autonomous maintenance — run a periodic sweep that re-scores stale chunks.
celery_app.conf.beat_schedule = {
    "maintenance-sweep": {
        "task": "maintenance_sweep",
        "schedule": settings.maintenance_rescore_interval_minutes * 60.0,
    },
}
