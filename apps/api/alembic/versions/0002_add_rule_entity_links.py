"""add business_rule_entity_links table

Revision ID: 0002_rule_entity_links
Revises: 0001_business_rules
Create Date: 2026-06-18 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_rule_entity_links"
down_revision = "0001_business_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_rule_entity_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "business_rule_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["business_rule_id"], ["business_rules.id"]),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_rule_id", "entity_id", name="uq_rule_entity_link"
        ),
    )


def downgrade() -> None:
    op.drop_table("business_rule_entity_links")
