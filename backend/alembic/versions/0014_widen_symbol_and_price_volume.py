"""Widen symbol columns and price_data.volume for large tickers / volume.

- market_snapshot.symbol, market_snapshot_history.symbol, index_constituents.symbol: VARCHAR(10) -> VARCHAR(20)
- price_data.volume: INTEGER -> BIGINT

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "price_data",
        "volume",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "market_snapshot",
        "symbol",
        existing_type=sa.String(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "market_snapshot_history",
        "symbol",
        existing_type=sa.String(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "index_constituents",
        "symbol",
        existing_type=sa.String(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "index_constituents",
        "symbol",
        existing_type=sa.String(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "market_snapshot_history",
        "symbol",
        existing_type=sa.String(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "market_snapshot",
        "symbol",
        existing_type=sa.String(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "price_data",
        "volume",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
