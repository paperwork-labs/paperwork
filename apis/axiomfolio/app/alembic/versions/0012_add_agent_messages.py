"""Add agent_messages table for persistent conversation storage.

Conversation messages were previously stored in Redis with a 7-day TTL,
causing session history to show as empty after expiration. This migration
persists conversations to PostgreSQL for indefinite retention.

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(50), nullable=False, index=True),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("tool_call_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index(
        "idx_agent_messages_session_order",
        "agent_messages",
        ["session_id", "message_index"],
    )


def downgrade() -> None:
    op.drop_index("idx_agent_messages_session_order", table_name="agent_messages")
    op.drop_table("agent_messages")
