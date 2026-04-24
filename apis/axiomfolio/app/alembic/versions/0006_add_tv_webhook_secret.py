"""Add tv_webhook_secret column to users table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-27

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tv_webhook_secret", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_users_tv_webhook_secret",
        "users",
        ["tv_webhook_secret"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_tv_webhook_secret", table_name="users")
    op.drop_column("users", "tv_webhook_secret")
