"""Replace nullable UNIQUE with functional unique index on provider_account_id.

Postgres treats NULL as distinct in UNIQUE constraints, so multiple rows could
exist for the same (user_id, broker) when provider_account_id IS NULL (E*TRADE
sandbox). Use COALESCE(provider_account_id, '') in a unique index instead.

Revision ID: 0044
Revises: 0043

Create Date: 2026-04-20
"""

from alembic import op


revision = "0051"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_broker_oauth_user_broker_provider",
        "broker_oauth_connections",
        type_="unique",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_broker_oauth_user_broker_provider_norm
        ON broker_oauth_connections (
            user_id,
            broker,
            COALESCE(provider_account_id, '')
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_broker_oauth_user_broker_provider_norm")
    op.create_unique_constraint(
        "uq_broker_oauth_user_broker_provider",
        "broker_oauth_connections",
        ["user_id", "broker", "provider_account_id"],
    )
