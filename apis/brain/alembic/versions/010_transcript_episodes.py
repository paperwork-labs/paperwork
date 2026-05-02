"""Cursor agent transcript episodes (JSONL ingest).

Revision ID: 010
Revises: 009
"""

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS transcript_episodes (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      transcript_id TEXT NOT NULL,
      turn_index INTEGER NOT NULL,
      user_message TEXT NOT NULL,
      assistant_message TEXT NOT NULL,
      summary TEXT,
      entities JSONB NOT NULL DEFAULT '[]'::jsonb,
      persona_slugs JSONB NOT NULL DEFAULT '[]'::jsonb,
      ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_transcript_episodes_transcript_id "
        "ON transcript_episodes(transcript_id);"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_transcript_episodes_turn "
        "ON transcript_episodes(transcript_id, turn_index);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transcript_episodes CASCADE;")
