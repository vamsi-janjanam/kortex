"""Unit tests for the Slack source connector.

``slack_sdk.WebClient`` is mocked via a fake client injected into
``SlackConnector._client`` — no live token and no network access.
"""

import pytest

from app.config import settings
from pipelines.ingestion.slack import SlackConnector


class _FakeWebClient:
    """Minimal stand-in for slack_sdk.WebClient used in tests."""

    def __init__(self):
        self.history = {
            "messages": [
                {"ts": "1.0", "user": "U1", "text": "First top-level message"},
                {
                    "ts": "2.0",
                    "user": "U2",
                    "text": "Thread parent message",
                    "thread_ts": "2.0",
                    "reply_count": 1,
                },
                {"ts": "3.0", "user": "U3", "text": "   "},  # blank -> filtered
                {
                    "ts": "4.0",
                    "user": "U4",
                    "text": "joined",
                    "subtype": "channel_join",
                },  # noise -> filtered
            ]
        }
        self.replies = {
            "messages": [
                {
                    "ts": "2.0",
                    "user": "U2",
                    "text": "Thread parent message",
                    "thread_ts": "2.0",
                },
                {
                    "ts": "2.1",
                    "user": "U5",
                    "text": "A reply inside the thread",
                    "thread_ts": "2.0",
                },
            ]
        }

    def conversations_history(self, channel, cursor=None, limit=200):
        return self.history

    def conversations_replies(self, channel, ts, cursor=None, limit=200):
        return self.replies

    def conversations_list(self, cursor=None, limit=200, types=None):
        return {"channels": [{"id": "C0123", "name": "general"}]}


def _install_fake_slack(monkeypatch, client):
    monkeypatch.setattr(SlackConnector, "_client", lambda self: client)


def test_returns_rawchunks_with_expected_metadata(monkeypatch):
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-fake", raising=False)
    _install_fake_slack(monkeypatch, _FakeWebClient())

    chunks = SlackConnector().ingest("C0123")

    assert isinstance(chunks, list)
    assert chunks
    for chunk in chunks:
        assert set(chunk["metadata"].keys()) == {
            "source",
            "channel",
            "user",
            "ts",
            "thread_ts",
        }
        assert chunk["text"].strip()
        assert chunk["metadata"]["channel"] == "C0123"


def test_thread_replies_included(monkeypatch):
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-fake", raising=False)
    _install_fake_slack(monkeypatch, _FakeWebClient())

    chunks = SlackConnector().ingest("C0123")
    texts = {c["text"] for c in chunks}

    assert "A reply inside the thread" in texts


def test_blank_and_noise_messages_filtered(monkeypatch):
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-fake", raising=False)
    _install_fake_slack(monkeypatch, _FakeWebClient())

    chunks = SlackConnector().ingest("C0123")
    texts = {c["text"] for c in chunks}

    assert "   " not in texts
    assert "joined" not in texts
    # Each surviving message appears exactly once (no dupes from thread pull).
    ts_values = [c["metadata"]["ts"] for c in chunks]
    assert len(ts_values) == len(set(ts_values))


def test_resolves_channel_name(monkeypatch):
    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-fake", raising=False)
    _install_fake_slack(monkeypatch, _FakeWebClient())

    chunks = SlackConnector().ingest("#general")
    assert chunks
    assert all(c["metadata"]["channel"] == "C0123" for c in chunks)


def test_empty_token_raises(monkeypatch):
    monkeypatch.setattr(settings, "slack_bot_token", "", raising=False)
    with pytest.raises(ValueError):
        SlackConnector().ingest("C0123")
