"""Add trade_decision_explanations table.

Persists structured "why was this trade taken" explanations for each
executed order. The row is the audit trail surfaced in the portfolio
trades drawer; it caches the LLM payload so the explainer is not re-run
on every page load.

Why this design:

* ``UNIQUE(order_id, version)`` keeps the regenerate endpoint's
  versioned-row contract enforceable at the DB layer (no race).
* ``cost_usd`` is ``Numeric(10, 6)`` because OpenAI prices in fractions
  of a cent; ``Float`` would break the iron law that monetary values
  use ``Decimal``.
* ``trigger_type`` is constrained at the DB layer so an upstream bug
  cannot persist a junk label that the UI then has to filter out.
* ``is_fallback`` records whether the row was produced by the
  deterministic-rule fallback path (LLM unavailable / malformed
  output). Surfacing it in the UI satisfies the no-silent-fallback rule.

Revision ID: 0051
Revises: 0040
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_decision_explanations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trade_id",
            sa.Integer(),
            sa.ForeignKey("trades.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column("model_used", sa.String(64), nullable=False),
        sa.Column(
            "prompt_token_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "completion_token_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "cost_usd >= 0",
            name="ck_trade_decision_explanations_cost_nonneg",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_trade_decision_explanations_version_positive",
        ),
        sa.CheckConstraint(
            "trigger_type IN ('pick','scan','rebalance','manual','strategy','unknown')",
            name="ck_trade_decision_explanations_trigger_type",
        ),
        sa.UniqueConstraint(
            "order_id",
            "version",
            name="uq_trade_decision_explanations_order_version",
        ),
    )
    op.create_index(
        "ix_trade_decision_explanations_user_id",
        "trade_decision_explanations",
        ["user_id"],
    )
    op.create_index(
        "ix_trade_decision_explanations_order_id",
        "trade_decision_explanations",
        ["order_id"],
    )
    op.create_index(
        "ix_trade_decision_explanations_trade_id",
        "trade_decision_explanations",
        ["trade_id"],
    )
    op.create_index(
        "ix_trade_decision_explanations_user_generated",
        "trade_decision_explanations",
        ["user_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trade_decision_explanations_user_generated",
        table_name="trade_decision_explanations",
    )
    op.drop_index(
        "ix_trade_decision_explanations_trade_id",
        table_name="trade_decision_explanations",
    )
    op.drop_index(
        "ix_trade_decision_explanations_order_id",
        table_name="trade_decision_explanations",
    )
    op.drop_index(
        "ix_trade_decision_explanations_user_id",
        table_name="trade_decision_explanations",
    )
    op.drop_table("trade_decision_explanations")
