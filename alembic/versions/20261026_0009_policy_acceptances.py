"""persist required onboarding policy acceptances

Revision ID: 20261026_0009
Revises: 20261025_0008
Create Date: 2026-10-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20261026_0009"
down_revision = "20261025_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_acceptances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("policy_type", sa.String(length=48), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "policy_type",
            "policy_version",
            name="uq_policy_acceptance_user_type_version",
        ),
    )
    op.create_index(
        "ix_policy_acceptances_user_id", "policy_acceptances", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_policy_acceptances_user_id", table_name="policy_acceptances")
    op.drop_table("policy_acceptances")
