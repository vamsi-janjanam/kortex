import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BusinessRuleEntityLink(Base):
    """Association linking a :class:`BusinessRule` to an :class:`Entity` it governs.

    This is what turns the decision graph and the entity graph from two islands
    into one: a rule extracted from a chunk is linked to the entities mentioned
    in that same chunk, enabling multi-hop reasoning
    (``chunk -> entity -> governing rule``) and a ``GOVERNS`` edge in Neo4j.
    """

    __tablename__ = "business_rule_entity_links"
    __table_args__ = (
        UniqueConstraint("business_rule_id", "entity_id", name="uq_rule_entity_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    business_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_rules.id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
