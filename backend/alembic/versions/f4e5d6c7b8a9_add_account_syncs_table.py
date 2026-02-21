"""Ensure account_syncs table exists for sync history.

Revision ID: f4e5d6c7b8a9
Revises: f3b2c9d4e1a0
Create Date: 2026-02-19

The baseline migration creates tables from Base.metadata; if it ran before
AccountSync was added, account_syncs may be missing. This migration
creates it explicitly when absent.
"""

from alembic import op
import sqlalchemy as sa
from backend.models.broker_account import SyncStatus


revision = "f4e5d6c7b8a9"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None

_syncstatus_enum = sa.Enum(SyncStatus, name="syncstatus", create_type=False)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("account_syncs"):
        return

    op.create_table(
        "account_syncs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("sync_type", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("status", _syncstatus_enum, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("positions_synced", sa.Integer(), nullable=True),
        sa.Column("transactions_synced", sa.Integer(), nullable=True),
        sa.Column("new_tax_lots_created", sa.Integer(), nullable=True),
        sa.Column("data_range_start", sa.DateTime(), nullable=True),
        sa.Column("data_range_end", sa.DateTime(), nullable=True),
        sa.Column("sync_trigger", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["broker_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_syncs_account_date", "account_syncs", ["account_id", "started_at"], unique=False)


def downgrade():
    op.drop_index("idx_syncs_account_date", "account_syncs", if_exists=True)
    op.drop_table("account_syncs")
