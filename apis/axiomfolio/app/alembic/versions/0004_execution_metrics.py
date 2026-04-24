"""Add execution_metrics table for fill quality and slippage analytics.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    return insp.has_table(table_name)


def upgrade() -> None:
    if _table_exists("execution_metrics"):
        return  # Already created by baseline

    op.create_table(
        "execution_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("broker", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("expected_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("fill_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("slippage_pct", sa.Float(), nullable=True),
        sa.Column("slippage_dollars", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_to_fill_ms", sa.Integer(), nullable=True),
        sa.Column("fill_rate", sa.Float(), nullable=True),
        sa.Column("partial_fills", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_execution_metrics_order_id"), "execution_metrics", ["order_id"], unique=False
    )
    op.create_index(
        op.f("ix_execution_metrics_user_id"), "execution_metrics", ["user_id"], unique=False
    )


def downgrade() -> None:
    if not _table_exists("execution_metrics"):
        return

    op.drop_index(op.f("ix_execution_metrics_user_id"), table_name="execution_metrics")
    op.drop_index(op.f("ix_execution_metrics_order_id"), table_name="execution_metrics")
    op.drop_table("execution_metrics")
