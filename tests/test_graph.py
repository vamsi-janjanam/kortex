"""Unit tests for GraphSyncer.sync_all using a fake Neo4j driver."""

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class FakeSession:
    def __init__(self, queries):
        self.queries = queries

    def run(self, query, **params):
        self.queries.append((query, params))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeDriver:
    def __init__(self):
        self.queries = []

    def session(self):
        return FakeSession(self.queries)


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


def test_sync_all_syncs_entities_and_relationships(db_session):
    from app.models import Entity, EntityRelationship
    from pipelines.graph.sync import GraphSyncer

    entity_a = Entity(
        id=uuid.uuid4(),
        name="Auth Service",
        entity_type="Service",
        description="Handles authentication",
    )
    entity_b = Entity(
        id=uuid.uuid4(),
        name="API Gateway",
        entity_type="Service",
        description="Routes API traffic",
    )
    db_session.add_all([entity_a, entity_b])
    db_session.commit()

    relationship = EntityRelationship(
        id=uuid.uuid4(),
        from_entity_id=entity_a.id,
        to_entity_id=entity_b.id,
        rel_type="depends_on",
        confidence=0.9,
    )
    db_session.add(relationship)
    db_session.commit()

    try:
        driver = FakeDriver()
        syncer = GraphSyncer()
        result = syncer.sync_all(db_session, driver)

        assert result["entities_synced"] >= 2
        assert result["relationships_synced"] >= 1

        entity_queries = [q for q, p in driver.queries if "MERGE (e:Entity" in q]
        rel_queries = [q for q, p in driver.queries if "RELATES_TO" in q]

        assert len(entity_queries) == result["entities_synced"]
        assert len(rel_queries) == result["relationships_synced"]

        entity_a_params = [
            p
            for q, p in driver.queries
            if "MERGE (e:Entity" in q and p["id"] == str(entity_a.id)
        ]
        assert len(entity_a_params) == 1
        assert entity_a_params[0]["name"] == "Auth Service"
        assert entity_a_params[0]["entity_type"] == "Service"
        assert entity_a_params[0]["description"] == "Handles authentication"

        rel_params = [
            p
            for q, p in driver.queries
            if "RELATES_TO" in q and p["id"] == str(relationship.id)
        ]
        assert len(rel_params) == 1
        assert rel_params[0]["from_id"] == str(entity_a.id)
        assert rel_params[0]["to_id"] == str(entity_b.id)
        assert rel_params[0]["rel_type"] == "depends_on"
        assert rel_params[0]["confidence"] == 0.9
    finally:
        _cleanup(
            db_session,
            (EntityRelationship, relationship.id),
            (Entity, entity_a.id),
            (Entity, entity_b.id),
        )
