"""Add TTM Squeeze indicator columns to MarketSnapshot and MarketSnapshotHistory.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-26

Note: This migration is idempotent — columns may already exist if the baseline
migration (0001) was run against models that include these columns.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists in a table."""
    conn = op.get_bind()
    insp = inspect(conn)
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    """Add a column only if it doesn't already exist."""
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade():
    ttm_columns = [
        sa.Column("keltner_upper", sa.Float(), nullable=True),
        sa.Column("keltner_lower", sa.Float(), nullable=True),
        sa.Column("ttm_squeeze_on", sa.Boolean(), nullable=True),
        sa.Column("ttm_momentum", sa.Float(), nullable=True),
    ]

    for table in ["market_snapshot", "market_snapshot_history"]:
        for col in ttm_columns:
            _add_column_if_missing(table, sa.Column(col.name, col.type, nullable=True))


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    """Drop a column only if it exists."""
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def downgrade():
    column_names = ["ttm_momentum", "ttm_squeeze_on", "keltner_lower", "keltner_upper"]

    for table in ["market_snapshot_history", "market_snapshot"]:
        for col_name in column_names:
            _drop_column_if_exists(table, col_name)
