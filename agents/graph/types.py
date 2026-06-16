"""Public result types for the agent workflow entrypoint."""

from pydantic import BaseModel


class MemoryRef(BaseModel):
    id: str
    agent_role: str
    memory_type: str
    content: str
    shared: bool


class AgentRunResult(BaseModel):
    answer: str
    plan: str
    recalled_memories: list[MemoryRef]
    created_memories: list[MemoryRef]
    sources: list[dict]
    agent_trace: list[str]
