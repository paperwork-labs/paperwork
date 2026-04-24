"""Add (analysis_type, symbol) index on market_snapshot_history.

Resolves R39: `repair_stage_history` and the monotonicity audit both
issue `SELECT DISTINCT symbol FROM market_snapshot_history WHERE
analysis_type = 'technical_snapshot' ORDER BY symbol`. With ~2,500
tracked symbols × ~250 rows each = ~625,000 rows in the snapshot history
ledger, that query takes >30s on Postgres without a supporting index and
is killed by the connection-level `statement_timeout = 30000ms`
(D74).

The composite btree index on `(analysis_type, symbol)` speeds
`DISTINCT symbol ... ORDER BY symbol` by avoiding a full sequential scan
on the ledger. Per-symbol window repairs still filter by `symbol` and
`analysis_type`; `ORDER BY as_of_date DESC LIMIT N` continues to use the
existing `idx_hist_type_date` index for date-ordered access.

We use `CREATE INDEX CONCURRENTLY` so the index build does not lock
writers during prod deploy; this requires `autocommit_block` because
CONCURRENTLY cannot run inside a transaction.

Revision ID: 0035
Revises: 0034
Create Date: 2026-04-09

REBASE NOTE: Originally numbered 0022/0021. After PRs #326 (0031,
entitlements), #338 (0033, entitlements hotfix), and #327 (0034, picks
pipeline) merged ahead of this branch, we re-stack on top of 0034 so the
chain stays linear: 0021 -> 0031 -> 0033 -> 0034 -> 0035.
"""

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


INDEX_NAME = "ix_market_snapshot_history_type_symbol"


def upgrade() -> None:
    # CONCURRENTLY can't run inside a transaction; we need an
    # autocommit block so Alembic doesn't wrap this in BEGIN/COMMIT.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON market_snapshot_history (analysis_type, symbol);"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME};")
