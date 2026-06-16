"""LangGraph shared state for the agent workflow."""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    query: str
    agent_role: str
    plan: str
    recalled: list
    knowledge: dict
    answer: str
    created: list
    trace: list[str]
