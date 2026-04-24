"""Ensure market_tracked_plan user FK uses ON DELETE SET NULL, drop redundant
indexes (duplicate institution_cik, redundant market_regime date index), and
add stage_label indexes on snapshot tables.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-06
"""

from alembic import op
from sqlalchemy import text

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    result = conn.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :t)"
        ),
        {"t": name},
    )
    return bool(result.scalar())


def _find_user_fk(conn, table: str, column: str) -> str | None:
    result = conn.execute(
        text(
            """
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = :table
          AND kcu.column_name = :column
          AND ccu.table_name = 'users'
    """
        ),
        {"table": table, "column": column},
    )
    row = result.fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("SET lock_timeout = '10s'"))

    # 1) Idempotent: enforce ON DELETE SET NULL on market_tracked_plan (aligns
    #    with 0015; safe if already applied).
    if _table_exists(conn, "market_tracked_plan"):
        existing = _find_user_fk(conn, "market_tracked_plan", "updated_by_user_id")
        if existing:
            op.drop_constraint(existing, "market_tracked_plan", type_="foreignkey")
        op.create_foreign_key(
            "fk_market_tracked_plan_updated_by_user_id_users",
            "market_tracked_plan",
            "users",
            ["updated_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 2) Drop duplicate index on institution_cik (keep ix_institutional_holdings_institution_cik).
    op.execute(text("DROP INDEX IF EXISTS ix_institutional_holdings_cik"))

    # 3) Redundant with unique index on as_of_date (ix_market_regime_as_of_date).
    op.execute(text("DROP INDEX IF EXISTS idx_regime_date"))

    # 4) stage_label filters (ORM index=True).
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_market_snapshot_stage_label "
            "ON market_snapshot (stage_label)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_market_snapshot_history_stage_label "
            "ON market_snapshot_history (stage_label)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("SET lock_timeout = '10s'"))

    op.execute(text("DROP INDEX IF EXISTS ix_market_snapshot_stage_label"))
    op.execute(text("DROP INDEX IF EXISTS ix_market_snapshot_history_stage_label"))

    op.create_index(
        "idx_regime_date",
        "market_regime",
        ["as_of_date"],
        unique=False,
    )

    op.create_index(
        "ix_institutional_holdings_cik",
        "institutional_holdings",
        ["institution_cik"],
        unique=False,
    )
    # FK left unchanged: still ON DELETE SET NULL after downgrade (0015 / 0017 intent).
