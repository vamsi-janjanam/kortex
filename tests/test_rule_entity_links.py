"""Pure unit tests for the multi-hop governed-rule lookup (no Docker, no API keys)."""
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


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


def _mock_db(entity_rows, rule_rows):
    """A MagicMock db whose first ``.execute`` resolves entities (``.all()``)
    and whose second resolves rules (``.scalars().all()``).
    """
    db = MagicMock()
    entity_result = MagicMock()
    entity_result.all.return_value = entity_rows
    rule_result = MagicMock()
    rule_result.scalars.return_value.all.return_value = rule_rows
    db.execute.side_effect = [entity_result, rule_result]
    return db


def test_fetch_governed_rules_matches_entity_and_returns_rules():
    from app.api.v1.endpoints.reasoning import _fetch_governed_rules

    entity_id = uuid.uuid4()
    # "OAuth" appears in the chunk text -> entity matched -> its rule returned.
    entity_rows = [(entity_id, "OAuth"), (uuid.uuid4(), "Webhooks")]
    rule = _rule()
    db = _mock_db(entity_rows, [rule])

    result = _fetch_governed_rules(db, ["We migrated authentication to OAuth 2.0."])

    assert len(result) == 1
    assert result[0].name == "Auth uses OAuth"
    assert db.execute.call_count == 2


def test_fetch_governed_rules_no_entity_match_short_circuits():
    from app.api.v1.endpoints.reasoning import _fetch_governed_rules

    # No known entity name appears in the chunk text -> no rule query at all.
    entity_rows = [(uuid.uuid4(), "SAML"), (uuid.uuid4(), "LDAP")]
    db = _mock_db(entity_rows, [_rule()])

    result = _fetch_governed_rules(db, ["Rate limits are now tier-based."])

    assert result == []
    # Only the entity lookup ran; the rule query was never reached.
    assert db.execute.call_count == 1


def test_fetch_governed_rules_empty_chunks_returns_empty():
    from app.api.v1.endpoints.reasoning import _fetch_governed_rules

    db = _mock_db([(uuid.uuid4(), "OAuth")], [_rule()])
    result = _fetch_governed_rules(db, [])

    assert result == []
    db.execute.assert_not_called()


def test_fetch_governed_rules_dedupes_and_caps():
    from app.api.v1.endpoints.reasoning import (
        MAX_BUSINESS_RULES,
        _fetch_governed_rules,
    )

    entity_rows = [(uuid.uuid4(), "OAuth")]
    # More distinct rules than the cap, plus a duplicate of the first.
    rules = [_rule(id=uuid.uuid4(), name=f"Rule {i}") for i in range(MAX_BUSINESS_RULES + 5)]
    rules.append(rules[0])
    db = _mock_db(entity_rows, rules)

    result = _fetch_governed_rules(db, ["auth via OAuth"])

    assert len(result) == MAX_BUSINESS_RULES
    # No duplicate rule ids in the result.
    assert len({r.id for r in result}) == len(result)


def test_fetch_governed_rules_degrades_on_failure():
    from app.api.v1.endpoints.reasoning import _fetch_governed_rules

    db = MagicMock()
    db.execute.side_effect = RuntimeError("db down")

    result = _fetch_governed_rules(db, ["auth via OAuth"])

    assert result == []
