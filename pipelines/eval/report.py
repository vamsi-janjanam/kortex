"""
Kortex Eval Report — injects harness results into the README metric table.

Reads the JSON produced by `pipelines.eval.harness --output <file>` (a flat list
of per-QA-pair results, each tagged with `mode`), aggregates raw vs. cleaned
metrics, computes deltas, and rewrites the README table between the markers:

    <!-- EVAL_TABLE_START -->
    ... generated table ...
    <!-- EVAL_TABLE_END -->

Idempotent: re-running replaces the table in place. Never fabricates numbers —
if a mode has no results, that cell is left as "—".

Usage:
  python -m pipelines.eval.report                       # defaults: results.json -> README.md
  python -m pipelines.eval.report --input results.json --readme README.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
START_MARKER = "<!-- EVAL_TABLE_START -->"
END_MARKER = "<!-- EVAL_TABLE_END -->"

# Metric rows: (label, json_agg_key, higher_is_better)
ROWS = [
    ("Accuracy", "accuracy", True),
    ("Faithfulness", "faithfulness", True),
    ("Hallucination Rate", "hallucination_rate", False),
    ("Explains Rationale (why)", "rationale", True),
    ("Conflicts Surfaced", "conflict_surfaced", True),
]


def aggregate(results: list[dict], mode: str) -> dict:
    """Aggregate per-QA-pair results for one mode. Mirrors harness.print_comparison.agg()."""
    rows = [r for r in results if r.get("mode") == mode]
    if not rows:
        return {}
    n = len(rows)
    conflict_rows = [r for r in rows if r.get("has_seeded_conflict")]
    nc = len(conflict_rows)
    return {
        "accuracy": round(sum(float(r.get("correctness", 0.0)) for r in rows) / n * 100, 1),
        "faithfulness": round(sum(float(r.get("faithfulness", 0.0)) for r in rows) / n * 100, 1),
        "hallucination_rate": round(
            sum(1 for r in rows if r.get("is_hallucinating")) / n * 100, 1
        ),
        "rationale": round(
            sum(float(r.get("explains_rationale", 0.0)) for r in rows) / n * 100, 1
        ),
        "conflict_surfaced": (
            round(sum(1 for r in conflict_rows if r.get("surfaces_conflict")) / nc * 100, 1)
            if nc
            else 0.0
        ),
        "n": n,
    }


def fmt_pct(agg: dict, key: str) -> str:
    if not agg or key not in agg:
        return "—"
    return f"{agg[key]:.1f}%"


def fmt_delta(raw: dict, cleaned: dict, key: str, higher_is_better: bool) -> str:
    if not raw or not cleaned or key not in raw or key not in cleaned:
        return "run `make eval-report`"
    delta = cleaned[key] - raw[key]
    if abs(delta) < 0.05:
        return "±0.0%"
    arrow = "▲" if delta > 0 else "▼"
    improved = (delta > 0) == higher_is_better
    mark = " ✓" if improved else ""
    return f"{arrow} {abs(delta):.1f}%{mark}"


def build_table(results: list[dict]) -> str:
    raw = aggregate(results, "raw")
    cleaned = aggregate(results, "cleaned")

    lines = [
        "| Metric | Raw | Cleaned | Delta |",
        "|--------|-----|---------|-------|",
    ]
    for label, key, hib in ROWS:
        lines.append(
            f"| {label} | {fmt_pct(raw, key)} | {fmt_pct(cleaned, key)} | "
            f"{fmt_delta(raw, cleaned, key, hib)} |"
        )

    n_raw = raw.get("n")
    n_cleaned = cleaned.get("n")
    if n_raw or n_cleaned:
        lines.append("")
        lines.append(
            f"_Questions evaluated: raw={n_raw or 0}, cleaned={n_cleaned or 0}._"
        )
    return "\n".join(lines)


def inject(readme_text: str, table: str) -> str:
    if START_MARKER not in readme_text or END_MARKER not in readme_text:
        raise SystemExit(
            f"README is missing markers {START_MARKER} / {END_MARKER}. "
            "Add them around the metric table first."
        )
    before, rest = readme_text.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    return f"{before}{START_MARKER}\n{table}\n{END_MARKER}{after}"


def main():
    parser = argparse.ArgumentParser(description="Inject eval results into README")
    parser.add_argument(
        "--input", default=str(REPO_ROOT / "results.json"),
        help="Harness results JSON (from --output)",
    )
    parser.add_argument(
        "--readme", default=str(REPO_ROOT / "README.md"), help="README to update",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(
            f"Results file not found: {input_path}. "
            "Run the harness with --output first (or use `make eval-report`)."
        )

    results = json.loads(input_path.read_text())
    if not isinstance(results, list):
        raise SystemExit(
            f"Expected a JSON list of per-QA results in {input_path}, "
            f"got {type(results).__name__}."
        )

    table = build_table(results)
    readme_path = Path(args.readme)
    updated = inject(readme_path.read_text(), table)
    readme_path.write_text(updated)
    print(f"  README metric table updated from {input_path} -> {readme_path}")


if __name__ == "__main__":
    main()
