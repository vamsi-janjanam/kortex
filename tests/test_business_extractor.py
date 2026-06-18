"""Pure unit tests for the BusinessRuleExtractor (no DB, no Docker)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


def _fake_response(text: str):
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


def _patched_extractor(response_text: str):
    from pipelines.extraction.business_extractor import BusinessRuleExtractor

    with patch("anthropic.Anthropic") as mock_anthropic:
        client = MagicMock()
        client.messages.create.return_value = _fake_response(response_text)
        mock_anthropic.return_value = client
        return BusinessRuleExtractor()


def test_extract_parses_rules():
    payload = json.dumps(
        {
            "rules": [
                {
                    "name": "Auth uses OAuth 2.0 JWT",
                    "type": "decision",
                    "statement": "All API authentication uses OAuth 2.0 JWT tokens.",
                    "rationale": "API keys were too hard to rotate and revoke.",
                    "confidence": 0.9,
                }
            ]
        }
    )
    extractor = _patched_extractor(payload)

    result = extractor.extract("some text")

    assert "rules" in result
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["name"] == "Auth uses OAuth 2.0 JWT"
    assert rule["type"] == "decision"
    assert rule["rationale"] == "API keys were too hard to rotate and revoke."
    assert rule["confidence"] == 0.9


def test_extract_empty_text_returns_empty():
    extractor = _patched_extractor('{"rules": []}')
    assert extractor.extract("") == {"rules": []}
    assert extractor.extract("   ") == {"rules": []}


def test_extract_malformed_json_returns_empty():
    extractor = _patched_extractor("not valid json {{{")
    assert extractor.extract("some text") == {"rules": []}
