"""Pure unit tests for the reasoning endpoint helpers (no Docker, no API keys)."""
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


def _mock_db_returning(rows):
    """A MagicMock db whose .execute(...).scalars().all() returns ``rows``."""
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = rows
    return db


def _rule(name="Auth uses OAuth", statement="Auth is OAuth 2.0 JWT", **kw):
    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        name=name,
        rule_type=kw.get("rule_type", "decision"),
        statement=statement,
        rationale=kw.get("rationale", "More secure than API keys"),
        status=kw.get("status", "active"),
        source_chunk_id=kw.get("source_chunk_id"),
    )


def _conflict(description="auth method disagreement", **kw):
    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        chunk_a_id=kw.get("chunk_a_id", uuid.uuid4()),
        chunk_b_id=kw.get("chunk_b_id", uuid.uuid4()),
        description=description,
        confidence_score=kw.get("confidence_score", 0.9),
        status=kw.get("status", "open"),
    )


def test_significant_words_drops_short_tokens():
    from app.api.v1.endpoints.reasoning import _significant_words

    words = _significant_words("How is the auth method configured?")
    assert "auth" in words
    assert "method" in words
    assert "configured" in words
    # Short noise words filtered out.
    assert "is" not in words
    assert "the" not in words


def test_fetch_business_rules_returns_and_dedupes():
    from app.api.v1.endpoints.reasoning import _fetch_business_rules

    shared_id = uuid.uuid4()
    rule = _rule(id=shared_id)
    # Same rule object returned twice (e.g. matched provenance + keyword).
    db = _mock_db_returning([rule, rule])

    result = _fetch_business_rules(
        db, [uuid.uuid4()], "What authentication method do we use?"
    )

    assert len(result) == 1
    assert result[0].name == "Auth uses OAuth"
    db.execute.assert_called_once()


def test_fetch_business_rules_no_conditions_returns_empty():
    from app.api.v1.endpoints.reasoning import _fetch_business_rules

    db = _mock_db_returning([_rule()])
    # No chunk ids and a question with no significant words -> no query at all.
    result = _fetch_business_rules(db, [], "is it ok?")

    assert result == []
    db.execute.assert_not_called()


def test_fetch_business_rules_caps_at_max():
    from app.api.v1.endpoints.reasoning import MAX_BUSINESS_RULES, _fetch_business_rules

    rows = [_rule(id=uuid.uuid4(), name=f"Rule {i}") for i in range(MAX_BUSINESS_RULES + 5)]
    db = _mock_db_returning(rows)

    result = _fetch_business_rules(db, [uuid.uuid4()], "authentication policy")

    assert len(result) == MAX_BUSINESS_RULES


def test_fetch_conflicts_returns_rows():
    from app.api.v1.endpoints.reasoning import _fetch_conflicts

    conflicts = [_conflict(), _conflict(description="rate limit disagreement")]
    db = _mock_db_returning(conflicts)

    result = _fetch_conflicts(db, [uuid.uuid4(), uuid.uuid4()])

    assert len(result) == 2
    assert result[1].description == "rate limit disagreement"
    db.execute.assert_called_once()


def test_fetch_conflicts_empty_chunk_ids_short_circuits():
    from app.api.v1.endpoints.reasoning import _fetch_conflicts

    db = _mock_db_returning([_conflict()])
    result = _fetch_conflicts(db, [])

    assert result == []
    db.execute.assert_not_called()


def test_reasoning_prompt_has_required_sections():
    from app.api.v1.endpoints.reasoning import REASONING_PROMPT

    filled = REASONING_PROMPT.format(
        context="ctx", rules="rules-here", conflicts="conf-here", question="q?"
    )
    assert "Business rules:" in filled
    assert "Known conflicts:" in filled
    assert "rules-here" in filled
    assert "conf-here" in filled
    # Must instruct the model to surface conflicts and prefer active rules.
    assert "conflict" in REASONING_PROMPT.lower()
    assert "active" in REASONING_PROMPT.lower()
