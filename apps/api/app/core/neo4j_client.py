from functools import lru_cache

from neo4j import Driver, GraphDatabase

from app.config import settings


@lru_cache(maxsize=1)
def get_neo4j_driver() -> Driver:
    """Return a singleton Neo4j driver instance."""
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
