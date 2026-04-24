"""Add positions.runner_since for runner (>=1R) tracking.

Revision ID: 0071
Revises: 0070
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("positions", sa.Column("runner_since", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("positions", "runner_since")
