"""Add cron_schedule table for unified schedule management.

Revision ID: c5d6e7f8a9b0
Revises: b1c2d3e4f5a6
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa

revision = "c5d6e7f8a9b0"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("cron_schedule"):
        op.create_table(
            "cron_schedule",
            sa.Column("id", sa.String(100), primary_key=True),
            sa.Column("display_name", sa.String(200), nullable=False),
            sa.Column("group", sa.String(50), nullable=False),
            sa.Column("task", sa.String(300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("cron", sa.String(100), nullable=False),
            sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
            sa.Column("args_json", sa.JSON(), nullable=True),
            sa.Column("kwargs_json", sa.JSON(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("timeout_s", sa.Integer(), nullable=True, server_default="3600"),
            sa.Column("singleflight", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("render_service_id", sa.String(100), nullable=True),
            sa.Column("render_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("render_sync_error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(200), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("cron_schedule")
