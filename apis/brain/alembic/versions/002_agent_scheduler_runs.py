"""agent_scheduler_runs for n8n shadow + scheduler observability (T1.1).

Revision ID: 002
Revises: 001
Create Date: 2026-04-25
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_scheduler_runs (
        id SERIAL PRIMARY KEY,
        job_id TEXT NOT NULL,
        started_at TIMESTAMPTZ NOT NULL,
        finished_at TIMESTAMPTZ NOT NULL,
        status TEXT NOT NULL,
        error_text TEXT,
        metadata_json JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_agent_scheduler_runs_job_finished
    ON agent_scheduler_runs (job_id, finished_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_scheduler_runs CASCADE")
