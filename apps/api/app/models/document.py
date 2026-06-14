import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SourceType(str, Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    GITHUB = "github"
    SLACK = "slack"
    GMAIL = "gmail"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    NOTION = "notion"
    OTHER = "other"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    raw_content_ref: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(  # noqa: F821
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )
    lineage_records: Mapped[list["LineageRecord"]] = relationship(  # noqa: F821
        "LineageRecord", back_populates="source_document", cascade="all, delete-orphan"
    )
