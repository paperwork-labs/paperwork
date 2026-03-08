"""create_watchlists_table

Revision ID: ca304cdf065a
Revises: 0b618cd073a8
Create Date: 2026-03-08 06:40:06.176565
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision = "ca304cdf065a"
down_revision = '0b618cd073a8'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if 'watchlists' in inspector.get_table_names():
        return

    op.create_table('watchlists',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'symbol', name='uq_watchlist_user_symbol')
    )
    op.create_index('idx_watchlist_user_symbol', 'watchlists', ['user_id', 'symbol'], unique=False)
    op.create_index(op.f('ix_watchlists_id'), 'watchlists', ['id'], unique=False)
    op.create_index(op.f('ix_watchlists_symbol'), 'watchlists', ['symbol'], unique=False)
    op.create_index(op.f('ix_watchlists_user_id'), 'watchlists', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_watchlists_user_id'), table_name='watchlists')
    op.drop_index(op.f('ix_watchlists_symbol'), table_name='watchlists')
    op.drop_index(op.f('ix_watchlists_id'), table_name='watchlists')
    op.drop_index('idx_watchlist_user_symbol', table_name='watchlists')
    op.drop_table('watchlists')



