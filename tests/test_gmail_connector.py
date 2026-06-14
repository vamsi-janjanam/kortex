"""Unit tests for the Gmail connector.

Pure-Python: no live OAuth, no network. The gmail ``service`` object is faked
and ``GmailConnector._service`` is monkeypatched to return it. OAuth credential
paths are set/cleared via the settings singleton.
"""

import base64

import pytest

from app.config import settings
from pipelines.ingestion.base import RawChunk
from pipelines.ingestion.gmail import GmailConnector


def _b64url(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")


class _FakeExec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeMessages:
    def __init__(self, list_result, get_results):
        self._list_result = list_result
        self._get_results = get_results

    def list(self, userId, q, pageToken=None):  # noqa: N803 — gmail API kwargs
        return _FakeExec(self._list_result)

    def get(self, userId, id, format):  # noqa: A002,N803 — gmail API kwargs
        return _FakeExec(self._get_results[id])


class _FakeUsers:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class _FakeService:
    def __init__(self, list_result, get_results):
        self._users = _FakeUsers(_FakeMessages(list_result, get_results))

    def users(self):
        return self._users


def _build_message(msg_id, thread_id, subject, sender, date, body_text):
    return {
        "id": msg_id,
        "threadId": thread_id,
        "snippet": "snippet fallback text",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
                {"name": "Date", "value": date},
            ],
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64url("<p>ignore</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64url(body_text)}},
            ],
        },
    }


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "gmail_token_path", "/tmp/token.json")
    monkeypatch.setattr(settings, "gmail_credentials_path", "")


def test_ingest_returns_rawchunks_with_metadata(monkeypatch, configured):
    body = "Hello world. " * 20
    msg = _build_message(
        "m1", "t1", "Quarterly update", "alice@example.com", "Mon, 1 Jan 2026 09:00:00", body
    )
    fake = _FakeService(
        list_result={"messages": [{"id": "m1"}]},
        get_results={"m1": msg},
    )
    monkeypatch.setattr(GmailConnector, "_service", lambda self: fake)

    chunks = GmailConnector().ingest("newer_than:30d")

    assert isinstance(chunks, list)
    assert len(chunks) >= 1
    first = chunks[0]
    assert isinstance(first, dict)  # RawChunk is a TypedDict
    assert set(first["metadata"]) == {
        "source",
        "message_id",
        "thread_id",
        "sender",
        "subject",
        "date",
    }
    assert first["metadata"]["source"] == "newer_than:30d"
    assert first["metadata"]["message_id"] == "m1"
    assert first["metadata"]["thread_id"] == "t1"
    assert first["metadata"]["sender"] == "alice@example.com"
    assert first["metadata"]["subject"] == "Quarterly update"
    # body was base64url-decoded, not the html part
    assert "Hello world." in first["text"]
    assert "ignore" not in first["text"]


def test_ingest_paginates(monkeypatch, configured):
    # The fake list ignores pageToken and never returns nextPageToken, so this
    # just confirms multiple message ids are all fetched and emitted.
    fake = _FakeService(
        list_result={"messages": [{"id": "m1"}, {"id": "m2"}]},
        get_results={
            "m1": _build_message("m1", "t1", "s1", "a@x.com", "d1", "First body text."),
            "m2": _build_message("m2", "t2", "s2", "b@x.com", "d2", "Second body text."),
        },
    )
    monkeypatch.setattr(GmailConnector, "_service", lambda self: fake)

    chunks = GmailConnector().ingest("label:inbox")
    ids = {c["metadata"]["message_id"] for c in chunks}
    assert ids == {"m1", "m2"}


def test_ingest_falls_back_to_snippet(monkeypatch, configured):
    msg = {
        "id": "m9",
        "threadId": "t9",
        "snippet": "only the snippet survives",
        "payload": {
            "mimeType": "text/html",
            "headers": [{"name": "Subject", "value": "no plaintext"}],
            "body": {},
        },
    }
    fake = _FakeService(
        list_result={"messages": [{"id": "m9"}]},
        get_results={"m9": msg},
    )
    monkeypatch.setattr(GmailConnector, "_service", lambda self: fake)

    chunks = GmailConnector().ingest("from:noone@x.com")
    assert len(chunks) == 1
    assert chunks[0]["text"] == "only the snippet survives"


def test_empty_messages_returns_empty_list(monkeypatch, configured):
    fake = _FakeService(list_result={}, get_results={})
    monkeypatch.setattr(GmailConnector, "_service", lambda self: fake)
    assert GmailConnector().ingest("newer_than:1d") == []


def test_missing_config_raises_value_error(monkeypatch):
    monkeypatch.setattr(settings, "gmail_token_path", "")
    monkeypatch.setattr(settings, "gmail_credentials_path", "")
    with pytest.raises(ValueError):
        GmailConnector()._credentials()
