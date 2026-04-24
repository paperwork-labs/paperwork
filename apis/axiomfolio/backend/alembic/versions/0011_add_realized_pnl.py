"""Add realized_pnl and cost_basis to orders.

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('realized_pnl', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('cost_basis', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'cost_basis')
    op.drop_column('orders', 'realized_pnl')
