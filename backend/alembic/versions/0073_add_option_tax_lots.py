"""Add option_tax_lots table for realized options (FIFO closed lots).

Revision ID: 0073
Revises: 0072
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "option_tax_lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("broker_account_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("underlying", sa.String(length=32), nullable=False),
        sa.Column("option_type", sa.String(length=8), nullable=False),
        sa.Column("strike", sa.Numeric(12, 4), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("multiplier", sa.Integer(), nullable=False),
        sa.Column("quantity_opened", sa.Numeric(15, 4), nullable=False),
        sa.Column("cost_basis_per_contract", sa.Numeric(12, 4), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity_closed", sa.Numeric(15, 4), nullable=False),
        sa.Column("proceeds_per_contract", sa.Numeric(12, 4), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(14, 4), nullable=True),
        sa.Column("holding_class", sa.String(length=16), nullable=True),
        sa.Column("opening_trade_id", sa.Integer(), nullable=False),
        sa.Column("closing_trade_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["broker_account_id"], ["broker_accounts.id"]),
        sa.ForeignKeyConstraint(["closing_trade_id"], ["trades.id"]),
        sa.ForeignKeyConstraint(["opening_trade_id"], ["trades.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opening_trade_id",
            "closing_trade_id",
            name="uq_option_tax_lots_opening_trade_id_closing_trade_id",
        ),
    )
    op.create_index(
        "ix_option_tax_lots_user_symbol", "option_tax_lots", ["user_id", "symbol"]
    )
    op.create_index(
        "ix_option_tax_lots_user_closed", "option_tax_lots", ["user_id", "closed_at"]
    )


def downgrade() -> None:
    op.drop_table("option_tax_lots")
