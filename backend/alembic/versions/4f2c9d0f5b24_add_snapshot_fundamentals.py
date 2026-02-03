"""Add fundamentals and extra SMA fields to snapshot tables.

Revision ID: 4f2c9d0f5b24
Revises: 4f2c9d0f5b23
Create Date: 2026-01-15
"""

from alembic import op
import sqlalchemy as sa


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


# revision identifiers, used by Alembic.
revision = "4f2c9d0f5b24"
down_revision = "4f2c9d0f5b23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("market_snapshot") as batch:
        if not _has_column("market_snapshot", "sma_10"):
            batch.add_column(sa.Column("sma_10", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "last_earnings"):
            batch.add_column(sa.Column("last_earnings", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("market_snapshot", "pe_ttm"):
            batch.add_column(sa.Column("pe_ttm", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "peg_ttm"):
            batch.add_column(sa.Column("peg_ttm", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "roe"):
            batch.add_column(sa.Column("roe", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "eps_growth_yoy"):
            batch.add_column(sa.Column("eps_growth_yoy", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "eps_growth_qoq"):
            batch.add_column(sa.Column("eps_growth_qoq", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "revenue_growth_yoy"):
            batch.add_column(sa.Column("revenue_growth_yoy", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "revenue_growth_qoq"):
            batch.add_column(sa.Column("revenue_growth_qoq", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "dividend_yield"):
            batch.add_column(sa.Column("dividend_yield", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "beta"):
            batch.add_column(sa.Column("beta", sa.Float(), nullable=True))
        if not _has_column("market_snapshot", "analyst_rating"):
            batch.add_column(sa.Column("analyst_rating", sa.String(length=50), nullable=True))

    with op.batch_alter_table("market_snapshot_history") as batch:
        if not _has_column("market_snapshot_history", "sma_10"):
            batch.add_column(sa.Column("sma_10", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "last_earnings"):
            batch.add_column(sa.Column("last_earnings", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("market_snapshot_history", "next_earnings"):
            batch.add_column(sa.Column("next_earnings", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("market_snapshot_history", "pe_ttm"):
            batch.add_column(sa.Column("pe_ttm", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "peg_ttm"):
            batch.add_column(sa.Column("peg_ttm", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "roe"):
            batch.add_column(sa.Column("roe", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "eps_growth_yoy"):
            batch.add_column(sa.Column("eps_growth_yoy", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "eps_growth_qoq"):
            batch.add_column(sa.Column("eps_growth_qoq", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "revenue_growth_yoy"):
            batch.add_column(sa.Column("revenue_growth_yoy", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "revenue_growth_qoq"):
            batch.add_column(sa.Column("revenue_growth_qoq", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "dividend_yield"):
            batch.add_column(sa.Column("dividend_yield", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "beta"):
            batch.add_column(sa.Column("beta", sa.Float(), nullable=True))
        if not _has_column("market_snapshot_history", "analyst_rating"):
            batch.add_column(sa.Column("analyst_rating", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("market_snapshot_history") as batch:
        for col in (
            "analyst_rating",
            "beta",
            "dividend_yield",
            "revenue_growth_qoq",
            "revenue_growth_yoy",
            "eps_growth_qoq",
            "eps_growth_yoy",
            "roe",
            "peg_ttm",
            "pe_ttm",
            "next_earnings",
            "last_earnings",
            "sma_10",
        ):
            if _has_column("market_snapshot_history", col):
                batch.drop_column(col)

    with op.batch_alter_table("market_snapshot") as batch:
        for col in (
            "analyst_rating",
            "beta",
            "dividend_yield",
            "revenue_growth_qoq",
            "revenue_growth_yoy",
            "eps_growth_qoq",
            "eps_growth_yoy",
            "roe",
            "peg_ttm",
            "pe_ttm",
            "last_earnings",
            "sma_10",
        ):
            if _has_column("market_snapshot", col):
                batch.drop_column(col)

