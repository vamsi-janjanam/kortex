"""Build the LangGraph agent graph and expose ``run_agent_query``.

The cross-agent story: ``memory_write`` persists a fact as the ``knowledge``
role with ``shared=True``; a later ``orchestrator`` run recalls it via
``memory_recall`` (include_shared=True). "Agent A learns -> Agent B knows."
"""

from functools import partial

from sqlalchemy.orm import Session

from agents.graph.nodes import (
    knowledge_retrieve,
    memory_recall,
    memory_write,
    orchestrator_plan,
    orchestrator_synthesize,
)
from agents.graph.state import AgentState
from agents.graph.types import AgentRunResult, MemoryRef


def build_agent_graph(db: Session):
    """Construct and compile the linear 5-node agent graph (db bound per node)."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(AgentState)
    graph.add_node("orchestrator_plan", partial(orchestrator_plan, db=db))
    graph.add_node("memory_recall", partial(memory_recall, db=db))
    graph.add_node("knowledge_retrieve", partial(knowledge_retrieve, db=db))
    graph.add_node("orchestrator_synthesize", partial(orchestrator_synthesize, db=db))
    graph.add_node("memory_write", partial(memory_write, db=db))

    graph.add_edge(START, "orchestrator_plan")
    graph.add_edge("orchestrator_plan", "memory_recall")
    graph.add_edge("memory_recall", "knowledge_retrieve")
    graph.add_edge("knowledge_retrieve", "orchestrator_synthesize")
    graph.add_edge("orchestrator_synthesize", "memory_write")
    graph.add_edge("memory_write", END)

    return graph.compile()


def run_agent_query(
    query: str, db: Session, *, agent_role: str = "orchestrator"
) -> AgentRunResult:
    """Run the multi-agent workflow and return a structured result."""
    compiled = build_agent_graph(db)

    initial: AgentState = {
        "query": query,
        "agent_role": agent_role,
        "plan": "",
        "recalled": [],
        "knowledge": {},
        "answer": "",
        "created": [],
        "trace": [],
    }
    final = compiled.invoke(initial)

    knowledge = final.get("knowledge") or {}
    return AgentRunResult(
        answer=final.get("answer", ""),
        plan=final.get("plan", ""),
        recalled_memories=[MemoryRef(**m) for m in final.get("recalled", [])],
        created_memories=[MemoryRef(**m) for m in final.get("created", [])],
        sources=knowledge.get("chunks", []),
        agent_trace=final.get("trace", []),
    )
