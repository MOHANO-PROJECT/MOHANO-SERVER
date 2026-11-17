"""persist user reports and temporary interaction restrictions

Revision ID: 20261027_0011
Revises: 20261026_0010
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20261027_0011"
down_revision = "20261026_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("restricted_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_restricted_until", "users", ["restricted_until"])

    op.create_table(
        "user_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reporter_id", sa.String(length=36), nullable=False),
        sa.Column("reported_user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=48), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reported_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_reports_reporter_id", "user_reports", ["reporter_id"])
    op.create_index("ix_user_reports_reported_user_id", "user_reports", ["reported_user_id"])
    op.create_index("ix_user_reports_created_at", "user_reports", ["created_at"])
    op.create_index(
        "ix_user_reports_reported_created_at",
        "user_reports",
        ["reported_user_id", "created_at"],
    )
    op.create_index(
        "ix_user_reports_reporter_target_created_at",
        "user_reports",
        ["reporter_id", "reported_user_id", "created_at"],
    )

    op.create_table(
        "safety_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("report_window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reporter_count", sa.Integer(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restricted_until", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_safety_actions_user_id", "safety_actions", ["user_id"])
    op.create_index("ix_safety_actions_triggered_at", "safety_actions", ["triggered_at"])
    op.create_index("ix_safety_actions_restricted_until", "safety_actions", ["restricted_until"])


def downgrade() -> None:
    op.drop_index("ix_safety_actions_restricted_until", table_name="safety_actions")
    op.drop_index("ix_safety_actions_triggered_at", table_name="safety_actions")
    op.drop_index("ix_safety_actions_user_id", table_name="safety_actions")
    op.drop_table("safety_actions")
    op.drop_index("ix_user_reports_reporter_target_created_at", table_name="user_reports")
    op.drop_index("ix_user_reports_reported_created_at", table_name="user_reports")
    op.drop_index("ix_user_reports_created_at", table_name="user_reports")
    op.drop_index("ix_user_reports_reported_user_id", table_name="user_reports")
    op.drop_index("ix_user_reports_reporter_id", table_name="user_reports")
    op.drop_table("user_reports")
    op.drop_index("ix_users_restricted_until", table_name="users")
    op.drop_column("users", "restricted_until")
