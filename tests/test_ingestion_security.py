"""Unit tests for the ingestion source-validation guards.

Pure-Python: no DB or live network. socket.getaddrinfo is monkeypatched so
URL validation is deterministic and offline.
"""

import socket
from pathlib import Path

import pytest

from pipelines.ingestion.security import (
    validate_file_path,
    validate_url,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATA_ROOT = _REPO_ROOT / "data"


def _fake_getaddrinfo(ip: str):
    """Return a getaddrinfo replacement that always resolves to ``ip``."""

    def _inner(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]

    return _inner


# --- validate_url ---------------------------------------------------------


def test_validate_url_rejects_cloud_metadata(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("169.254.169.254"))
    with pytest.raises(ValueError):
        validate_url("http://169.254.169.254/latest/meta-data/")


def test_validate_url_rejects_localhost(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    with pytest.raises(ValueError):
        validate_url("http://localhost/")


def test_validate_url_rejects_loopback_ip(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    with pytest.raises(ValueError):
        validate_url("http://127.0.0.1/")


def test_validate_url_rejects_private_10_host(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.5"))
    with pytest.raises(ValueError):
        validate_url("http://internal.example.com/")


def test_validate_url_rejects_file_scheme():
    # No DNS lookup needed — scheme check fires first.
    with pytest.raises(ValueError):
        validate_url("file:///etc/passwd")


def test_validate_url_accepts_public_https(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    assert validate_url("https://example.com/docs.md") == "https://example.com/docs.md"


# --- validate_file_path ---------------------------------------------------


def test_validate_file_path_rejects_etc_passwd():
    with pytest.raises(ValueError):
        validate_file_path("/etc/passwd")


def test_validate_file_path_rejects_outside_root(tmp_path):
    outside = tmp_path / "secret.md"
    outside.write_text("nope")
    with pytest.raises(ValueError):
        validate_file_path(str(outside))


def test_validate_file_path_rejects_traversal():
    with pytest.raises(ValueError):
        validate_file_path(str(_DATA_ROOT / ".." / "etc" / "passwd"))


def test_validate_file_path_accepts_file_in_data_root():
    target = _DATA_ROOT / "seed_corpus" / "api_docs_v1.md"
    resolved = validate_file_path(str(target))
    assert resolved == target.resolve()


def test_validate_file_path_honors_explicit_allowed_root(tmp_path):
    inside = tmp_path / "doc.md"
    inside.write_text("hi")
    resolved = validate_file_path(str(inside), allowed_root=str(tmp_path))
    assert resolved == inside.resolve()
