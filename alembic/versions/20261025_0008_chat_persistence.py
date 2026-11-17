"""persist chat message type and system events

Revision ID: 20261025_0008
Revises: 20261025_0007
Create Date: 2026-10-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20261025_0008"
down_revision = "20261025_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "message_type",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'message'"),
        ),
    )
    op.alter_column(
        "messages",
        "sender_id",
        existing_type=sa.String(length=36),
        existing_nullable=False,
        nullable=True,
    )
    op.create_index(
        "ix_conversation_members_user_id",
        "conversation_members",
        ["user_id"],
    )
    op.alter_column("messages", "message_type", server_default=None)


def downgrade() -> None:
    # System events have no user sender and cannot be represented in the old schema.
    op.execute("DELETE FROM messages WHERE sender_id IS NULL")
    op.drop_index("ix_conversation_members_user_id", table_name="conversation_members")
    op.alter_column(
        "messages",
        "sender_id",
        existing_type=sa.String(length=36),
        existing_nullable=True,
        nullable=False,
    )
    op.drop_column("messages", "message_type")
