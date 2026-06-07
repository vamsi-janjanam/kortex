import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EntityType(str, Enum):
    SERVICE = "Service"
    API = "API"
    TEAM = "Team"
    PERSON = "Person"
    RULE = "Rule"
    CONCEPT = "Concept"
    OTHER = "Other"


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=EntityType.OTHER
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    outgoing_relationships: Mapped[list["EntityRelationship"]] = relationship(  # noqa: F821
        "EntityRelationship",
        foreign_keys="EntityRelationship.from_entity_id",
        back_populates="from_entity",
    )
    incoming_relationships: Mapped[list["EntityRelationship"]] = relationship(  # noqa: F821
        "EntityRelationship",
        foreign_keys="EntityRelationship.to_entity_id",
        back_populates="to_entity",
    )
