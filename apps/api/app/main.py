from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_router
from app.config import settings


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["health"])
app.include_router(api_router, prefix="/api/v1")
