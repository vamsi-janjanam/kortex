import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import limiter

from agents.memory.store import MemoryStore

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentQueryRequest(BaseModel):
    query: str = Field(..., max_length=4000)
    agent_role: str = "orchestrator"


class MemoryOut(BaseModel):
    id: str
    agent_role: str
    memory_type: str
    content: str
    shared: bool
    created_at: datetime | None = None
    accessed_at: datetime | None = None


class MemoryRef(BaseModel):
    id: str
    agent_role: str
    memory_type: str
    content: str
    shared: bool


class AgentQueryResponse(BaseModel):
    answer: str
    plan: str
    recalled_memories: list[MemoryRef]
    created_memories: list[MemoryRef]
    sources: list
    agent_trace: list[str]


class MemoryCreateRequest(BaseModel):
    agent_role: str
    content: str
    memory_type: str = "semantic"
    shared: bool = False
    metadata: dict | None = None


def _memory_ref(m) -> MemoryRef:
    return MemoryRef(
        id=str(m.id),
        agent_role=m.agent_role,
        memory_type=m.memory_type,
        content=m.content,
        shared=m.shared,
    )


def _memory_out(m) -> MemoryOut:
    return MemoryOut(
        id=str(m.id),
        agent_role=m.agent_role,
        memory_type=m.memory_type,
        content=m.content,
        shared=m.shared,
        created_at=m.created_at,
        accessed_at=m.accessed_at,
    )


@router.post("", response_model=AgentQueryResponse)
@limiter.limit("20/minute")
def query_agent(
    request: Request, payload: AgentQueryRequest, db: Session = Depends(get_db)
):
    try:
        from agents.graph.workflow import run_agent_query

        result = run_agent_query(payload.query, db, agent_role=payload.agent_role)
    except Exception as e:
        logger.exception("Agent workflow failed during query")
        raise HTTPException(status_code=503, detail="Agent service unavailable") from e

    return AgentQueryResponse(
        answer=result.answer,
        plan=result.plan,
        recalled_memories=[_memory_ref(m) for m in result.recalled_memories],
        created_memories=[_memory_ref(m) for m in result.created_memories],
        sources=result.sources,
        agent_trace=result.agent_trace,
    )


@router.get("/memory", response_model=list[MemoryOut])
@limiter.limit("20/minute")
def list_memory(
    request: Request,
    agent_role: str | None = None,
    memory_type: str | None = None,
    shared: bool | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    memories = MemoryStore(db).list_memories(
        agent_role=agent_role,
        memory_type=memory_type,
        shared=shared,
        limit=limit,
    )
    return [_memory_out(m) for m in memories]


@router.post("/memory", response_model=MemoryOut)
@limiter.limit("20/minute")
def create_memory(
    request: Request, payload: MemoryCreateRequest, db: Session = Depends(get_db)
):
    memory = MemoryStore(db).write(
        agent_role=payload.agent_role,
        content=payload.content,
        memory_type=payload.memory_type,
        shared=payload.shared,
        metadata=payload.metadata,
    )
    return _memory_out(memory)
