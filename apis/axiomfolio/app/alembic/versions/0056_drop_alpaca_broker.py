"""Drop Alpaca scaffolding: delete any alpaca rows + update CHECK constraint.

Revision ID: 0056
Revises: 0055
Create Date: 2026-04-21

Context:
    Alpaca was half-scaffolded throughout the codebase but never used for
    sync or trading. Autotrading runs through OrderManager -> RiskGate ->
    BrokerRouter against IBKR / Schwab / TastyTrade (D128).

    ``broker_accounts.broker`` is a PostgreSQL ENUM (``brokertype``) and
    SQLAlchemy's default ``Column(Enum(PyEnum))`` stores the *member name*
    (e.g. ``ALPACA``), not the string value (``'alpaca'``). We therefore
    delete using the enum member literal ``'ALPACA'`` and keep the enum
    value in place — postgres enum members cannot be removed cheaply,
    and the Python enum removal plus this DELETE is sufficient to keep
    new rows from appearing. (Earlier drafts of this migration used the
    lowercase string which blew up with
    ``invalid input value for enum brokertype: "alpaca"`` on fresh CI.)

    ``broker_oauth_connections.broker`` is a VARCHAR with a CHECK
    constraint of lowercase slugs; the DELETE + constraint rewrite
    there stays lowercase.
"""

from __future__ import annotations

from alembic import op


revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # VARCHAR(slug) column — lowercase matches existing CHECK constraint.
    op.execute("DELETE FROM broker_oauth_connections WHERE broker = 'alpaca'")
    # ENUM(brokertype) column — SQLAlchemy stores the enum *name*
    # (uppercase), not the lowercase value. Cast via text comparison
    # so the DELETE does not re-introduce the lowercase literal that
    # postgres rejects as not-a-member-of-enum.
    op.execute(
        "DELETE FROM broker_accounts WHERE broker::text = 'ALPACA'"
    )

    op.drop_constraint(
        "ck_broker_oauth_connections_broker",
        "broker_oauth_connections",
        type_="check",
    )
    op.create_check_constraint(
        "ck_broker_oauth_connections_broker",
        "broker_oauth_connections",
        "broker IN ('etrade_sandbox','etrade','schwab','fidelity','tastytrade','ibkr','robinhood','tradier','coinbase')",
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
        "broker IN ('etrade_sandbox','etrade','schwab','fidelity','tastytrade','ibkr','alpaca','robinhood')",
    )
