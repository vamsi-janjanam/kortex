"""Integration tests for the Knowledge Observability stats endpoints."""

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _cleanup(db_session, *models_and_ids):
    for model, obj_id in models_and_ids:
        obj = db_session.get(model, obj_id)
        if obj is not None:
            db_session.delete(obj)
    db_session.commit()


def test_stats_includes_avg_hallucination_risk(client):
    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "avg_hallucination_risk" in data
    assert 0.0 <= data["avg_hallucination_risk"] <= 1.0


def test_hallucination_risk_trend_empty(client):
    resp = client.get("/api/v1/stats/hallucination-risk/trend?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["days"] == 30
    assert len(data["data"]) == 30
    today = datetime.now(timezone.utc).date()
    assert data["data"][-1]["date"] == today.isoformat()
    for point in data["data"]:
        assert point["avg_hallucination_risk"] == 0.0
        assert point["chunk_count"] == 0


def test_hallucination_risk_trend_with_data(client, db_session):
    from app.models import Chunk, Document

    doc = Document(
        id=uuid.uuid4(), source_type="github", source_url="http://example.com"
    )
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        text="hello",
        position=0,
        hallucination_risk=0.6,
    )
    db_session.add_all([doc, chunk])
    db_session.commit()

    try:
        resp = client.get("/api/v1/stats/hallucination-risk/trend?days=30")
        assert resp.status_code == 200
        data = resp.json()
        today_point = data["data"][-1]
        assert today_point["chunk_count"] >= 1
        assert today_point["avg_hallucination_risk"] > 0.0
    finally:
        _cleanup(db_session, (Chunk, chunk.id), (Document, doc.id))


def test_conflicts_trend_empty(client):
    resp = client.get("/api/v1/stats/conflicts/trend?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["days"] == 30
    assert len(data["data"]) == 30
    today = datetime.now(timezone.utc).date()
    assert data["data"][-1]["date"] == today.isoformat()
    for point in data["data"]:
        assert point["detected"] == 0
        assert point["closed"] == 0


def test_conflicts_trend_with_data(client, db_session):
    from app.models import Chunk, Conflict, Document

    doc = Document(
        id=uuid.uuid4(), source_type="github", source_url="http://example.com"
    )
    chunk_a = Chunk(id=uuid.uuid4(), document_id=doc.id, text="a", position=0)
    chunk_b = Chunk(id=uuid.uuid4(), document_id=doc.id, text="b", position=1)
    db_session.add_all([doc, chunk_a, chunk_b])
    db_session.commit()

    now = datetime.now(timezone.utc)
    conflict = Conflict(
        id=uuid.uuid4(),
        chunk_a_id=chunk_a.id,
        chunk_b_id=chunk_b.id,
        confidence_score=0.9,
        status="resolved",
        detected_at=now,
        resolved_at=now,
    )
    db_session.add(conflict)
    db_session.commit()

    try:
        resp = client.get("/api/v1/stats/conflicts/trend?days=30")
        assert resp.status_code == 200
        data = resp.json()
        today_point = data["data"][-1]
        assert today_point["detected"] == 1
        assert today_point["closed"] == 1
    finally:
        _cleanup(
            db_session,
            (Conflict, conflict.id),
            (Chunk, chunk_a.id),
            (Chunk, chunk_b.id),
            (Document, doc.id),
        )


def test_quality_by_source_empty(client):
    resp = client.get("/api/v1/stats/quality/by-source")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"] == []


def test_quality_by_source_with_data(client, db_session):
    from app.models import Chunk, Document

    doc = Document(
        id=uuid.uuid4(), source_type="github", source_url="http://example.com"
    )
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        text="hello",
        position=0,
        freshness_score=0.8,
        trust_score=0.9,
        conflict_risk=0.1,
    )
    db_session.add_all([doc, chunk])
    db_session.commit()

    try:
        resp = client.get("/api/v1/stats/quality/by-source")
        assert resp.status_code == 200
        data = resp.json()["data"]
        github_entry = next((d for d in data if d["source_type"] == "github"), None)
        assert github_entry is not None
        assert github_entry["chunk_count"] >= 1
        assert 0.0 <= github_entry["avg_freshness_score"] <= 1.0
        assert 0.0 <= github_entry["avg_trust_score"] <= 1.0
    finally:
        _cleanup(db_session, (Chunk, chunk.id), (Document, doc.id))


def test_quality_distribution_empty(client):
    resp = client.get("/api/v1/stats/quality/distribution")
    assert resp.status_code == 200
    data = resp.json()
    expected_buckets = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    assert [b["bucket"] for b in data["freshness"]] == expected_buckets
    assert [b["bucket"] for b in data["trust"]] == expected_buckets
    assert [b["bucket"] for b in data["hallucination"]] == expected_buckets
    for b in data["freshness"]:
        assert b["count"] == 0
    for b in data["trust"]:
        assert b["count"] == 0
    for b in data["hallucination"]:
        assert b["count"] == 0


def test_quality_distribution_with_data(client, db_session):
    from app.models import Chunk, Document

    doc = Document(
        id=uuid.uuid4(), source_type="github", source_url="http://example.com"
    )
    chunk_low = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        text="low",
        position=0,
        freshness_score=0.1,
        trust_score=0.1,
    )
    chunk_high = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        text="high",
        position=1,
        freshness_score=0.95,
        trust_score=1.0,
    )
    db_session.add_all([doc, chunk_low, chunk_high])
    db_session.commit()

    try:
        resp = client.get("/api/v1/stats/quality/distribution")
        assert resp.status_code == 200
        data = resp.json()
        freshness_by_bucket = {b["bucket"]: b["count"] for b in data["freshness"]}
        trust_by_bucket = {b["bucket"]: b["count"] for b in data["trust"]}
        assert freshness_by_bucket["0.0-0.2"] >= 1
        assert freshness_by_bucket["0.8-1.0"] >= 1
        assert trust_by_bucket["0.0-0.2"] >= 1
        assert trust_by_bucket["0.8-1.0"] >= 1
    finally:
        _cleanup(
            db_session,
            (Chunk, chunk_low.id),
            (Chunk, chunk_high.id),
            (Document, doc.id),
        )


def test_staleness_by_age_empty(client):
    resp = client.get("/api/v1/stats/staleness/by-age")
    assert resp.status_code == 200
    data = resp.json()
    expected_buckets = ["0-30d", "30-90d", "90-180d", "180-365d", "365d+"]
    assert [b["age_bucket"] for b in data["data"]] == expected_buckets
    for b in data["data"]:
        assert b["chunk_count"] == 0
        assert b["avg_freshness_score"] == 0.0


def test_staleness_by_age_with_data(client, db_session):
    from app.models import Chunk, Document

    doc = Document(
        id=uuid.uuid4(), source_type="github", source_url="http://example.com"
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    chunk_new = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        text="new",
        position=0,
        freshness_score=0.9,
        created_at=now,
    )
    chunk_old = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        text="old",
        position=1,
        freshness_score=0.1,
        created_at=now - timedelta(days=400),
    )
    db_session.add_all([doc, chunk_new, chunk_old])
    db_session.commit()

    try:
        resp = client.get("/api/v1/stats/staleness/by-age")
        assert resp.status_code == 200
        data = {b["age_bucket"]: b for b in resp.json()["data"]}
        assert data["0-30d"]["chunk_count"] >= 1
        assert data["365d+"]["chunk_count"] >= 1
    finally:
        _cleanup(
            db_session, (Chunk, chunk_new.id), (Chunk, chunk_old.id), (Document, doc.id)
        )
