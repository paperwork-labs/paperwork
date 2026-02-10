"""Add stage duration fields to snapshot tables.

Revision ID: 8c1f2e9b7a12
Revises: 4f2c9d0f5b24
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


# revision identifiers, used by Alembic.
revision = "8c1f2e9b7a12"
down_revision = "4f2c9d0f5b24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("market_snapshot") as batch:
        if not _has_column("market_snapshot", "current_stage_days"):
            batch.add_column(sa.Column("current_stage_days", sa.Integer(), nullable=True))
        if not _has_column("market_snapshot", "previous_stage_label"):
            batch.add_column(sa.Column("previous_stage_label", sa.String(length=10), nullable=True))
        if not _has_column("market_snapshot", "previous_stage_days"):
            batch.add_column(sa.Column("previous_stage_days", sa.Integer(), nullable=True))

    with op.batch_alter_table("market_snapshot_history") as batch:
        if not _has_column("market_snapshot_history", "current_stage_days"):
            batch.add_column(sa.Column("current_stage_days", sa.Integer(), nullable=True))
        if not _has_column("market_snapshot_history", "previous_stage_label"):
            batch.add_column(sa.Column("previous_stage_label", sa.String(length=10), nullable=True))
        if not _has_column("market_snapshot_history", "previous_stage_days"):
            batch.add_column(sa.Column("previous_stage_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("market_snapshot_history") as batch:
        for col in ("previous_stage_days", "previous_stage_label", "current_stage_days"):
            if _has_column("market_snapshot_history", col):
                batch.drop_column(col)

    with op.batch_alter_table("market_snapshot") as batch:
        for col in ("previous_stage_days", "previous_stage_label", "current_stage_days"):
            if _has_column("market_snapshot", col):
                batch.drop_column(col)
