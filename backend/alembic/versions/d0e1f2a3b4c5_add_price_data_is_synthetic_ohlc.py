"""Add is_synthetic_ohlc to price_data

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-02-24

"""
import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE price_data ADD COLUMN IF NOT EXISTS is_synthetic_ohlc BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.drop_column("price_data", "is_synthetic_ohlc")
