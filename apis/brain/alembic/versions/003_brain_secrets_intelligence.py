"""Brain secrets registry and operational episodes (secrets intelligence).

Revision ID: 003
Revises: 002
Create Date: 2026-04-27
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS brain_secrets_registry (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      name TEXT UNIQUE NOT NULL,
      purpose TEXT,
      service TEXT NOT NULL,
      format_hint TEXT,
      expected_prefix TEXT,
      criticality TEXT NOT NULL DEFAULT 'normal',
      depends_in_apps TEXT[] DEFAULT '{}',
      depends_in_services TEXT[] DEFAULT '{}',
      rotation_cadence_days INTEGER,
      last_rotated_at TIMESTAMPTZ,
      last_verified_synced_at TIMESTAMPTZ,
      drift_detected_at TIMESTAMPTZ,
      drift_summary TEXT,
      lessons_learned JSONB DEFAULT '[]'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    )
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS brain_secrets_episodes (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      secret_name TEXT NOT NULL,
      event_type TEXT NOT NULL,
      event_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      source TEXT NOT NULL,
      summary TEXT NOT NULL,
      details JSONB DEFAULT '{}'::jsonb,
      triggered_task_id UUID,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS brain_secrets_episodes_name_idx "
        "ON brain_secrets_episodes(secret_name, event_at DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS brain_secrets_registry_name_idx ON brain_secrets_registry(name);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS brain_secrets_episodes CASCADE;")
    op.execute("DROP TABLE IF EXISTS brain_secrets_registry CASCADE;")
