"""Add users.clerk_user_id for Clerk session JWT (Track B5 / WS-14).

Revision ID: 0077
Revises: 0076
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("clerk_user_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_column("users", "clerk_user_id")
