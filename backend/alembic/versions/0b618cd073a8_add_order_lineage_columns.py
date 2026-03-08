"""add_order_lineage_columns

Revision ID: 0b618cd073a8
Revises: f2a3b4c5d6e7
Create Date: 2026-03-08 06:13:15.829182
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision = "0b618cd073a8"
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    indexes = [i["name"] for i in inspector.get_indexes(table)]
    return index_name in indexes


def upgrade():
    if not _has_column('orders', 'strategy_id'):
        op.add_column('orders', sa.Column('strategy_id', sa.Integer(), nullable=True))
    if not _has_column('orders', 'signal_id'):
        op.add_column('orders', sa.Column('signal_id', sa.Integer(), nullable=True))
    if not _has_column('orders', 'position_id'):
        op.add_column('orders', sa.Column('position_id', sa.Integer(), nullable=True))
    if not _has_column('orders', 'user_id'):
        op.add_column('orders', sa.Column('user_id', sa.Integer(), nullable=True))
    if not _has_column('orders', 'source'):
        op.add_column('orders', sa.Column('source', sa.String(length=20), server_default='manual', nullable=False))
    if not _has_column('orders', 'broker_type'):
        op.add_column('orders', sa.Column('broker_type', sa.String(length=20), server_default='ibkr', nullable=False))
    if not _has_index('orders', 'idx_orders_strategy_id'):
        op.create_index('idx_orders_strategy_id', 'orders', ['strategy_id'], unique=False)
    if not _has_index('orders', 'idx_orders_user_id'):
        op.create_index('idx_orders_user_id', 'orders', ['user_id'], unique=False)
    if not _has_index('orders', 'ix_orders_position_id'):
        op.create_index('ix_orders_position_id', 'orders', ['position_id'], unique=False)
    if not _has_index('orders', 'ix_orders_signal_id'):
        op.create_index('ix_orders_signal_id', 'orders', ['signal_id'], unique=False)

    bind = op.get_bind()
    inspector = sa_inspect(bind)
    fks = [fk["name"] for fk in inspector.get_foreign_keys("orders")]
    if 'fk_orders_user_id' not in fks:
        op.create_foreign_key('fk_orders_user_id', 'orders', 'users', ['user_id'], ['id'])
    if 'fk_orders_strategy_id' not in fks:
        op.create_foreign_key('fk_orders_strategy_id', 'orders', 'strategies', ['strategy_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_orders_strategy_id', 'orders', type_='foreignkey')
    op.drop_constraint('fk_orders_user_id', 'orders', type_='foreignkey')
    op.drop_index('ix_orders_signal_id', table_name='orders')
    op.drop_index('ix_orders_position_id', table_name='orders')
    op.drop_index('idx_orders_user_id', table_name='orders')
    op.drop_index('idx_orders_strategy_id', table_name='orders')
    op.drop_column('orders', 'broker_type')
    op.drop_column('orders', 'source')
    op.drop_column('orders', 'user_id')
    op.drop_column('orders', 'position_id')
    op.drop_column('orders', 'signal_id')
    op.drop_column('orders', 'strategy_id')
