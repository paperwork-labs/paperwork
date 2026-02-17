"""Backfill monitor_coverage_health -> admin_coverage_refresh in job_run.

Revision ID: b1c2d3e4f5a6
Revises: a91f4d2c8b7e
Create Date: 2026-02-17
"""

from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a91f4d2c8b7e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE job_run SET task_name = 'admin_coverage_refresh' "
        "WHERE task_name = 'monitor_coverage_health'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE job_run SET task_name = 'monitor_coverage_health' "
        "WHERE task_name = 'admin_coverage_refresh'"
    )
