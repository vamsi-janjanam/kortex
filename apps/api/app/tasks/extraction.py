import uuid

from sqlalchemy import select

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import (
    BusinessRule,
    BusinessRuleEntityLink,
    Chunk,
    Entity,
    EntityRelationship,
)


@celery_app.task(name="extract_entities", bind=True, max_retries=3)
def extract_entities_task(self, document_id: str):
    """Extract entities and relationships from a document's chunks and persist them."""
    from pipelines.extraction.business_extractor import BusinessRuleExtractor
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

        rule_extractor = BusinessRuleExtractor()
        seen_rule_names: set[str] = set()
        business_rules_extracted = 0
        seen_rule_entity_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
        rule_entity_links = 0

        for chunk in chunks:
            rule_result = rule_extractor.extract(chunk.text)
            chunk_text_lower = chunk.text.lower()
            for rule in rule_result.get("rules", []):
                name = rule.get("name")
                statement = rule.get("statement")
                if not name or not statement:
                    continue

                key = name.lower()
                if key in seen_rule_names:
                    continue
                seen_rule_names.add(key)

                business_rule = BusinessRule(
                    name=name,
                    rule_type=rule.get("type", "decision"),
                    statement=statement,
                    rationale=(rule.get("rationale") or None),
                    source_chunk_id=chunk.id,
                    document_id=uuid.UUID(document_id),
                    confidence=rule.get("confidence", 1.0),
                )
                db.add(business_rule)
                db.flush()
                business_rules_extracted += 1

                # Link the rule to the entities mentioned in THIS chunk so
                # reasoning can do chunk -> entity -> governing rule traversal.
                for entity_name, entity_id in name_to_id.items():
                    if entity_name not in chunk_text_lower:
                        continue
                    pair = (business_rule.id, entity_id)
                    if pair in seen_rule_entity_pairs:
                        continue
                    seen_rule_entity_pairs.add(pair)
                    db.add(
                        BusinessRuleEntityLink(
                            business_rule_id=business_rule.id,
                            entity_id=entity_id,
                        )
                    )
                    rule_entity_links += 1

        db.commit()

        from app.tasks.graph import sync_graph_task

        sync_graph_task.delay()

        return {
            "document_id": document_id,
            "entities_extracted": entities_extracted,
            "relationships_extracted": relationships_extracted,
            "business_rules_extracted": business_rules_extracted,
            "rule_entity_links": rule_entity_links,
        }
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()
