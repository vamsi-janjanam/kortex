"""Shared source-validation helpers for ingestion connectors.

Connectors accept an arbitrary ``source`` string that originates from an
(unauthenticated) API request. Without guards this allows:
  * reading ANY local file that exists (path traversal -> /etc/passwd)
  * fetching ANY URL via httpx (SSRF to internal services / cloud metadata
    at 169.254.169.254)

These helpers constrain file reads to an allowlisted root and reject URLs
that resolve to private / loopback / link-local / reserved IPs.

Stdlib only — no third-party dependencies.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

# Repo root is parents[2] of this file: pipelines/ingestion/security.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ALLOWED_ROOT = _REPO_ROOT / "data"


def _resolved_allowed_root(allowed_root: str | None = None) -> Path:
    """Resolve the allowlisted base directory for file ingestion.

    Precedence: explicit ``allowed_root`` arg > ``INGESTION_ALLOWED_ROOT`` env
    var > repo ``data/`` directory.
    """
    root = allowed_root or os.environ.get("INGESTION_ALLOWED_ROOT")
    if root:
        return Path(root).resolve()
    return _DEFAULT_ALLOWED_ROOT.resolve()


def is_url(source: str) -> bool:
    """True if ``source`` looks like an http(s) URL."""
    return source.startswith("http://") or source.startswith("https://")


def is_probably_path(source: str) -> bool:
    """True if ``source`` is most likely a filesystem path rather than a URL."""
    if is_url(source):
        return False
    return "://" not in source


def validate_file_path(source: str, allowed_root: str | None = None) -> Path:
    """Resolve ``source`` and confirm it lives inside the allowlisted root.

    Raises ``ValueError`` if the resolved path escapes the allowed root
    (path traversal / absolute paths such as ``/etc/passwd``).
    """
    root = _resolved_allowed_root(allowed_root)
    resolved = Path(source).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(
            f"Refused to ingest unsafe source: path '{resolved}' is outside "
            f"the allowed root '{root}'"
        )
    return resolved


def validate_url(source: str) -> str:
    """Validate ``source`` as a safe http(s) URL (SSRF guard).

    Requires an http/https scheme and rejects any URL whose hostname resolves
    to a private, loopback, link-local, reserved, or multicast IP address.
    Raises ``ValueError`` on any violation.
    """
    parsed = urlparse(source)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Refused to ingest unsafe source: unsupported URL scheme "
            f"'{parsed.scheme}' (only http/https allowed)"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(
            f"Refused to ingest unsafe source: URL has no hostname: {source}"
        )

    try:
        addrinfo = socket.getaddrinfo(hostname, parsed.port or None)
    except OSError as exc:
        raise ValueError(
            f"Refused to ingest unsafe source: cannot resolve host '{hostname}': {exc}"
        ) from exc

    for family, _type, _proto, _canon, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError(
                f"Refused to ingest unsafe source: host '{hostname}' resolves "
                f"to non-public address {ip_str}"
            )

    return source
