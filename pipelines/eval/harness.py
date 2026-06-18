"""
Kortex Eval Harness — measures retrieval quality before vs. after cleaning.

Usage:
  python -m pipelines.eval.harness --mode raw
  python -m pipelines.eval.harness --mode cleaned
  python -m pipelines.eval.harness --mode both   (default)
  python -m pipelines.eval.harness --mode both --output results.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import anthropic

QA_FILE = Path(__file__).parent.parent.parent / "data" / "eval_qa_pairs" / "qa_pairs.json"

ANSWER_PROMPT = """You are a helpful assistant. Answer the question using ONLY the provided context.
If the context doesn't contain enough information, say "I don't know."

Context:
{context}

Question: {question}

Answer concisely."""

JUDGE_PROMPT = """You are an evaluation judge. Compare the generated answer to the reference answer.

Question: {question}
Reference answer: {reference_answer}
Generated answer: {generated_answer}
Context used: {context}

Score the generated answer:
1. faithfulness (0.0-1.0): Is every claim in the generated answer supported by the context?
2. correctness (0.0-1.0): Does the generated answer match the reference answer?
3. is_hallucinating (true/false): Does the answer contain claims NOT in the context?

Return ONLY JSON: {{"faithfulness": 0.0, "correctness": 0.0, "is_hallucinating": false}}"""

BUSINESS_JUDGE_PROMPT = """You are an evaluation judge measuring BUSINESS UNDERSTANDING — \
whether the answer explains the *why* (business logic / rationale), not just the bare fact.

Question: {question}
Reference answer: {reference_answer}
Generated answer: {generated_answer}
This question is known to involve contradictory/conflicting sources: {has_conflict}

Score the generated answer:
1. explains_rationale (0.0-1.0): Does it explain the reasoning, decision, policy, or "why" \
behind the answer — not merely restate a fact?
2. surfaces_conflict (true/false): If conflicting information is involved, does the answer \
explicitly acknowledge the contradiction (vs. silently picking one side)? If no conflict is \
involved, return false.

Return ONLY JSON: {{"explains_rationale": 0.0, "surfaces_conflict": false}}"""


@dataclass
class QAPair:
    id: str
    question: str
    reference_answer: str
    has_seeded_conflict: bool = False
    notes: str = ""


@dataclass
class EvalResult:
    qa_id: str
    question: str
    reference_answer: str
    retrieved_chunks: int
    generated_answer: str
    faithfulness: float
    correctness: float
    is_hallucinating: bool
    mode: str
    # Business-understanding metrics (does the answer explain the "why"?).
    explains_rationale: float = 0.0
    surfaces_conflict: bool = False
    has_seeded_conflict: bool = False


def load_qa_pairs() -> list[QAPair]:
    with open(QA_FILE) as f:
        data = json.load(f)
    return [QAPair(**item) for item in data]


def embed_query(query: str, settings) -> list[float]:
    from openai import OpenAI
    oai = OpenAI(api_key=settings.openai_api_key)
    resp = oai.embeddings.create(model=settings.embedding_model, input=query)
    return resp.data[0].embedding


def retrieve_chunks(query_vector: list[float], settings, mode: Literal["raw", "cleaned"], top_k: int = 5) -> list[dict]:
    from qdrant_client import QdrantClient

    qc = QdrantClient(url=settings.qdrant_url)
    hits = qc.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        limit=top_k * 3 if mode == "cleaned" else top_k,
        with_payload=True,
    )

    if mode == "raw":
        return [{"text": h.payload.get("text", ""), "score": h.score} for h in hits[:top_k]]

    # "cleaned" mode: filter low-quality chunks via DB scores
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "api"))
    import uuid as _uuid
    from app.database import SessionLocal
    from app.models import Chunk
    db = SessionLocal()
    results = []
    try:
        for hit in hits:
            chunk_id_str = hit.payload.get("chunk_id")
            if not chunk_id_str:
                continue
            chunk = db.get(Chunk, _uuid.UUID(chunk_id_str))
            if not chunk:
                continue
            if chunk.freshness_score < 0.3 or chunk.conflict_risk > 0.7:
                continue
            results.append({"text": hit.payload.get("text", ""), "score": hit.score,
                             "freshness": chunk.freshness_score, "conflict_risk": chunk.conflict_risk})
            if len(results) >= top_k:
                break
    finally:
        db.close()
    return results


def generate_answer(question: str, chunks: list[dict], client: anthropic.Anthropic, model: str) -> str:
    if not chunks:
        return "I don't know (no relevant context found)."
    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    message = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": ANSWER_PROMPT.format(context=context, question=question)}],
    )
    return message.content[0].text.strip()


def judge_answer(qa: QAPair, generated: str, chunks: list[dict], client: anthropic.Anthropic, model: str) -> dict:
    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    message = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(
            question=qa.question,
            reference_answer=qa.reference_answer,
            generated_answer=generated,
            context=context[:3000],
        )}],
    )
    raw = message.content[0].text.strip()
    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"faithfulness": 0.0, "correctness": 0.0, "is_hallucinating": True}


def judge_business_understanding(
    qa: QAPair, generated: str, client: anthropic.Anthropic, model: str
) -> dict:
    """Judge whether the answer explains the *why* and surfaces conflicts.

    This is the business-understanding metric: it measures reasoning quality
    (rationale + conflict-awareness) rather than bare fact retrieval. Parsing is
    defensive and mirrors :func:`judge_answer`.
    """
    message = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{"role": "user", "content": BUSINESS_JUDGE_PROMPT.format(
            question=qa.question,
            reference_answer=qa.reference_answer,
            generated_answer=generated,
            has_conflict=qa.has_seeded_conflict,
        )}],
    )
    raw = message.content[0].text.strip()
    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"explains_rationale": 0.0, "surfaces_conflict": False}


def run_eval(mode: Literal["raw", "cleaned"], settings, client: anthropic.Anthropic) -> list[EvalResult]:
    qa_pairs = load_qa_pairs()
    results = []

    print(f"\n  Running {len(qa_pairs)} queries in [{mode.upper()}] mode...")
    for i, qa in enumerate(qa_pairs, 1):
        try:
            vector = embed_query(qa.question, settings)
            chunks = retrieve_chunks(vector, settings, mode)
            answer = generate_answer(qa.question, chunks, client, settings.claude_model)
            scores = judge_answer(qa, answer, chunks, client, settings.claude_model)
            biz = judge_business_understanding(qa, answer, client, settings.claude_model)

            results.append(EvalResult(
                qa_id=qa.id,
                question=qa.question,
                reference_answer=qa.reference_answer,
                retrieved_chunks=len(chunks),
                generated_answer=answer,
                faithfulness=scores.get("faithfulness", 0.0),
                correctness=scores.get("correctness", 0.0),
                is_hallucinating=scores.get("is_hallucinating", False),
                mode=mode,
                explains_rationale=biz.get("explains_rationale", 0.0),
                surfaces_conflict=biz.get("surfaces_conflict", False),
                has_seeded_conflict=qa.has_seeded_conflict,
            ))
            print(f"    [{i}/{len(qa_pairs)}] {qa.id}: correctness={scores.get('correctness', 0):.2f} hallucinating={scores.get('is_hallucinating')}")
            time.sleep(0.5)  # rate limit courtesy
        except Exception as e:
            print(f"    [{i}/{len(qa_pairs)}] {qa.id}: ERROR — {e}")

    return results


def print_comparison(raw_results: list[EvalResult], cleaned_results: list[EvalResult]):
    def agg(results: list[EvalResult]) -> dict:
        if not results:
            return {}
        n = len(results)
        conflict_results = [r for r in results if r.has_seeded_conflict]
        nc = len(conflict_results)
        return {
            "accuracy": round(sum(r.correctness for r in results) / n * 100, 1),
            "faithfulness": round(sum(r.faithfulness for r in results) / n * 100, 1),
            "hallucination_rate": round(sum(1 for r in results if r.is_hallucinating) / n * 100, 1),
            "rationale": round(sum(r.explains_rationale for r in results) / n * 100, 1),
            # Of the questions with a seeded conflict, how many did the answer surface?
            "conflict_surfaced": (
                round(sum(1 for r in conflict_results if r.surfaces_conflict) / nc * 100, 1)
                if nc
                else 0.0
            ),
            "n": n,
        }

    r = agg(raw_results)
    c = agg(cleaned_results)

    print("\n" + "=" * 60)
    print("  KORTEX EVAL RESULTS — Before vs. After")
    print("=" * 60)
    print(f"  {'Metric':<28} {'RAW':>8} {'CLEANED':>10} {'DELTA':>8}")
    print(f"  {'-'*56}")

    def row(label, key, higher_is_better=True):
        rv, cv = r.get(key, 0), c.get(key, 0)
        delta = cv - rv
        sign = "▲" if delta > 0 else ("▼" if delta < 0 else "—")
        good = (delta > 0) == higher_is_better
        marker = "✓" if good and abs(delta) > 0 else ""
        print(f"  {label:<28} {rv:>7.1f}% {cv:>9.1f}% {sign}{abs(delta):>5.1f}% {marker}")

    row("Retrieval Accuracy", "accuracy")
    row("Faithfulness", "faithfulness")
    row("Hallucination Rate", "hallucination_rate", higher_is_better=False)
    row("Explains Rationale (why)", "rationale")
    row("Conflicts Surfaced", "conflict_surfaced")
    print(f"  {'Questions evaluated':<28} {r.get('n', 0):>8} {c.get('n', 0):>10}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Kortex Eval Harness")
    parser.add_argument("--mode", choices=["raw", "cleaned", "both"], default="both")
    parser.add_argument("--output", type=str, help="Save results JSON to file")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "api"))
    from app.config import settings

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    raw_results, cleaned_results = [], []

    if args.mode in ("raw", "both"):
        raw_results = run_eval("raw", settings, client)

    if args.mode in ("cleaned", "both"):
        cleaned_results = run_eval("cleaned", settings, client)

    if args.mode == "both":
        print_comparison(raw_results, cleaned_results)

    if args.output:
        all_results = [asdict(r) for r in raw_results + cleaned_results]
        Path(args.output).write_text(json.dumps(all_results, indent=2))
        print(f"\n  Results saved to {args.output}")


if __name__ == "__main__":
    main()
