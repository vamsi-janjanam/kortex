from fastapi import APIRouter

from app.api.v1.endpoints import documents, search, stats

api_router = APIRouter()

api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
