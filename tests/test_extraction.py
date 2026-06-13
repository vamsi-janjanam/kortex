"""Tests for the entity/relationship extraction task."""
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


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


def _make_document_with_chunks(db_session, texts):
    from app.models import Chunk, Document

    doc = Document(id=uuid.uuid4(), source_type="github", source_url="http://example.com")
    chunks = []
    for i, text in enumerate(texts):
        chunk = Chunk(id=uuid.uuid4(), document_id=doc.id, text=text, position=i)
        chunks.append(chunk)

    db_session.add(doc)
    db_session.add_all(chunks)
    db_session.commit()
    return doc, chunks


def test_extract_entities_creates_entities_and_relationships(db_session):
    from app.models import Entity, EntityRelationship
    from app.tasks.extraction import extract_entities_task

    doc, chunks = _make_document_with_chunks(db_session, ["PaymentsAPI is owned by the Payments Team."])

    mock_result = {
        "entities": [
            {"name": "PaymentsAPI", "type": "API", "description": "REST API for payments"},
            {"name": "Payments Team", "type": "Team", "description": "Owns the Payments API"},
        ],
        "relationships": [
            {"from": "Payments Team", "to": "PaymentsAPI", "type": "owns", "confidence": 0.9},
        ],
    }

    try:
        with patch(
            "pipelines.extraction.entity_extractor.EntityExtractor.extract",
            return_value=mock_result,
        ):
            result = extract_entities_task.run(str(doc.id))

        assert result["document_id"] == str(doc.id)
        assert result["entities_extracted"] == 2
        assert result["relationships_extracted"] == 1

        entities = db_session.query(Entity).filter(
            Entity.name.in_(["PaymentsAPI", "Payments Team"])
        ).all()
        by_name = {e.name: e for e in entities}
        assert len(entities) == 2
        assert by_name["PaymentsAPI"].entity_type == "API"
        assert by_name["Payments Team"].entity_type == "Team"

        rels = db_session.query(EntityRelationship).filter(
            EntityRelationship.from_entity_id == by_name["Payments Team"].id,
            EntityRelationship.to_entity_id == by_name["PaymentsAPI"].id,
        ).all()
        assert len(rels) == 1
        assert rels[0].rel_type == "owns"
        assert rels[0].confidence == pytest.approx(0.9)
    finally:
        for chunk in chunks:
            db_session.delete(chunk)
        db_session.delete(doc)
        db_session.commit()
        db_session.query(EntityRelationship).delete()
        db_session.query(Entity).filter(
            Entity.name.in_(["PaymentsAPI", "Payments Team"])
        ).delete(synchronize_session=False)
        db_session.commit()


def test_extract_entities_dedupes_across_calls(db_session):
    from app.models import Entity
    from app.tasks.extraction import extract_entities_task

    doc1, chunks1 = _make_document_with_chunks(db_session, ["PaymentsAPI is a service."])
    doc2, chunks2 = _make_document_with_chunks(db_session, ["paymentsapi is mentioned again."])

    mock_result_1 = {
        "entities": [{"name": "PaymentsAPI", "type": "API", "description": "REST API for payments"}],
        "relationships": [],
    }
    mock_result_2 = {
        "entities": [{"name": "paymentsapi", "type": "API", "description": "Same API, lowercase name"}],
        "relationships": [],
    }

    try:
        with patch(
            "pipelines.extraction.entity_extractor.EntityExtractor.extract",
            return_value=mock_result_1,
        ):
            result1 = extract_entities_task.run(str(doc1.id))
        assert result1["entities_extracted"] == 1

        with patch(
            "pipelines.extraction.entity_extractor.EntityExtractor.extract",
            return_value=mock_result_2,
        ):
            result2 = extract_entities_task.run(str(doc2.id))
        assert result2["entities_extracted"] == 0

        entities = db_session.query(Entity).filter(
            Entity.name.ilike("paymentsapi")
        ).all()
        assert len(entities) == 1
    finally:
        for chunk in chunks1 + chunks2:
            db_session.delete(chunk)
        db_session.delete(doc1)
        db_session.delete(doc2)
        db_session.commit()
        db_session.query(Entity).filter(Entity.name.ilike("paymentsapi")).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_extract_entities_skips_unknown_relationship(db_session):
    from app.models import Entity, EntityRelationship
    from app.tasks.extraction import extract_entities_task

    doc, chunks = _make_document_with_chunks(db_session, ["Some service exists."])

    mock_result = {
        "entities": [
            {"name": "SomeService", "type": "Service", "description": "A service"},
        ],
        "relationships": [
            {"from": "SomeService", "to": "NonExistentEntity", "type": "uses", "confidence": 0.8},
        ],
    }

    try:
        with patch(
            "pipelines.extraction.entity_extractor.EntityExtractor.extract",
            return_value=mock_result,
        ):
            result = extract_entities_task.run(str(doc.id))

        assert result["entities_extracted"] == 1
        assert result["relationships_extracted"] == 0

        entity = db_session.query(Entity).filter(Entity.name == "SomeService").one()
        rels = db_session.query(EntityRelationship).filter(
            (EntityRelationship.from_entity_id == entity.id)
            | (EntityRelationship.to_entity_id == entity.id)
        ).all()
        assert rels == []
    finally:
        for chunk in chunks:
            db_session.delete(chunk)
        db_session.delete(doc)
        db_session.commit()
        db_session.query(Entity).filter(Entity.name == "SomeService").delete(
            synchronize_session=False
        )
        db_session.commit()
