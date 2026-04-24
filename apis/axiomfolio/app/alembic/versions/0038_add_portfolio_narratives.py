"""Add portfolio_narratives for daily AI narrative.

Revision ID: 0038
Revises: 0037
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_narratives",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("narrative_date", sa.Date(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("summary_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(8, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "narrative_date", name="uq_portfolio_narrative_user_date"),
    )
    op.create_index(
        "ix_portfolio_narrative_user_created",
        "portfolio_narratives",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_portfolio_narratives_user_id"),
        "portfolio_narratives",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_portfolio_narratives_prompt_hash"),
        "portfolio_narratives",
        ["prompt_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_portfolio_narratives_prompt_hash"), table_name="portfolio_narratives")
    op.drop_index(op.f("ix_portfolio_narratives_user_id"), table_name="portfolio_narratives")
    op.drop_index("ix_portfolio_narrative_user_created", table_name="portfolio_narratives")
    op.drop_table("portfolio_narratives")
