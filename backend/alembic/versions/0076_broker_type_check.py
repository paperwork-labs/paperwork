"""Add CHECK constraint on orders.broker_type enforcing the BrokerType enum.

Revision ID: 0076
Revises: 0075
Create Date: 2026-04-22

Part of Wave F Phase 0 (trading parity foundation, issue #473). The
``orders.broker_type`` column is ``VARCHAR(20)`` (see ``backend/models/order.py``),
not a Postgres ENUM, so nothing previously enforced that values come from
``BrokerType``. That's fine until we start registering multiple new brokers
(Tradier, E*TRADE, Coinbase, etc.) — at that point a typo (``"tradier_"``,
``"schwabb"``) would silently route through ``BrokerRouter`` until it failed
deep inside an executor, which violates the no-silent-fallback rule.

This migration adds a CHECK constraint that pins the column to the exact set
of values declared in ``BrokerType``. It is **additive and non-destructive**:
no data is rewritten, no rows are touched, and existing values already match
the constraint (verified against prod — only ``ibkr``, ``tastytrade``, ``schwab``
are in use today).

Idempotent against Postgres: the constraint is dropped first if it already
exists so reruns (e.g. replays in staging) don't fail.

Reversible: the downgrade drops the constraint, restoring the pre-0076 state
byte-for-byte.
"""

from __future__ import annotations

from alembic import op


revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


ALLOWED_BROKERS = (
    "ibkr",
    "tastytrade",
    "schwab",
    "etrade",
    "tradier",
    "tradier_sandbox",
    "coinbase",
)

CONSTRAINT_NAME = "ck_orders_broker_type_valid"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind is not None else ""

    values_sql = ", ".join(f"'{v}'" for v in ALLOWED_BROKERS)

    if dialect == "postgresql":
        op.execute(
            f"ALTER TABLE orders DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"
        )
        op.execute(
            f"ALTER TABLE orders ADD CONSTRAINT {CONSTRAINT_NAME} "
            f"CHECK (broker_type IS NULL OR broker_type IN ({values_sql}))"
        )
    else:
        op.create_check_constraint(
            CONSTRAINT_NAME,
            "orders",
            f"broker_type IS NULL OR broker_type IN ({values_sql})",
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind is not None else ""

    if dialect == "postgresql":
        op.execute(
            f"ALTER TABLE orders DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"
        )
    else:
        op.drop_constraint(CONSTRAINT_NAME, "orders", type_="check")
