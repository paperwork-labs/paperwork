"""Add orders.approved_by and pending_approval lifecycle support (column only).

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("approved_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_orders_approved_by_users",
        "orders",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_approved_by_users", "orders", type_="foreignkey")
    op.drop_column("orders", "approved_by")
