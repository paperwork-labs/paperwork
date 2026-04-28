"""GitHub Actions quota snapshot table (Brain quota monitor).

Revision ID: 005
Revises: 004
Create Date: 2026-04-28
"""

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS github_actions_quota_snapshot (
      id BIGSERIAL PRIMARY KEY,
      recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      repo TEXT NOT NULL,
      is_public BOOLEAN NOT NULL,
      minutes_used DOUBLE PRECISION,
      minutes_limit DOUBLE PRECISION,
      included_minutes INTEGER,
      paid_minutes_used DOUBLE PRECISION,
      total_paid_minutes_used_breakdown JSONB,
      minutes_used_breakdown JSONB,
      cache_size_bytes BIGINT,
      cache_count INTEGER,
      extra_json JSONB
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS github_actions_quota_snapshot_recorded_at_idx "
        "ON github_actions_quota_snapshot(recorded_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS github_actions_quota_snapshot CASCADE;")
