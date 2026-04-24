"""Add earnings_calendar table.

Stores upcoming and recent earnings dates with EPS/revenue estimates and
actuals, populated from FMP (premium) with yfinance fallback.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "earnings_calendar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("fiscal_period", sa.String(20)),
        sa.Column("estimate_eps", sa.Numeric()),
        sa.Column("actual_eps", sa.Numeric()),
        sa.Column("estimate_revenue", sa.Numeric()),
        sa.Column("actual_revenue", sa.Numeric()),
        sa.Column("time_of_day", sa.String(10)),
        sa.Column("source", sa.String(20)),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "symbol",
            "report_date",
            "fiscal_period",
            name="uq_earnings_sym_date_period",
        ),
    )
    op.create_index("idx_earnings_report_date", "earnings_calendar", ["report_date"])
    op.create_index("idx_earnings_symbol_date", "earnings_calendar", ["symbol", "report_date"])


def downgrade() -> None:
    op.drop_index("idx_earnings_symbol_date", table_name="earnings_calendar")
    op.drop_index("idx_earnings_report_date", table_name="earnings_calendar")
    op.drop_table("earnings_calendar")
