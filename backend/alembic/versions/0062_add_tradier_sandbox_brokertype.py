"""Add TRADIER_SANDBOX to brokertype for sandbox Tradier accounts.

Revision ID: 0062
Revises: 0061
Create Date: 2026-04-21

``BrokerOAuthConnection`` uses ``tradier_sandbox`` as the slug for the sandbox
token; ``BrokerAccount`` needs a distinct ``brokertype`` member (value
``tradier_sandbox``) so sync selects the correct OAuth row instead of the most
recent of ``tradier`` + ``tradier_sandbox`` (see D132).
"""

from __future__ import annotations

from alembic import op


revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE brokertype ADD VALUE IF NOT EXISTS 'TRADIER_SANDBOX'"
        )


def downgrade() -> None:
    # Postgres does not support removing an enum value without recreating
    # the entire type. See module docstring.
    pass
