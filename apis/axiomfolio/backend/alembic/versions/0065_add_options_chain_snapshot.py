"""Add options_chain_snapshot (gold options surface).

Revision ID: 0065
Revises: 0064
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "options_chain_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("strike", sa.Numeric(12, 4), nullable=False),
        sa.Column("option_type", sa.String(length=4), nullable=False),
        sa.Column("bid", sa.Numeric(12, 4), nullable=True),
        sa.Column("ask", sa.Numeric(12, 4), nullable=True),
        sa.Column("mid", sa.Numeric(12, 4), nullable=True),
        sa.Column("spread_abs", sa.Numeric(12, 4), nullable=True),
        sa.Column("spread_rel", sa.Numeric(6, 4), nullable=True),
        sa.Column("open_interest", sa.Integer(), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("implied_vol", sa.Numeric(6, 4), nullable=True),
        sa.Column("iv_pctile_1y", sa.Numeric(6, 4), nullable=True),
        sa.Column("iv_rank_1y", sa.Numeric(6, 4), nullable=True),
        sa.Column("liquidity_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("delta", sa.Numeric(6, 4), nullable=True),
        sa.Column("gamma", sa.Numeric(8, 6), nullable=True),
        sa.Column("theta", sa.Numeric(8, 4), nullable=True),
        sa.Column("vega", sa.Numeric(6, 4), nullable=True),
        sa.Column("snapshot_taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "expiry",
            "strike",
            "option_type",
            "snapshot_taken_at",
            name="uq_ocs_sym_exp_strike_type_ts",
        ),
    )
    op.create_index("ix_ocs_sym_ts", "options_chain_snapshot", ["symbol", "snapshot_taken_at"])
    op.create_index(
        op.f("ix_options_chain_snapshot_expiry"), "options_chain_snapshot", ["expiry"]
    )
    op.create_index(
        op.f("ix_options_chain_snapshot_symbol"), "options_chain_snapshot", ["symbol"]
    )
    op.create_index(
        op.f("ix_options_chain_snapshot_snapshot_taken_at"),
        "options_chain_snapshot",
        ["snapshot_taken_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_options_chain_snapshot_snapshot_taken_at",
        table_name="options_chain_snapshot",
        if_exists=True,
    )
    op.drop_index(
        "ix_options_chain_snapshot_symbol",
        table_name="options_chain_snapshot",
        if_exists=True,
    )
    op.drop_index(
        "ix_options_chain_snapshot_expiry",
        table_name="options_chain_snapshot",
        if_exists=True,
    )
    op.drop_index("ix_ocs_sym_ts", table_name="options_chain_snapshot", if_exists=True)
    op.drop_table("options_chain_snapshot")
