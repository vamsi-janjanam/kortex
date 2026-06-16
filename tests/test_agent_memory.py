"""Unit tests for MemoryStore shared/private visibility and recall semantics."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))  # make `agents` importable like `pipelines`
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

KNOWLEDGE_ROLE = "knowledge_test_a"
ORCH_ROLE = "orchestrator_test_a"


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _cleanup(db_session, *roles):
    from app.models import AgentMemory

    db_session.query(AgentMemory).filter(AgentMemory.agent_role.in_(roles)).delete(
        synchronize_session=False
    )
    db_session.commit()


def test_shared_memory_visible_to_other_agent(db_session):
    from agents.memory.store import MemoryStore

    store = MemoryStore(db_session)
    try:
        written = store.write(
            agent_role=KNOWLEDGE_ROLE,
            content="OAuth 2.0 JWT is the current auth scheme",
            shared=True,
        )
        recalled = store.recall(agent_role=ORCH_ROLE)
        assert any(m.id == written.id for m in recalled)
    finally:
        _cleanup(db_session, KNOWLEDGE_ROLE, ORCH_ROLE)


def test_private_memory_hidden_from_other_agent(db_session):
    from agents.memory.store import MemoryStore

    store = MemoryStore(db_session)
    try:
        written = store.write(
            agent_role=KNOWLEDGE_ROLE,
            content="private scratch note",
            shared=False,
        )
        other = store.recall(agent_role=ORCH_ROLE)
        assert all(m.id != written.id for m in other)

        own = store.recall(agent_role=KNOWLEDGE_ROLE)
        assert any(m.id == written.id for m in own)
    finally:
        _cleanup(db_session, KNOWLEDGE_ROLE, ORCH_ROLE)


def test_recall_updates_accessed_at(db_session):
    from agents.memory.store import MemoryStore

    store = MemoryStore(db_session)
    try:
        written = store.write(
            agent_role=KNOWLEDGE_ROLE, content="reuse signal note", shared=False
        )
        assert written.accessed_at is None

        store.recall(agent_role=KNOWLEDGE_ROLE)
        db_session.refresh(written)
        assert written.accessed_at is not None
    finally:
        _cleanup(db_session, KNOWLEDGE_ROLE)


def test_memory_type_filter(db_session):
    from agents.memory.store import MemoryStore

    store = MemoryStore(db_session)
    try:
        store.write(agent_role=KNOWLEDGE_ROLE, content="a fact", memory_type="semantic")
        episodic = store.write(
            agent_role=KNOWLEDGE_ROLE, content="an event", memory_type="episodic"
        )

        results = store.recall(agent_role=KNOWLEDGE_ROLE, memory_type="episodic")
        assert all(m.memory_type == "episodic" for m in results)
        assert any(m.id == episodic.id for m in results)
    finally:
        _cleanup(db_session, KNOWLEDGE_ROLE)
