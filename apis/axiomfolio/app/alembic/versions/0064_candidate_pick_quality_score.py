"""Add pick quality score columns to candidates.

Revision ID: 0064
Revises: 0063
Create Date: 2026-04-21

Stores explainable 0-100 pick quality from ``PickQualityScorer`` alongside
the generator's legacy ``score`` field.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("pick_quality_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "candidates",
        sa.Column("pick_quality_breakdown", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidates", "pick_quality_breakdown")
    op.drop_column("candidates", "pick_quality_score")
