"""Pure unit tests for the business-understanding eval judge.

No Docker, no live API: the anthropic client is faked. Validates JSON parsing,
markdown-fence handling, and the defensive fallback.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from pipelines.eval.harness import QAPair, judge_business_understanding


class _FakeMessages:
    def __init__(self, text):
        self._text = text

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=self._text)])


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def _qa(has_conflict=False):
    return QAPair(
        id="q1",
        question="Why did auth change?",
        reference_answer="Moved to OAuth for per-tenant scoping.",
        has_seeded_conflict=has_conflict,
    )


def test_parses_business_scores():
    client = _FakeClient('{"explains_rationale": 0.8, "surfaces_conflict": true}')
    out = judge_business_understanding(_qa(True), "because ...", client, "model")
    assert out["explains_rationale"] == 0.8
    assert out["surfaces_conflict"] is True


def test_strips_markdown_fence():
    client = _FakeClient('```json\n{"explains_rationale": 0.5, "surfaces_conflict": false}\n```')
    out = judge_business_understanding(_qa(), "answer", client, "model")
    assert out["explains_rationale"] == 0.5
    assert out["surfaces_conflict"] is False


def test_malformed_json_falls_back():
    client = _FakeClient("not json at all")
    out = judge_business_understanding(_qa(), "answer", client, "model")
    assert out == {"explains_rationale": 0.0, "surfaces_conflict": False}
