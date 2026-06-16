"""Hermetic tests for the agent workflow.

No external services and no real DB: we mock retrieval, Anthropic, and the
MemoryStore so the whole LangGraph runs in-process.
"""

import uuid
from unittest.mock import Mock

import pytest

pytest.importorskip("langgraph")


class _FakeMemory:
    def __init__(self, content, agent_role="knowledge", shared=True):
        self.id = uuid.uuid4()
        self.agent_role = agent_role
        self.memory_type = "semantic"
        self.content = content
        self.shared = shared


class FakeMemoryStore:
    """Records writes/recalls so tests can assert the cross-agent contract."""

    writes: list[dict] = []
    store: list[_FakeMemory] = []

    def __init__(self, db):
        self.db = db

    def recall(self, *, agent_role, query=None, include_shared=True, memory_type=None, limit=10):
        return [
            m
            for m in FakeMemoryStore.store
            if m.agent_role == agent_role or (m.shared and include_shared)
        ][:limit]

    def write(self, *, agent_role, content, memory_type, shared=False, metadata=None):
        FakeMemoryStore.writes.append(
            {
                "agent_role": agent_role,
                "content": content,
                "memory_type": memory_type,
                "shared": shared,
                "metadata": metadata,
            }
        )
        mem = _FakeMemory(content, agent_role=agent_role, shared=shared)
        FakeMemoryStore.store.append(mem)
        return mem


class _FakeContentBlock:
    def __init__(self, text):
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeContentBlock(text)]


class _FakeAnthropic:
    def __init__(self, *args, **kwargs):
        self.messages = self

    def create(self, *args, **kwargs):
        return _FakeMessage("Mocked LLM response.")


@pytest.fixture(autouse=True)
def _patch_externals(monkeypatch):
    FakeMemoryStore.writes = []
    FakeMemoryStore.store = []

    import agents.graph.nodes as nodes

    monkeypatch.setattr(nodes, "MemoryStore", FakeMemoryStore)
    monkeypatch.setattr(nodes.anthropic, "Anthropic", _FakeAnthropic)
    monkeypatch.setattr(
        nodes,
        "retrieve_context",
        lambda query, db=None: {
            "chunks": [
                {
                    "chunk_id": "c1",
                    "text": "OAuth 2.0 JWT is the current auth method.",
                    "score": 0.9,
                    "freshness_score": 0.8,
                    "conflict_risk": 0.1,
                    "document_title": "API Docs v2",
                    "source_type": "markdown",
                }
            ],
            "entities": [],
            "context_text": "OAuth 2.0 JWT is the current auth method.",
        },
    )
    yield


def test_run_agent_query_returns_result():
    from agents.graph.workflow import AgentRunResult, run_agent_query

    result = run_agent_query("What auth does the API use?", db=Mock())

    assert isinstance(result, AgentRunResult)
    assert result.answer
    assert result.agent_trace == [
        "orchestrator:plan",
        "memory:recalled 0",
        "knowledge:retrieved 1 chunks",
        "orchestrator:synthesize",
        "memory:wrote 1 (shared)",
    ]
    assert len(result.created_memories) == 1
    assert result.sources and result.sources[0]["chunk_id"] == "c1"


def test_shared_write_is_recallable_cross_agent():
    """Agent A (knowledge) writes shared -> a fresh orchestrator run recalls it."""
    from agents.graph.workflow import run_agent_query

    run_agent_query("First question about retention", db=Mock())

    # The written memory must be under role 'knowledge' and shared=True.
    assert FakeMemoryStore.writes
    last = FakeMemoryStore.writes[-1]
    assert last["agent_role"] == "knowledge"
    assert last["shared"] is True

    # A new orchestrator run should now recall that shared memory.
    result = run_agent_query("Follow-up question", db=Mock())
    assert any("recalled" in step for step in result.agent_trace)
    recalled_step = [s for s in result.agent_trace if s.startswith("memory:recalled")][0]
    assert recalled_step != "memory:recalled 0"
    assert len(result.recalled_memories) >= 1
