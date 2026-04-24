"""Add previous refresh token family columns for concurrent-tab grace window.

When two browser tabs refresh simultaneously with the same pre-rotation refresh
cookie, the second request would previously fail family validation and revoke
the session. Storing the immediately prior family for a short TTL lets the
backend treat that as a benign race (D/auth refresh cascade).

Revision ID: 0037
Revises: 0036
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("previous_refresh_token_family", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("previous_refresh_token_rotated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "previous_refresh_token_rotated_at")
    op.drop_column("users", "previous_refresh_token_family")
