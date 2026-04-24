"""add_strategy_id_to_position

Revision ID: bce73e98544e
Revises: 0004
Create Date: 2026-03-27 16:47:30.390231

Adds strategy_id and entry_signal_id to positions table for attribution of
positions to the strategies that generated them.
"""

from alembic import op
import sqlalchemy as sa

revision = "bce73e98544e"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("positions", sa.Column("strategy_id", sa.Integer(), nullable=True))
    op.add_column("positions", sa.Column("entry_signal_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_positions_strategy_id"), "positions", ["strategy_id"], unique=False)
    op.create_foreign_key(
        "fk_positions_strategy_id", "positions", "strategies", ["strategy_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_positions_entry_signal_id", "positions", "signals", ["entry_signal_id"], ["id"]
    )


def downgrade():
    op.drop_constraint("fk_positions_entry_signal_id", "positions", type_="foreignkey")
    op.drop_constraint("fk_positions_strategy_id", "positions", type_="foreignkey")
    op.drop_index(op.f("ix_positions_strategy_id"), table_name="positions")
    op.drop_column("positions", "entry_signal_id")
    op.drop_column("positions", "strategy_id")
