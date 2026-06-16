"""The agent node functions that make up the LangGraph workflow.

Each node is a pure-ish function ``(state) -> partial state``. The db Session is
bound via closures in ``workflow.build_agent_graph``. All LLM calls are
defensive: if the Anthropic API is unavailable they fall back to a deterministic
string so the workflow (and its tests) still run.
"""

import logging

import anthropic

from agents.memory.store import MemoryStore
from agents.retrieval import retrieve_context
from app.config import settings

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"


def _call_claude(prompt: str, *, model: str, max_tokens: int = 512) -> str | None:
    """Call Anthropic and return the text, or ``None`` on any failure."""
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        logger.warning("Claude call failed (%s); using fallback", model)
        return None


def _memref(mem) -> dict:
    """Map an AgentMemory ORM object to a MemoryRef-shaped dict."""
    return {
        "id": str(getattr(mem, "id", "")),
        "agent_role": getattr(mem, "agent_role", ""),
        "memory_type": getattr(mem, "memory_type", ""),
        "content": getattr(mem, "content", ""),
        "shared": bool(getattr(mem, "shared", False)),
    }


def orchestrator_plan(state: dict, db) -> dict:
    query = state["query"]
    prompt = (
        "You are an orchestrator agent. In 1-2 sentences, outline a plan to "
        "answer the user's question: what knowledge should be fetched and what "
        f"should be remembered for next time.\n\nQuestion: {query}"
    )
    plan = _call_claude(prompt, model=HAIKU_MODEL, max_tokens=256)
    if not plan:
        plan = (
            f"Recall prior memories, retrieve knowledge relevant to '{query}', "
            "synthesize an answer, and store a durable fact."
        )
    trace = list(state.get("trace", []))
    trace.append("orchestrator:plan")
    return {"plan": plan, "trace": trace}


def memory_recall(state: dict, db) -> dict:
    # Recall recent memories visible to this agent: its own plus any shared by
    # other agents. We deliberately do NOT filter by the raw query text — prior
    # learnings rarely contain the new question verbatim, and substring matching
    # would defeat the cross-agent "what has the team already learned" recall.
    try:
        memories = MemoryStore(db).recall(
            agent_role=state["agent_role"],
            include_shared=True,
            limit=5,
        )
    except Exception:
        logger.warning("memory_recall failed; continuing with no memories")
        memories = []
    recalled = [_memref(m) for m in memories]
    trace = list(state.get("trace", []))
    trace.append(f"memory:recalled {len(recalled)}")
    return {"recalled": recalled, "trace": trace}


def knowledge_retrieve(state: dict, db) -> dict:
    knowledge = retrieve_context(state["query"], db=db)
    n = len(knowledge.get("chunks", []))
    trace = list(state.get("trace", []))
    trace.append(f"knowledge:retrieved {n} chunks")
    return {"knowledge": knowledge, "trace": trace}


def orchestrator_synthesize(state: dict, db) -> dict:
    query = state["query"]
    recalled = state.get("recalled", [])
    knowledge = state.get("knowledge", {})
    context_text = knowledge.get("context_text", "")

    memory_block = ""
    if recalled:
        joined = "\n".join(f"- {m['content']}" for m in recalled)
        memory_block = (
            "\n\nRelevant memories from prior agent runs (cite that you used "
            f"prior memory):\n{joined}"
        )

    prompt = (
        "You are an orchestrator agent answering a question using retrieved "
        "knowledge and any prior memories. Be concise and factual.\n\n"
        f"Question: {query}\n\n"
        f"Knowledge context:\n{context_text or '(no knowledge retrieved)'}"
        f"{memory_block}\n\nAnswer:"
    )
    answer = _call_claude(prompt, model=settings.claude_model, max_tokens=1024)
    if not answer:
        prior = " Drawing on prior memory." if recalled else ""
        answer = (
            f"Based on the available knowledge, here is what I found for "
            f"'{query}'.{prior}\n\n{context_text or 'No supporting context was available.'}"
        )
    trace = list(state.get("trace", []))
    trace.append("orchestrator:synthesize")
    return {"answer": answer, "trace": trace}


def memory_write(state: dict, db) -> dict:
    query = state["query"]
    answer = state.get("answer", "")

    fact = _call_claude(
        "Summarize the single most durable, reusable fact from this answer in "
        f"one concise sentence.\n\nQuestion: {query}\n\nAnswer: {answer}",
        model=HAIKU_MODEL,
        max_tokens=128,
    )
    if not fact:
        fact = (answer or f"Answered a question about: {query}")[:280]

    created: list[dict] = []
    try:
        mem = MemoryStore(db).write(
            agent_role="knowledge",
            content=fact,
            memory_type="semantic",
            shared=True,
            metadata={"source_query": query},
        )
        created.append(_memref(mem))
    except Exception:
        logger.warning("memory_write failed; recording fact without persistence")
        created.append(
            {
                "id": "",
                "agent_role": "knowledge",
                "memory_type": "semantic",
                "content": fact,
                "shared": True,
            }
        )

    trace = list(state.get("trace", []))
    trace.append("memory:wrote 1 (shared)")
    return {"created": created, "trace": trace}
