"""Add Stage Analysis state, Quad Engine, and Scan/Sizing columns.

Adds 11 nullable columns to market_snapshot and market_snapshot_history
for state tracking (pass_count, atre_promoted, action_override,
manual_review), Quad Engine (quad_quarterly, quad_monthly,
quad_divergence_flag, quad_depth), and Scan enrichment (forward_rr,
correlation_flag, sector_confirmation).

Also adds weights_used JSON to market_regime for audit trail.

All columns are nullable for backward compatibility with existing rows.

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_SNAPSHOT_TABLES = ("market_snapshot", "market_snapshot_history")

_NEW_COLUMNS = [
    # Stage Analysis state
    ("pass_count", sa.Integer(), None),
    ("atre_promoted", sa.Boolean(), None),
    ("action_override", sa.String(10), None),
    ("manual_review", sa.Boolean(), None),
    # Quad Engine
    ("quad_quarterly", sa.String(10), None),
    ("quad_monthly", sa.String(10), None),
    ("quad_divergence_flag", sa.Boolean(), None),
    ("quad_depth", sa.String(10), None),
    # Scan / Sizing enrichment
    ("forward_rr", sa.Float(), None),
    ("correlation_flag", sa.Boolean(), None),
    ("sector_confirmation", sa.String(20), None),
]


def upgrade() -> None:
    for table in _SNAPSHOT_TABLES:
        for col_name, col_type, server_default in _NEW_COLUMNS:
            op.add_column(
                table,
                sa.Column(col_name, col_type, nullable=True, server_default=server_default),
            )

    op.add_column(
        "market_regime",
        sa.Column("weights_used", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_regime", "weights_used")

    for table in _SNAPSHOT_TABLES:
        for col_name, _, _ in reversed(_NEW_COLUMNS):
            op.drop_column(table, col_name)
