"""Create orders table for trade execution.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("symbol", sa.String(20), nullable=False),
            sa.Column("side", sa.String(10), nullable=False),
            sa.Column("order_type", sa.String(20), nullable=False),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="preview",
            ),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("limit_price", sa.Float(), nullable=True),
            sa.Column("stop_price", sa.Float(), nullable=True),
            sa.Column("filled_quantity", sa.Float(), nullable=True, server_default="0"),
            sa.Column("filled_avg_price", sa.Float(), nullable=True),
            sa.Column("account_id", sa.String(100), nullable=True),
            sa.Column("broker_order_id", sa.String(100), nullable=True),
            sa.Column("estimated_commission", sa.Float(), nullable=True),
            sa.Column("estimated_margin_impact", sa.Float(), nullable=True),
            sa.Column("estimated_equity_with_loan", sa.Float(), nullable=True),
            sa.Column("preview_data", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.String(500), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("created_by", sa.String(200), nullable=True),
        )
        op.create_index("ix_orders_symbol", "orders", ["symbol"])
        op.create_index("ix_orders_status", "orders", ["status"])
        op.create_index("ix_orders_broker_order_id", "orders", ["broker_order_id"])
        op.create_index("idx_orders_symbol_status", "orders", ["symbol", "status"])
        op.create_index(
            "idx_orders_status_created_at", "orders", ["status", "created_at"]
        )


def downgrade() -> None:
    op.drop_index("idx_orders_status_created_at", table_name="orders")
    op.drop_index("idx_orders_symbol_status", table_name="orders")
    op.drop_index("ix_orders_broker_order_id", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_symbol", table_name="orders")
    op.drop_table("orders")
