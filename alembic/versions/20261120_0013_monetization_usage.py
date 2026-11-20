"""add monetization entitlement and daily advertising gate records

Revision ID: 20261120_0013
Revises: 20261028_0012
Create Date: 2026-11-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20261120_0013"
down_revision = "20261028_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_entitlements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("store", sa.String(length=24), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_subscription_entitlements_ends_at", "subscription_entitlements", ["ends_at"])

    op.create_table(
        "discovery_daily_usages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("batches_served", sa.Integer(), nullable=False),
        sa.Column("unlocked_batches", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "local_date", name="uq_discovery_daily_usage"),
    )
    op.create_index("ix_discovery_daily_usages_user_id", "discovery_daily_usages", ["user_id"])
    op.create_index("ix_discovery_daily_usages_local_date", "discovery_daily_usages", ["local_date"])

    op.create_table(
        "chat_daily_usages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("initial_gate_completed", sa.Boolean(), nullable=False),
        sa.Column("outgoing_messages_since_gate", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "conversation_id", "local_date", name="uq_chat_daily_usage"),
    )
    op.create_index("ix_chat_daily_usages_user_id", "chat_daily_usages", ["user_id"])
    op.create_index("ix_chat_daily_usages_conversation_id", "chat_daily_usages", ["conversation_id"])
    op.create_index("ix_chat_daily_usages_local_date", "chat_daily_usages", ["local_date"])

    op.create_table(
        "ad_gate_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("gate_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "gate_type", "subject_id", "local_date", "sequence", name="uq_ad_gate_event"),
    )
    op.create_index("ix_ad_gate_events_user_id", "ad_gate_events", ["user_id"])
    op.create_index("ix_ad_gate_events_local_date", "ad_gate_events", ["local_date"])


def downgrade() -> None:
    op.drop_index("ix_ad_gate_events_local_date", table_name="ad_gate_events")
    op.drop_index("ix_ad_gate_events_user_id", table_name="ad_gate_events")
    op.drop_table("ad_gate_events")
    op.drop_index("ix_chat_daily_usages_local_date", table_name="chat_daily_usages")
    op.drop_index("ix_chat_daily_usages_conversation_id", table_name="chat_daily_usages")
    op.drop_index("ix_chat_daily_usages_user_id", table_name="chat_daily_usages")
    op.drop_table("chat_daily_usages")
    op.drop_index("ix_discovery_daily_usages_local_date", table_name="discovery_daily_usages")
    op.drop_index("ix_discovery_daily_usages_user_id", table_name="discovery_daily_usages")
    op.drop_table("discovery_daily_usages")
    op.drop_index("ix_subscription_entitlements_ends_at", table_name="subscription_entitlements")
    op.drop_table("subscription_entitlements")
