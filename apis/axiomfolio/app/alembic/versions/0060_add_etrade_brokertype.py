"""Add ETRADE value to brokertype enum (Phase 1 / PR D2).

Revision ID: 0060
Revises: 0059
Create Date: 2026-04-21

Context:
    Phase 1 of the broker_parity_medallion_v1 plan adds direct OAuth for
    E*TRADE (sandbox-only in v1). ``broker_accounts.broker`` is a Postgres
    ENUM (``brokertype``); SQLAlchemy's default ``Column(Enum(PyEnum))``
    persists the *member name* (e.g. ``ETRADE``), not the lowercase value
    (``'etrade'``). Migration 0056 applied the same pattern when deleting
    ``ALPACA`` rows, so we add ``'ETRADE'`` here.

    ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block on
    most Postgres clients, so we use ``autocommit_block()``. ``IF NOT
    EXISTS`` keeps the migration idempotent (safe to re-run on partial
    deploys, and a no-op on DBs where a prior manual hotfix added the
    value).

Downgrade:
    Postgres cannot remove individual enum values cheaply (it requires
    recreating the enum type and rewriting every column referencing it).
    Since enum additions are effectively forward-only, the downgrade is
    a documented no-op; rolling back the Python enum member + redeploying
    is sufficient to prevent new ``ETRADE`` rows from being written.
"""

from __future__ import annotations

from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE brokertype ADD VALUE IF NOT EXISTS 'ETRADE'")


def downgrade() -> None:
    # Postgres does not support removing an enum value without recreating
    # the entire type. See module docstring.
    pass
