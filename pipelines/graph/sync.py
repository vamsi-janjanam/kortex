from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BusinessRule,
    BusinessRuleEntityLink,
    Entity,
    EntityRelationship,
)


class GraphSyncer:
    """Syncs Entity and EntityRelationship rows from Postgres into Neo4j."""

    def sync_all(self, db: Session, driver) -> dict:
        entities = db.execute(select(Entity)).scalars().all()
        relationships = db.execute(select(EntityRelationship)).scalars().all()
        business_rules = db.execute(select(BusinessRule)).scalars().all()
        governs_links = db.execute(select(BusinessRuleEntityLink)).scalars().all()

        entities_synced = 0
        relationships_synced = 0
        business_rules_synced = 0
        governs_edges_synced = 0

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

            for rule in business_rules:
                session.run(
                    "MERGE (r:BusinessRule {id: $id}) "
                    "SET r.name = $name, r.rule_type = $rule_type, "
                    "r.statement = $statement, r.status = $status",
                    id=str(rule.id),
                    name=rule.name,
                    rule_type=rule.rule_type,
                    statement=rule.statement,
                    status=rule.status,
                )
                business_rules_synced += 1

            for rule in business_rules:
                if rule.supersedes_id is None:
                    continue
                session.run(
                    "MATCH (a:BusinessRule {id: $from_id}), (b:BusinessRule {id: $to_id}) "
                    "MERGE (a)-[:SUPERSEDES]->(b)",
                    from_id=str(rule.id),
                    to_id=str(rule.supersedes_id),
                )

            for link in governs_links:
                session.run(
                    "MATCH (r:BusinessRule {id: $rule_id}), (e:Entity {id: $entity_id}) "
                    "MERGE (r)-[:GOVERNS]->(e)",
                    rule_id=str(link.business_rule_id),
                    entity_id=str(link.entity_id),
                )
                governs_edges_synced += 1

        return {
            "entities_synced": entities_synced,
            "relationships_synced": relationships_synced,
            "business_rules_synced": business_rules_synced,
            "governs_edges_synced": governs_edges_synced,
        }
