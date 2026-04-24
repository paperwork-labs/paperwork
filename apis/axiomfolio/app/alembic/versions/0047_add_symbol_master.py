"""Add symbol master tables (single source of truth for symbol identity).

Creates three new tables:

* ``symbol_master`` — canonical row per tradeable entity. Holds the
  current ``primary_ticker`` plus stable cross-system identifiers
  (CIK, ISIN, FIGI), GICS classification, exchange / country /
  currency, and lifecycle status.
* ``symbol_alias`` — historical or alternate tickers for a master
  row. ``[valid_from, valid_to)`` half-open interval supports
  point-in-time resolution (e.g. "what did 'FB' mean on
  2022-06-08?").
* ``symbol_history`` — append-only audit ledger of changes
  (rename, exchange migration, status flip, merger).

This migration only ADDS new tables; no existing table is altered to
FK into the master. Downstream callers migrate to the master in
follow-up PRs per the master plan (Phase 7a).

Enums are persisted as VARCHAR rather than Postgres ENUM types to
avoid the ``ALTER TYPE … ADD VALUE`` headaches we've hit before.

Revision ID: 0047
Revises: 0040

Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0047"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # symbol_master
    # ------------------------------------------------------------------
    op.create_table(
        "symbol_master",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("primary_ticker", sa.String(20), nullable=False),
        sa.Column("cik", sa.String(20), nullable=True),
        sa.Column("isin", sa.String(20), nullable=True),
        sa.Column("figi", sa.String(20), nullable=True),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(20), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("gics_code", sa.String(20), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("delisted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "merged_into_symbol_master_id",
            sa.Integer(),
            sa.ForeignKey("symbol_master.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("primary_ticker", name="uq_symbol_master_primary_ticker"),
    )
    op.create_index(
        "ix_symbol_master_primary_ticker",
        "symbol_master",
        ["primary_ticker"],
        unique=True,
    )
    op.create_index("ix_symbol_master_cik", "symbol_master", ["cik"])
    op.create_index("ix_symbol_master_isin", "symbol_master", ["isin"])
    op.create_index("ix_symbol_master_figi", "symbol_master", ["figi"])
    op.create_index(
        "ix_symbol_master_merged_into",
        "symbol_master",
        ["merged_into_symbol_master_id"],
    )
    op.create_index(
        "idx_symbol_master_asset_class_status",
        "symbol_master",
        ["asset_class", "status"],
    )
    op.create_index("idx_symbol_master_status", "symbol_master", ["status"])

    # ------------------------------------------------------------------
    # symbol_alias
    # ------------------------------------------------------------------
    op.create_table(
        "symbol_alias",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "symbol_master_id",
            sa.Integer(),
            sa.ForeignKey("symbol_master.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_ticker", sa.String(20), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "symbol_master_id",
            "alias_ticker",
            "valid_from",
            name="uq_alias_master_ticker_from",
        ),
    )
    op.create_index("ix_symbol_alias_master", "symbol_alias", ["symbol_master_id"])
    op.create_index("ix_symbol_alias_ticker", "symbol_alias", ["alias_ticker"])
    op.create_index(
        "idx_symbol_alias_ticker_from",
        "symbol_alias",
        ["alias_ticker", "valid_from"],
    )

    # ------------------------------------------------------------------
    # symbol_history
    # ------------------------------------------------------------------
    op.create_table(
        "symbol_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "symbol_master_id",
            sa.Integer(),
            sa.ForeignKey("symbol_master.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change_type", sa.String(30), nullable=False),
        # JSONB so equality comparisons work natively (Postgres has no
        # `=` operator for `json`, which broke the dedupe path in
        # ``record_ticker_change`` when this used `sa.JSON()`).
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source", sa.String(30), nullable=False),
    )
    op.create_index("ix_symbol_history_master", "symbol_history", ["symbol_master_id"])
    op.create_index(
        "ix_symbol_history_effective_date",
        "symbol_history",
        ["effective_date"],
    )
    op.create_index(
        "idx_symbol_history_master_effective",
        "symbol_history",
        ["symbol_master_id", "effective_date"],
    )
    op.create_index(
        "idx_symbol_history_change_type",
        "symbol_history",
        ["change_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_symbol_history_change_type", table_name="symbol_history")
    op.drop_index("idx_symbol_history_master_effective", table_name="symbol_history")
    op.drop_index("ix_symbol_history_effective_date", table_name="symbol_history")
    op.drop_index("ix_symbol_history_master", table_name="symbol_history")
    op.drop_table("symbol_history")

    op.drop_index("idx_symbol_alias_ticker_from", table_name="symbol_alias")
    op.drop_index("ix_symbol_alias_ticker", table_name="symbol_alias")
    op.drop_index("ix_symbol_alias_master", table_name="symbol_alias")
    op.drop_table("symbol_alias")

    op.drop_index("idx_symbol_master_status", table_name="symbol_master")
    op.drop_index("idx_symbol_master_asset_class_status", table_name="symbol_master")
    op.drop_index("ix_symbol_master_merged_into", table_name="symbol_master")
    op.drop_index("ix_symbol_master_figi", table_name="symbol_master")
    op.drop_index("ix_symbol_master_isin", table_name="symbol_master")
    op.drop_index("ix_symbol_master_cik", table_name="symbol_master")
    op.drop_index("ix_symbol_master_primary_ticker", table_name="symbol_master")
    op.drop_table("symbol_master")
