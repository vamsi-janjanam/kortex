from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Entity, EntityRelationship


class GraphSyncer:
    """Syncs Entity and EntityRelationship rows from Postgres into Neo4j."""

    def sync_all(self, db: Session, driver) -> dict:
        entities = db.execute(select(Entity)).scalars().all()
        relationships = db.execute(select(EntityRelationship)).scalars().all()

        entities_synced = 0
        relationships_synced = 0

        with driver.session() as session:
            for entity in entities:
                session.run(
                    "MERGE (e:Entity {id: $id}) "
                    "SET e.name = $name, e.entity_type = $entity_type, "
                    "e.description = $description",
                    id=str(entity.id),
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                )
                entities_synced += 1

            for rel in relationships:
                session.run(
                    "MATCH (a:Entity {id: $from_id}), (b:Entity {id: $to_id}) "
                    "MERGE (a)-[r:RELATES_TO {id: $id}]->(b) "
                    "SET r.rel_type = $rel_type, r.confidence = $confidence",
                    from_id=str(rel.from_entity_id),
                    to_id=str(rel.to_entity_id),
                    id=str(rel.id),
                    rel_type=rel.rel_type,
                    confidence=rel.confidence,
                )
                relationships_synced += 1

        return {
            "entities_synced": entities_synced,
            "relationships_synced": relationships_synced,
        }
