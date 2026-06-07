import redis as redis_client
from fastapi import APIRouter
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings
from app.database import check_db

router = APIRouter()


@router.get("/health")
def health():
    checks: dict[str, str] = {}

    checks["database"] = "ok" if check_db() else "error"

    try:
        r = redis_client.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    try:
        qc = QdrantClient(url=settings.qdrant_url, timeout=3)
        qc.get_collections()
        checks["qdrant"] = "ok"
    except Exception:
        checks["qdrant"] = "error"

    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
