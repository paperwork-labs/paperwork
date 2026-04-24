"""Add COINBASE to brokertype enum (Coinbase consumer wallet OAuth).

Revision ID: 0063
Revises: 0062
Create Date: 2026-04-21

``broker_oauth_connections.broker`` already allows ``coinbase`` via migration
0061's CHECK constraint. This revision adds the matching ``BrokerAccount``
Postgres enum label so ORM rows can persist ``BrokerType.COINBASE``.
"""

from __future__ import annotations

from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE brokertype ADD VALUE IF NOT EXISTS 'COINBASE'")


def downgrade() -> None:
    pass
