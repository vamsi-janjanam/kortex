from app.celery_app import celery_app
from app.core.neo4j_client import get_neo4j_driver
from app.database import SessionLocal


@celery_app.task(name="sync_graph", bind=True, max_retries=3)
def sync_graph_task(self):
    """Sync Entity and EntityRelationship rows from Postgres into Neo4j."""
    from pipelines.graph.sync import GraphSyncer

    db = SessionLocal()
    try:
        driver = get_neo4j_driver()
        syncer = GraphSyncer()
        result = syncer.sync_all(db, driver)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()
