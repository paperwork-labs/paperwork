"""Workstream board dispatch log + progress snapshots (Track Z).

Revision ID: 004
Revises: 003
Create Date: 2026-04-27
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS workstream_dispatch_log (
      id BIGSERIAL PRIMARY KEY,
      workstream_id TEXT NOT NULL,
      dispatched_at TIMESTAMPTZ NOT NULL,
      github_workflow TEXT NOT NULL,
      inputs_json JSONB,
      github_run_id TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS workstream_dispatch_log_ws_idx "
        "ON workstream_dispatch_log(workstream_id, dispatched_at DESC);"
    )
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS workstream_progress_snapshot (
      id BIGSERIAL PRIMARY KEY,
      workstream_id TEXT NOT NULL,
      recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      percent_done INTEGER NOT NULL,
      computed_status TEXT NOT NULL,
      merged_pr_count INTEGER NOT NULL,
      open_pr_count INTEGER NOT NULL,
      denominator INTEGER NOT NULL,
      extra_json JSONB
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS workstream_progress_snapshot_ws_idx "
        "ON workstream_progress_snapshot(workstream_id, recorded_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workstream_progress_snapshot CASCADE;")
    op.execute("DROP TABLE IF EXISTS workstream_dispatch_log CASCADE;")
