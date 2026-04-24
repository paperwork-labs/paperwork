"""Add market_quad table for Hedgeye GIP Quad Model state.

Stores quarterly and monthly Quad classifications (Q1-Q4), depth,
divergence tracking, and GDP/CPI audit inputs.

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_quad",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("as_of_date", sa.DateTime(), nullable=False, unique=True, index=True),
        sa.Column("quarterly_quad", sa.String(10), nullable=False),
        sa.Column("monthly_quad", sa.String(10), nullable=False),
        sa.Column("quarterly_depth", sa.String(10)),
        sa.Column("monthly_depth", sa.String(10)),
        sa.Column("operative_quad", sa.String(10), nullable=False),
        sa.Column("divergence_flag", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("divergence_months", sa.Integer(), server_default=sa.text("0")),
        sa.Column("gdp_yoy_quarterly", sa.Float()),
        sa.Column("cpi_yoy_quarterly", sa.Float()),
        sa.Column("gdp_first_diff_quarterly", sa.Float()),
        sa.Column("cpi_first_diff_quarterly", sa.Float()),
        sa.Column("gdp_yoy_monthly", sa.Float()),
        sa.Column("cpi_yoy_monthly", sa.Float()),
        sa.Column("gdp_first_diff_monthly", sa.Float()),
        sa.Column("cpi_first_diff_monthly", sa.Float()),
        sa.Column("source", sa.String(20)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("market_quad")
