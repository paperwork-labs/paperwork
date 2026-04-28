"""Vercel quota snapshot table (Brain quota monitor).

Revision ID: 005
Revises: 004
Create Date: 2026-04-27
"""

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS vercel_quota_snapshot (
      id BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      project_id TEXT,
      project_name TEXT NOT NULL,
      window_days INTEGER NOT NULL,
      deploy_count INTEGER NOT NULL,
      build_minutes DOUBLE PRECISION NOT NULL,
      source_breakdown JSONB,
      meta JSONB
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS vercel_quota_snapshot_created_at_idx "
        "ON vercel_quota_snapshot(created_at DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS vercel_quota_snapshot_project_id_idx "
        "ON vercel_quota_snapshot(project_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vercel_quota_snapshot CASCADE;")
