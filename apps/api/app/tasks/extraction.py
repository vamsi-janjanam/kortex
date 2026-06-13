import uuid

from sqlalchemy import select

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Chunk, Entity, EntityRelationship


@celery_app.task(name="extract_entities", bind=True, max_retries=3)
def extract_entities_task(self, document_id: str):
    """Extract entities and relationships from a document's chunks and persist them."""
    from pipelines.extraction.entity_extractor import EntityExtractor

    db = SessionLocal()
    try:
        chunks = (
            db.execute(select(Chunk).where(Chunk.document_id == uuid.UUID(document_id)))
            .scalars()
            .all()
        )

        extractor = EntityExtractor()

        # Map of lowercased entity name -> Entity id, seeded with existing entities
        name_to_id: dict[str, uuid.UUID] = {}
        for existing in db.execute(select(Entity)).scalars().all():
            name_to_id[existing.name.lower()] = existing.id

        entities_extracted = 0
        relationships_extracted = 0
        pending_relationships: list[dict] = []

        for chunk in chunks:
            result = extractor.extract(chunk.text)
            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            for entity_dict in entities:
                name = entity_dict.get("name")
                if not name:
                    continue

                key = name.lower()
                if key in name_to_id:
                    continue

                entity = Entity(
                    name=name,
                    entity_type=entity_dict.get("type", "Other"),
                    description=entity_dict.get("description"),
                )
                db.add(entity)
                db.flush()

                name_to_id[key] = entity.id
                entities_extracted += 1

            pending_relationships.extend(relationships)

        for rel_dict in pending_relationships:
            from_name = rel_dict.get("from")
            to_name = rel_dict.get("to")
            if not from_name or not to_name:
                continue

            from_id = name_to_id.get(from_name.lower())
            to_id = name_to_id.get(to_name.lower())

            if not from_id or not to_id:
                continue
            if from_id == to_id:
                continue

            relationship = EntityRelationship(
                from_entity_id=from_id,
                to_entity_id=to_id,
                rel_type=rel_dict.get("type", "other"),
                confidence=rel_dict.get("confidence", 1.0),
            )
            db.add(relationship)
            relationships_extracted += 1

        db.commit()

        from app.tasks.graph import sync_graph_task

        sync_graph_task.delay()

        return {
            "document_id": document_id,
            "entities_extracted": entities_extracted,
            "relationships_extracted": relationships_extracted,
        }
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()
