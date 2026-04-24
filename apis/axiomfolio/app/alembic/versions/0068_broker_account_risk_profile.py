"""Add broker_account_risk_profiles table.

Stores per-account risk-profile overrides. The firm-level caps remain in
``backend/config.py`` and ``app/services/risk/firm_caps.py``; the
effective limit for any field is ``min(firm_cap, per_account_cap)`` (see
``app/services/risk/account_risk_profile.py``). Per-account values
can only tighten firm caps, never loosen them — the ``apply_override``
service enforces this invariant at write time, and the merge service
enforces it at read time.

Revision ID: 0068
Revises: 0065
Create Date: 2026-04-21

After ``0067`` (sleeve/conviction) is on ``main``, rebase this branch and
set ``down_revision = "0067"`` if Alembic reports multiple heads.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0068"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_account_risk_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("broker_accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("max_position_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("max_stage_2c_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("max_options_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("max_daily_loss_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("hard_stop_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "max_position_pct IS NULL OR (max_position_pct >= 0 AND max_position_pct <= 1)",
            name="ck_barp_max_position_pct_0_1",
        ),
        sa.CheckConstraint(
            "max_stage_2c_pct IS NULL OR (max_stage_2c_pct >= 0 AND max_stage_2c_pct <= 1)",
            name="ck_barp_max_stage_2c_pct_0_1",
        ),
        sa.CheckConstraint(
            "max_options_pct IS NULL OR (max_options_pct >= 0 AND max_options_pct <= 1)",
            name="ck_barp_max_options_pct_0_1",
        ),
        sa.CheckConstraint(
            "max_daily_loss_pct IS NULL OR (max_daily_loss_pct >= 0 AND max_daily_loss_pct <= 1)",
            name="ck_barp_max_daily_loss_pct_0_1",
        ),
        sa.CheckConstraint(
            "hard_stop_pct IS NULL OR (hard_stop_pct >= 0 AND hard_stop_pct <= 1)",
            name="ck_barp_hard_stop_pct_0_1",
        ),
    )
    op.create_index(
        "ix_broker_account_risk_profiles_account_id",
        "broker_account_risk_profiles",
        ["account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_broker_account_risk_profiles_account_id",
        table_name="broker_account_risk_profiles",
    )
    op.drop_table("broker_account_risk_profiles")
