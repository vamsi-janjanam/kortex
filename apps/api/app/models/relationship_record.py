import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RelationshipType(str, Enum):
    OWNS = "owns"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    CALLS = "calls"
    INHERITS = "inherits"
    REFERENCES = "references"
    OTHER = "other"


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    to_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    rel_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=RelationshipType.OTHER
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    from_entity: Mapped["Entity"] = relationship(  # noqa: F821
        "Entity", foreign_keys=[from_entity_id], back_populates="outgoing_relationships"
    )
    to_entity: Mapped["Entity"] = relationship(  # noqa: F821
        "Entity", foreign_keys=[to_entity_id], back_populates="incoming_relationships"
    )
