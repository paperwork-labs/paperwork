"""Plaid Investments integration schema.

Revision ID: 0075
Revises: 0074
Create Date: 2026-04-22

Adds the persistence surface for the single-phase Plaid Investments Pro-tier
feature (plan: ``docs/plans/PLAID_FIDELITY_401K.md``, decision D130 in
``docs/KNOWLEDGE.md``):

* ``broker_accounts.connection_source`` VARCHAR(16) NOT NULL DEFAULT
  ``'direct'``.  Existing rows are backfilled to ``'direct'`` via the server
  default; new Plaid-wired rows set ``'plaid'``.  A CHECK constraint limits
  values to ``('direct','plaid')`` so a typo fails loudly at INSERT time
  rather than silently contaminating the sync dispatcher.

* ``taxlotsource`` enum gains the value ``'aggregator'`` for Plaid-sourced
  tax lots that have no per-lot cost basis (``cost_per_share IS NULL``).
  The enum add runs in an autocommit block because Postgres forbids
  ``ALTER TYPE ... ADD VALUE`` inside a transaction (see migration 0063
  for the same pattern).

* ``plaid_connections`` table: one row per Plaid Item (``user_id``,
  institution, access token).  Access tokens are Fernet-encrypted at rest
  — the column is TEXT not VARCHAR because MultiFernet output grows with
  key-rotation metadata.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) broker_accounts.connection_source -----------------------------------
    #
    # Server default ``'direct'`` backfills existing rows in a single pass.
    # The NOT NULL is safe because Postgres fills the column using the
    # default before applying the constraint.
    op.add_column(
        "broker_accounts",
        sa.Column(
            "connection_source",
            sa.String(length=16),
            nullable=False,
            server_default="direct",
        ),
    )
    op.create_check_constraint(
        "ck_broker_accounts_connection_source",
        "broker_accounts",
        "connection_source IN ('direct', 'plaid')",
    )

    # 2) taxlotsource enum gains 'AGGREGATOR' --------------------------------
    #
    # The existing values in ``taxlotsource`` are the SQLAlchemy enum
    # *names* (``OFFICIAL_STATEMENT``, ``REALTIME_API``, ``MANUAL_ENTRY``,
    # ``CALCULATED``) because the model declares ``SQLEnum(TaxLotSource)``
    # without ``values_callable``, and SQLA defaults to the enum NAME.
    # We follow that convention here so ``TaxLotSource.AGGREGATOR`` serializes
    # to the string ``'AGGREGATOR'`` and matches the DB enum.
    #
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction; Alembic
    # offline mode still emits the statement but is a no-op there. We use
    # ``IF NOT EXISTS`` so re-running this migration on an environment
    # where the value was added out-of-band doesn't fail.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE taxlotsource ADD VALUE IF NOT EXISTS 'AGGREGATOR'"
        )

    # 3) plaid_connections table ---------------------------------------------
    op.create_table(
        "plaid_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Plaid Item identifier; unique across all users by Plaid guarantee.
        sa.Column("item_id", sa.String(length=64), nullable=False, unique=True),
        # Fernet ciphertext of the Plaid access token. NEVER store plaintext.
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("institution_id", sa.String(length=32), nullable=False),
        sa.Column("institution_name", sa.String(length=128), nullable=False),
        sa.Column("transactions_cursor", sa.String(length=256), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "environment",
            sa.String(length=16),
            nullable=False,
            server_default="sandbox",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'needs_reauth', 'revoked', 'error')",
            name="ck_plaid_connections_status",
        ),
        sa.CheckConstraint(
            "environment IN ('sandbox', 'development', 'production')",
            name="ck_plaid_connections_environment",
        ),
    )
    op.create_index(
        "idx_plaid_connections_user_status",
        "plaid_connections",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    # Drop in reverse order of creation. We cannot remove enum values in
    # Postgres (no ALTER TYPE DROP VALUE), so ``'aggregator'`` lingers on
    # downgrade — that's acceptable because nothing depends on its absence.
    op.drop_index(
        "idx_plaid_connections_user_status", table_name="plaid_connections"
    )
    op.drop_table("plaid_connections")

    op.drop_constraint(
        "ck_broker_accounts_connection_source",
        "broker_accounts",
        type_="check",
    )
    op.drop_column("broker_accounts", "connection_source")
