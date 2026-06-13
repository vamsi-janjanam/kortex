import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.neo4j_client import get_neo4j_driver

logger = logging.getLogger(__name__)

router = APIRouter()


class GraphNode(BaseModel):
    id: str
    label: str
    type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    confidence: float


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


@router.get("", response_model=GraphResponse)
def get_graph():
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            node_records = session.run(
                "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, "
                "e.entity_type AS entity_type"
            )
            nodes = [
                GraphNode(
                    id=record["id"],
                    label=record["name"],
                    type=record["entity_type"],
                )
                for record in node_records
            ]

            edge_records = session.run(
                "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
                "RETURN a.id AS source, b.id AS target, r.rel_type AS rel_type, "
                "r.confidence AS confidence"
            )
            edges = [
                GraphEdge(
                    source=record["source"],
                    target=record["target"],
                    type=record["rel_type"],
                    confidence=record["confidence"],
                )
                for record in edge_records
            ]

        return GraphResponse(nodes=nodes, edges=edges)
    except Exception:
        logger.warning("Failed to fetch graph from Neo4j", exc_info=True)
        return GraphResponse(nodes=[], edges=[])
