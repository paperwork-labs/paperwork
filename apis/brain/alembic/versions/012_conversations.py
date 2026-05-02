"""Conversations mirror + message transcripts (WS-82 W10a).

Revision ID: 012
Revises: 011
"""

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS conversations (
      id UUID PRIMARY KEY,
      title TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """
    )
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS conversation_messages (
      id UUID PRIMARY KEY,
      conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
      role VARCHAR(20) NOT NULL CHECK (
        role IN ('user','assistant','persona')
      ),
      content TEXT NOT NULL,
      persona_slug VARCHAR(100),
      model_used VARCHAR(100),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    )
    op.execute(
        """
    CREATE INDEX IF NOT EXISTS conversation_messages_conversation_id_idx
    ON conversation_messages (conversation_id);
    """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversation_messages;")
    op.execute("DROP TABLE IF EXISTS conversations;")
