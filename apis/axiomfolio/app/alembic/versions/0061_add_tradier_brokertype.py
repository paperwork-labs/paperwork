"""Add TRADIER to brokertype enum; extend broker_oauth CHECK for Tradier OAuth slugs.

Revision ID: 0061
Revises: 0060
Create Date: 2026-04-21

Context:
    Tradier (live + sandbox) uses direct OAuth 2.0. ``broker_accounts.broker``
    is Postgres ``brokertype``; SQLAlchemy ``Column(Enum(PyEnum))`` stores the
    member *name* (e.g. ``TRADIER``), so we add the enum value here (same
    pattern as 0060 for E*TRADE).

    ``broker_oauth_connections.broker`` is a ``VARCHAR(32)`` with a
    ``CHECK`` constraint (``ck_broker_oauth_connections_broker``), not a PG
    enum. Migration 0056 whitelisted ``'tradier'`` but sandbox OAuth uses the
    slug ``'tradier_sandbox'``; without extending the CHECK, inserts fail with
    ``CheckViolation`` for that slug.

    ``ALTER TYPE ... ADD VALUE`` must run outside a normal transaction, so
    the enum add uses ``autocommit_block()``. The CHECK is dropped and
    recreated in the same migration after the enum add.

Downgrade:
    Recreates the pre-0061 CHECK (without ``tradier_sandbox``) for symmetry;
    it will fail if any ``'tradier_sandbox'`` rows still exist. Postgres cannot
    remove an enum value without recreating the type; 0061 enum add is
    forward-only.
"""

from __future__ import annotations

from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

# Same broker slug set as 0056 plus sandbox Tradier, matching
# :meth:`0056.upgrade` order for the downgrade path.
_BROKER_OAUTH_IN_0061 = (
    "broker IN ("
    "'etrade_sandbox','etrade','schwab','fidelity',"
    "'tastytrade','ibkr','robinhood',"
    "'tradier','tradier_sandbox','coinbase'"
    ")"
)

_BROKER_OAUTH_IN_0056 = (
    "broker IN ("
    "'etrade_sandbox','etrade','schwab','fidelity',"
    "'tastytrade','ibkr','robinhood',"
    "'tradier','coinbase'"
    ")"
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE brokertype ADD VALUE IF NOT EXISTS 'TRADIER'")

    op.drop_constraint(
        "ck_broker_oauth_connections_broker",
        "broker_oauth_connections",
        type_="check",
    )
    op.create_check_constraint(
        "ck_broker_oauth_connections_broker",
        "broker_oauth_connections",
        _BROKER_OAUTH_IN_0061,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_broker_oauth_connections_broker",
        "broker_oauth_connections",
        type_="check",
    )
    op.create_check_constraint(
        "ck_broker_oauth_connections_broker",
        "broker_oauth_connections",
        _BROKER_OAUTH_IN_0056,
    )
