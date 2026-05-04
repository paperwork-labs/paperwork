"""Add content_tsv TSVECTOR + message_metadata JSONB to conversation_messages.

Enables Postgres full-text search over message bodies (T1.0d Wave 0).
``content_tsv`` is kept in sync by a BEFORE INSERT OR UPDATE trigger.
``message_metadata`` stores ThreadMessage fields not present in the 012 schema
(author, attachments, reactions, parent_message_id).

Revision ID: 015
Revises: 014
"""

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ columns
    op.execute("ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS content_tsv TSVECTOR")
    op.execute(
        "ALTER TABLE conversation_messages "
        "ADD COLUMN IF NOT EXISTS message_metadata JSONB NOT NULL DEFAULT '{}'::jsonb"
    )

    # ------------------------------------------------------------------- index
    op.execute(
        "CREATE INDEX IF NOT EXISTS conversation_messages_content_tsv_gin "
        "ON conversation_messages USING GIN (content_tsv)"
    )

    # --------------------------------------------------------------- function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION conversation_messages_content_tsv_trigger()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.content_tsv := to_tsvector('english', NEW.content);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # --------------------------------------------------------------- trigger
    op.execute(
        "DROP TRIGGER IF EXISTS conversation_messages_content_tsv_update ON conversation_messages"
    )
    op.execute(
        """
        CREATE TRIGGER conversation_messages_content_tsv_update
            BEFORE INSERT OR UPDATE OF content ON conversation_messages
            FOR EACH ROW EXECUTE FUNCTION conversation_messages_content_tsv_trigger()
        """
    )

    # ------------------------------------------------------- backfill existing
    op.execute(
        "UPDATE conversation_messages "
        "SET content_tsv = to_tsvector('english', content) "
        "WHERE content_tsv IS NULL"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS conversation_messages_content_tsv_update ON conversation_messages"
    )
    op.execute("DROP FUNCTION IF EXISTS conversation_messages_content_tsv_trigger()")
    op.execute("DROP INDEX IF EXISTS conversation_messages_content_tsv_gin")
    op.execute("ALTER TABLE conversation_messages DROP COLUMN IF EXISTS content_tsv")
    op.execute("ALTER TABLE conversation_messages DROP COLUMN IF EXISTS message_metadata")
