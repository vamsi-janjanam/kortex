import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BusinessRuleType(str, Enum):
    """The kind of business logic a rule captures."""

    DECISION = "decision"  # a choice that was made (and ideally why)
    POLICY = "policy"  # a standing governance rule
    PROCESS = "process"  # how something is done / a workflow
    CONSTRAINT = "constraint"  # a limit or requirement
    METRIC = "metric"  # a target / threshold the business cares about


class BusinessRuleStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    PROPOSED = "proposed"


class BusinessRule(Base):
    """A first-class piece of business logic extracted from source content.

    Unlike :class:`Entity` (a named *thing*), a ``BusinessRule`` captures a
    *decision / policy / process* together with its **rationale** — the "why"
    that separates business knowledge from raw knowledge.
    """

    __tablename__ = "business_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Short human title, e.g. "Auth uses OAuth 2.0 JWT".
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rule_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=BusinessRuleType.DECISION
    )
    # What the rule/decision IS.
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    # WHY it holds — the business reasoning. Nullable: not every source states it.
    rationale: Mapped[str | None] = mapped_column(Text)

    # Provenance: where this rule was extracted from (best-effort, nullable).
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id"), nullable=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=BusinessRuleStatus.ACTIVE
    )
    # Decision provenance: this rule replaces an earlier one.
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_rules.id"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    supersedes: Mapped["BusinessRule | None"] = relationship(
        "BusinessRule", remote_side=[id]
    )
