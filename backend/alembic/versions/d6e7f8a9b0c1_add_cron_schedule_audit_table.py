"""Add cron_schedule_audit table for change history.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("cron_schedule_audit"):
        op.create_table(
            "cron_schedule_audit",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("schedule_id", sa.String(100), nullable=False),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("actor", sa.String(200), nullable=False),
            sa.Column("changes", sa.JSON(), nullable=True),
            sa.Column(
                "timestamp",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index("idx_audit_schedule_time", "cron_schedule_audit", ["schedule_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("idx_audit_schedule_time", table_name="cron_schedule_audit")
    op.drop_table("cron_schedule_audit")
