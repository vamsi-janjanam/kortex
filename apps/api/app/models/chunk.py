import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Qdrant point ID (stored as string to handle UUID or int IDs)
    embedding_id: Mapped[str | None] = mapped_column(Text)

    # Scoring
    freshness_score: Mapped[float] = mapped_column(Float, default=1.0)
    trust_score: Mapped[float] = mapped_column(Float, default=1.0)
    completeness_score: Mapped[float] = mapped_column(Float, default=1.0)
    conflict_risk: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")  # noqa: F821
    lineage: Mapped[list["LineageRecord"]] = relationship(  # noqa: F821
        "LineageRecord", back_populates="chunk"
    )
    conflicts_as_a: Mapped[list["Conflict"]] = relationship(  # noqa: F821
        "Conflict", foreign_keys="Conflict.chunk_a_id", back_populates="chunk_a"
    )
    conflicts_as_b: Mapped[list["Conflict"]] = relationship(  # noqa: F821
        "Conflict", foreign_keys="Conflict.chunk_b_id", back_populates="chunk_b"
    )
