"""Add agent_memories table for agent long-term memory.

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("memory_type", sa.String(50), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("relevance_score", sa.Float(), default=0.0),
        sa.Column("access_count", sa.Integer(), default=0),
        sa.Column("last_accessed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_memory_user_type", "agent_memories", ["user_id", "memory_type"])
    op.create_index("idx_memory_created", "agent_memories", ["created_at"])
    op.create_index("idx_memory_hash", "agent_memories", ["content_hash"])


def downgrade() -> None:
    op.drop_index("idx_memory_hash", table_name="agent_memories")
    op.drop_index("idx_memory_created", table_name="agent_memories")
    op.drop_index("idx_memory_user_type", table_name="agent_memories")
    op.drop_table("agent_memories")
