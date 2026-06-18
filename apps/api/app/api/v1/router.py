from fastapi import APIRouter

from app.api.v1.endpoints import (
    agents,
    chat,
    documents,
    graph,
    reasoning,
    search,
    stats,
)

api_router = APIRouter()

api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(reasoning.router, prefix="/reasoning", tags=["reasoning"])
