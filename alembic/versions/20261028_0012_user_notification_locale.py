"""persist the selected locale used for push notification copy

Revision ID: 20261028_0012
Revises: 20261027_0011
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20261028_0012"
down_revision = "20261027_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notification_locale",
            sa.String(length=8),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notification_locale")
