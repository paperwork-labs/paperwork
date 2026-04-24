"""external_signals table for auxiliary Finviz/Zacks-style rows.

Revision ID: 0072
Revises: 0071
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(20, 8), nullable=True),
        sa.Column("raw_payload", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "symbol",
            "source",
            "signal_date",
            "signal_type",
            name="uq_external_signals_sym_src_day_type",
        ),
    )
    op.create_index(
        "ix_external_signals_symbol", "external_signals", ["symbol"], unique=False
    )
    op.create_index(
        "ix_external_signals_signal_date", "external_signals", ["signal_date"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_external_signals_signal_date", table_name="external_signals")
    op.drop_index("ix_external_signals_symbol", table_name="external_signals")
    op.drop_table("external_signals")
