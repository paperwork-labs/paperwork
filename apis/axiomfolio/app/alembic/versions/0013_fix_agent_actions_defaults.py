"""Fix agent_actions table defaults.

The agent_actions table was missing server_default values for created_at
and status columns. When SQLAlchemy's Python-side defaults don't fire
(e.g., during certain flush patterns or ORM quirks), the DB INSERT fails
with NOT NULL constraint violations.

This migration adds server_default values so the database can handle
inserts even without explicit Python values:
- created_at: now()
- status: 'pending'

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add server_default to created_at
    op.alter_column(
        "agent_actions",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
        existing_nullable=False,
    )

    # Add server_default to status
    op.alter_column(
        "agent_actions",
        "status",
        server_default="pending",
        existing_type=sa.String(20),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Remove server_default from status
    op.alter_column(
        "agent_actions",
        "status",
        server_default=None,
        existing_type=sa.String(20),
        existing_nullable=False,
    )

    # Remove server_default from created_at
    op.alter_column(
        "agent_actions",
        "created_at",
        server_default=None,
        existing_type=sa.DateTime(),
        existing_nullable=False,
    )
