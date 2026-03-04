"""Add eps_ttm and revenue_ttm to snapshot tables

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-03-02

"""
import sqlalchemy as sa
from alembic import op


revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    for table in ("market_snapshot", "market_snapshot_history"):
        with op.batch_alter_table(table) as batch:
            if not _has_column(table, "eps_ttm"):
                batch.add_column(sa.Column("eps_ttm", sa.Float(), nullable=True))
            if not _has_column(table, "revenue_ttm"):
                batch.add_column(sa.Column("revenue_ttm", sa.Float(), nullable=True))


def downgrade() -> None:
    for table in ("market_snapshot", "market_snapshot_history"):
        with op.batch_alter_table(table) as batch:
            if _has_column(table, "eps_ttm"):
                batch.drop_column("eps_ttm")
            if _has_column(table, "revenue_ttm"):
                batch.drop_column("revenue_ttm")
