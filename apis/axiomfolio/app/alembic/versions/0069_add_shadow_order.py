"""Add shadow_orders table for paper-autotrading recorder.

Part of the default-ON shadow trading scaffold (see D137). Populated by
``app.services.execution.shadow_order_recorder.ShadowOrderRecorder`` when
``settings.SHADOW_TRADING_MODE`` is True. No existing rows or code paths
depend on this table being present; downgrade drops it.

Revision ID: 0069
Revises: 0067
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0069"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=100), nullable=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column(
            "order_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'market'"),
        ),
        sa.Column("qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("limit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("tif", sa.String(length=10), nullable=True),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'intended'"),
        ),
        sa.Column("risk_gate_verdict", sa.JSON(), nullable=True),
        sa.Column("intended_fill_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("intended_fill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("simulated_pnl", sa.Numeric(18, 6), nullable=True),
        sa.Column("simulated_pnl_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_mark_price", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "source_order_id",
            sa.Integer(),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_shadow_orders_user_id", "shadow_orders", ["user_id"], unique=False)
    op.create_index("ix_shadow_orders_symbol", "shadow_orders", ["symbol"], unique=False)
    op.create_index("ix_shadow_orders_status", "shadow_orders", ["status"], unique=False)
    op.create_index(
        "ix_shadow_orders_source_order_id",
        "shadow_orders",
        ["source_order_id"],
        unique=False,
    )
    op.create_index(
        "ix_shadow_orders_user_status",
        "shadow_orders",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_shadow_orders_user_created",
        "shadow_orders",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shadow_orders_user_created", table_name="shadow_orders")
    op.drop_index("ix_shadow_orders_user_status", table_name="shadow_orders")
    op.drop_index("ix_shadow_orders_source_order_id", table_name="shadow_orders")
    op.drop_index("ix_shadow_orders_status", table_name="shadow_orders")
    op.drop_index("ix_shadow_orders_symbol", table_name="shadow_orders")
    op.drop_index("ix_shadow_orders_user_id", table_name="shadow_orders")
    op.drop_table("shadow_orders")
