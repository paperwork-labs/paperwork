"""Add foreign keys to orders table for signal_id and position_id.

Revision ID: 0005
Revises: bce73e98544e
Create Date: 2026-03-27

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "bce73e98544e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add FK constraint for signal_id -> signals.id
    op.create_foreign_key(
        "fk_orders_signal_id",
        "orders",
        "signals",
        ["signal_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add FK constraint for position_id -> positions.id
    op.create_foreign_key(
        "fk_orders_position_id",
        "orders",
        "positions",
        ["position_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Also update strategy_id FK to have ondelete="SET NULL" if not already
    # (This is idempotent if constraint name differs)
    op.drop_constraint("orders_strategy_id_fkey", "orders", type_="foreignkey")
    op.create_foreign_key(
        "fk_orders_strategy_id",
        "orders",
        "strategies",
        ["strategy_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Also update user_id FK to have ondelete="SET NULL"
    op.drop_constraint("orders_user_id_fkey", "orders", type_="foreignkey")
    op.create_foreign_key(
        "fk_orders_user_id",
        "orders",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Remove new FK constraints
    op.drop_constraint("fk_orders_signal_id", "orders", type_="foreignkey")
    op.drop_constraint("fk_orders_position_id", "orders", type_="foreignkey")

    # Restore original FK constraints without ondelete
    op.drop_constraint("fk_orders_strategy_id", "orders", type_="foreignkey")
    op.create_foreign_key(
        "orders_strategy_id_fkey",
        "orders",
        "strategies",
        ["strategy_id"],
        ["id"],
    )

    op.drop_constraint("fk_orders_user_id", "orders", type_="foreignkey")
    op.create_foreign_key(
        "orders_user_id_fkey",
        "orders",
        "users",
        ["user_id"],
        ["id"],
    )
