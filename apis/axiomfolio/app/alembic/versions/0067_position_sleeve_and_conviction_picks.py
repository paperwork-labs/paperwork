"""Position sleeve tagging + conviction picks table.

Revision ID: 0067
Revises: 0068
Create Date: 2026-04-21

Adds two pieces of schema:

1. ``positions.sleeve`` — lightweight ``active`` / ``conviction`` tag that
   lets downstream services (trade card, exit cascade, health auditor)
   branch on how aggressively a position is being managed. Nullable
   defaulting to ``active`` so legacy rows classify as short-term by
   default; a user or the nightly classifier can promote to
   ``conviction``. Composite index on ``(user_id, sleeve)`` keeps the
   "give me this user's conviction book" lookup cheap.

2. ``conviction_picks`` — persisted output of the nightly conviction
   pick generator. One row per symbol per generation run; the latest
   generation per user is what ``GET /api/v1/picks/conviction`` serves.

Revision chains after ``0068`` (per-account risk profile; ``main`` as of
2026-04-22).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- positions.sleeve -------------------------------------------------
    op.add_column(
        "positions",
        sa.Column(
            "sleeve",
            sa.String(length=32),
            nullable=True,
            server_default="active",
        ),
    )
    op.create_index(
        "idx_positions_user_sleeve",
        "positions",
        ["user_id", "sleeve"],
    )

    # --- conviction_picks -------------------------------------------------
    op.create_table(
        "conviction_picks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(10, 4), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("stage_label", sa.String(length=10), nullable=True),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("generator_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_conviction_picks_user_generated",
        "conviction_picks",
        ["user_id", "generated_at"],
    )
    op.create_index(
        "idx_conviction_picks_user_rank",
        "conviction_picks",
        ["user_id", "rank"],
    )


def downgrade() -> None:
    op.drop_index("idx_conviction_picks_user_rank", table_name="conviction_picks")
    op.drop_index("idx_conviction_picks_user_generated", table_name="conviction_picks")
    op.drop_table("conviction_picks")
    op.drop_index("idx_positions_user_sleeve", table_name="positions")
    op.drop_column("positions", "sleeve")
