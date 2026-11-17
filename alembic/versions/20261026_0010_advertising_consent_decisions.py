"""persist advertising personalization preference decisions

Revision ID: 20261026_0010
Revises: 20261026_0009
Create Date: 2026-10-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20261026_0010"
down_revision = "20261026_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advertising_consent_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("consent_version", sa.String(length=32), nullable=False),
        sa.Column("personalized_ads_allowed", sa.Boolean(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_advertising_consent_decisions_user_id",
        "advertising_consent_decisions",
        ["user_id"],
    )
    op.create_index(
        "ix_advertising_consent_decisions_decided_at",
        "advertising_consent_decisions",
        ["decided_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_advertising_consent_decisions_decided_at",
        table_name="advertising_consent_decisions",
    )
    op.drop_index(
        "ix_advertising_consent_decisions_user_id",
        table_name="advertising_consent_decisions",
    )
    op.drop_table("advertising_consent_decisions")
