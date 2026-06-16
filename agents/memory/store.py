"""MemoryStore: synchronous CRUD/recall layer over the AgentMemory model.

This is the shared persistence contract for the agent memory layer. Memories
written with ``shared=True`` by one agent role become recallable by any other
role — this is the "Agent A learns -> Agent B knows" mechanism.
"""

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import AgentMemory


class MemoryStore:
    def __init__(self, db: Session):
        self.db = db

    def write(
        self,
        *,
        agent_role: str,
        content: str,
        memory_type: str = "semantic",
        shared: bool = False,
        metadata: dict | None = None,
    ) -> AgentMemory:
        memory = AgentMemory(
            agent_role=agent_role,
            content=content,
            memory_type=memory_type,
            shared=shared,
            extra_metadata=metadata,
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def recall(
        self,
        *,
        agent_role: str,
        query: str | None = None,
        include_shared: bool = True,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[AgentMemory]:
        stmt = self.db.query(AgentMemory)

        if include_shared:
            stmt = stmt.filter(
                or_(
                    AgentMemory.agent_role == agent_role,
                    AgentMemory.shared.is_(True),
                )
            )
        else:
            stmt = stmt.filter(AgentMemory.agent_role == agent_role)

        if memory_type is not None:
            stmt = stmt.filter(AgentMemory.memory_type == memory_type)

        if query:
            stmt = stmt.filter(AgentMemory.content.ilike(f"%{query}%"))

        memories = stmt.order_by(AgentMemory.created_at.desc()).limit(limit).all()

        # Stamp accessed_at on every returned row — the "memory reuse" signal.
        if memories:
            now = datetime.now(timezone.utc)
            for memory in memories:
                memory.accessed_at = now
            self.db.commit()

        return memories

    def list_memories(
        self,
        *,
        agent_role: str | None = None,
        memory_type: str | None = None,
        shared: bool | None = None,
        limit: int = 100,
    ) -> list[AgentMemory]:
        stmt = self.db.query(AgentMemory)

        if agent_role is not None:
            stmt = stmt.filter(AgentMemory.agent_role == agent_role)
        if memory_type is not None:
            stmt = stmt.filter(AgentMemory.memory_type == memory_type)
        if shared is not None:
            stmt = stmt.filter(AgentMemory.shared.is_(shared))

        return stmt.order_by(AgentMemory.created_at.desc()).limit(limit).all()
