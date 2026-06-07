"""Integration test: API health endpoint."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "checks" in data
    assert data["status"] in ("healthy", "degraded")


def test_stats_endpoint_empty(client):
    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "document_count" in data
    assert "chunk_count" in data
    assert data["document_count"] >= 0


def test_documents_list_empty(client):
    resp = client.get("/api/v1/documents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
