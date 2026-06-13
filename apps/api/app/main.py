from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_router
from app.config import settings
from app.core.security import limiter, require_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_qdrant_collection()
    yield


def _ensure_qdrant_collection():
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        qc = QdrantClient(url=settings.qdrant_url, timeout=5)
        collections = [c.name for c in qc.get_collections().collections]
        if settings.qdrant_collection not in collections:
            qc.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dim, distance=Distance.COSINE
                ),
            )
    except Exception as e:
        print(f"[startup] Qdrant collection setup skipped: {e}")


app = FastAPI(
    title="Kortex API",
    description="Enterprise knowledge reliability platform — ingestion, scoring, conflict detection, and retrieval.",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting (slowapi). The shared limiter is defined in app.core.security
# so endpoint modules can apply @limiter.limit(...) without importing main.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# /health stays open; all /api/v1 routes require a valid API key.
app.include_router(health_router, tags=["health"])
app.include_router(
    api_router, prefix="/api/v1", dependencies=[Depends(require_api_key)]
)
