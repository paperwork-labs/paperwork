"""Add multi-timeframe stage columns.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade():
    for table in ["market_snapshot", "market_snapshot_history"]:
        if not _column_exists(table, "stage_4h"):
            op.add_column(table, sa.Column("stage_4h", sa.String(10), nullable=True))
        if not _column_exists(table, "stage_confirmed"):
            op.add_column(table, sa.Column("stage_confirmed", sa.Boolean(), nullable=True))


def downgrade():
    for table in ["market_snapshot", "market_snapshot_history"]:
        if _column_exists(table, "stage_4h"):
            op.drop_column(table, "stage_4h")
        if _column_exists(table, "stage_confirmed"):
            op.drop_column(table, "stage_confirmed")
