"""add_result_meta_to_job_run

Revision ID: 2a3b4c5d6e7f
Revises: 1e0612af8a13
Create Date: 2026-03-24 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "2a3b4c5d6e7f"
down_revision = "1e0612af8a13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not any(c["name"] == "result_meta" for c in insp.get_columns("job_run")):
        op.add_column("job_run", sa.Column("result_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_run", "result_meta")
