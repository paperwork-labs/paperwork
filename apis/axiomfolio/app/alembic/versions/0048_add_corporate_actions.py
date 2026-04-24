"""Add corporate_actions + applied_corporate_actions tables.

Phase 7c. Authoritative ledger of corporate actions (splits, dividends,
mergers, spinoffs, name changes) plus the per-user, per-holding apply
records that make every adjustment fully reversible.

We chain off 0040 to dodge the (currently-unmerged) 0041..0047 sibling
PRs. The single-head invariant is enforced by
``test_migration_chain.test_single_head``; whichever sibling lands
first will be responsible for re-pointing 0048's ``down_revision`` to
the new tip during merge.

Revision ID: 0048
Revises: 0049
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("symbol_master_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("declaration_date", sa.Date(), nullable=True),
        sa.Column("ratio_numerator", sa.Numeric(20, 8), nullable=True),
        sa.Column("ratio_denominator", sa.Numeric(20, 8), nullable=True),
        sa.Column("cash_amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("cash_currency", sa.String(length=8), nullable=True, server_default="USD"),
        sa.Column("target_symbol", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "ohlcv_adjusted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "symbol",
            "action_type",
            "ex_date",
            name="uq_corp_action_symbol_type_exdate",
        ),
    )
    op.create_index(
        "ix_corporate_actions_symbol",
        "corporate_actions",
        ["symbol"],
    )
    op.create_index(
        "ix_corporate_actions_symbol_master_id",
        "corporate_actions",
        ["symbol_master_id"],
    )
    op.create_index(
        "ix_corporate_actions_ex_date",
        "corporate_actions",
        ["ex_date"],
    )
    op.create_index(
        "ix_corporate_actions_status",
        "corporate_actions",
        ["status"],
    )
    op.create_index(
        "ix_corp_action_status_exdate",
        "corporate_actions",
        ["status", "ex_date"],
    )

    op.create_table(
        "applied_corporate_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "corporate_action_id",
            sa.Integer(),
            sa.ForeignKey("corporate_actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "position_id",
            sa.Integer(),
            sa.ForeignKey("positions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tax_lot_id",
            sa.Integer(),
            sa.ForeignKey("tax_lots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("original_qty", sa.Numeric(20, 8), nullable=False),
        sa.Column("original_cost_basis", sa.Numeric(20, 8), nullable=False),
        sa.Column("original_avg_cost", sa.Numeric(20, 8), nullable=True),
        sa.Column("adjusted_qty", sa.Numeric(20, 8), nullable=False),
        sa.Column("adjusted_cost_basis", sa.Numeric(20, 8), nullable=False),
        sa.Column("adjusted_avg_cost", sa.Numeric(20, 8), nullable=True),
        sa.Column("cash_credited", sa.Numeric(20, 8), nullable=True),
        sa.Column(
            "applied_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "corporate_action_id",
            "user_id",
            "position_id",
            "tax_lot_id",
            name="uq_applied_action_user_position_lot",
        ),
    )
    op.create_index(
        "ix_applied_corporate_actions_corporate_action_id",
        "applied_corporate_actions",
        ["corporate_action_id"],
    )
    op.create_index(
        "ix_applied_corporate_actions_user_id",
        "applied_corporate_actions",
        ["user_id"],
    )
    op.create_index(
        "ix_applied_corporate_actions_position_id",
        "applied_corporate_actions",
        ["position_id"],
    )
    op.create_index(
        "ix_applied_corporate_actions_tax_lot_id",
        "applied_corporate_actions",
        ["tax_lot_id"],
    )
    op.create_index(
        "ix_applied_action_user_symbol",
        "applied_corporate_actions",
        ["user_id", "symbol"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_applied_action_user_symbol",
        table_name="applied_corporate_actions",
    )
    op.drop_index(
        "ix_applied_corporate_actions_tax_lot_id",
        table_name="applied_corporate_actions",
    )
    op.drop_index(
        "ix_applied_corporate_actions_position_id",
        table_name="applied_corporate_actions",
    )
    op.drop_index(
        "ix_applied_corporate_actions_user_id",
        table_name="applied_corporate_actions",
    )
    op.drop_index(
        "ix_applied_corporate_actions_corporate_action_id",
        table_name="applied_corporate_actions",
    )
    op.drop_table("applied_corporate_actions")

    op.drop_index("ix_corp_action_status_exdate", table_name="corporate_actions")
    op.drop_index("ix_corporate_actions_status", table_name="corporate_actions")
    op.drop_index("ix_corporate_actions_ex_date", table_name="corporate_actions")
    op.drop_index(
        "ix_corporate_actions_symbol_master_id",
        table_name="corporate_actions",
    )
    op.drop_index("ix_corporate_actions_symbol", table_name="corporate_actions")
    op.drop_table("corporate_actions")
