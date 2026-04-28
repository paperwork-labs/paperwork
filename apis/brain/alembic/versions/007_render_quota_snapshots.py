"""Render quota snapshot table (Brain quota monitor).

Revision ID: 007
Revises: 006
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS render_quota_snapshots (
      id BIGSERIAL PRIMARY KEY,
      recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      month TEXT NOT NULL,
      pipeline_minutes_used DOUBLE PRECISION NOT NULL,
      pipeline_minutes_included DOUBLE PRECISION NOT NULL,
      bandwidth_gb_used DOUBLE PRECISION,
      bandwidth_gb_included DOUBLE PRECISION,
      unbilled_charges_usd DOUBLE PRECISION,
      services_count INTEGER,
      datastores_storage_gb DOUBLE PRECISION,
      workspace_plan TEXT,
      derived_from TEXT NOT NULL,
      extra_json JSONB
    );
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS render_quota_snapshots_month_recorded_idx "
        "ON render_quota_snapshots (month DESC, recorded_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS render_quota_snapshots CASCADE;")
