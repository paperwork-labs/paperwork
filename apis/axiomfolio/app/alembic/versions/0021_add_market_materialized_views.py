"""Add market data materialized views and supporting index.

Creates:
- idx_hist_type_date: Composite index on (analysis_type, as_of_date)
  for market_snapshot_history to speed breadth/stage queries.
- mv_breadth_daily: Pre-computed % above SMA50/200 per trading day.
- mv_stage_distribution: Daily stage label counts.
- mv_sector_performance: Sector-level aggregations from latest snapshots.

All MVs support CONCURRENTLY refresh via unique indexes.
MVs are created WITH NO DATA to avoid blocking API startup; the
nightly pipeline populates them via refresh_market_mvs task.

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-10
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hist_type_date "
        "ON market_snapshot_history (analysis_type, as_of_date);"
    )

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_breadth_daily AS
        SELECT
            as_of_date::date AS dt,
            COUNT(*) FILTER (
                WHERE current_price > sma_50 AND sma_50 IS NOT NULL
            ) AS above_50,
            COUNT(*) FILTER (
                WHERE current_price > sma_200 AND sma_200 IS NOT NULL
            ) AS above_200,
            COUNT(*) AS total
        FROM market_snapshot_history
        WHERE analysis_type = 'technical_snapshot'
        GROUP BY as_of_date::date
        WITH NO DATA;
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_breadth_daily_dt ON mv_breadth_daily (dt);"
    )

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_stage_distribution AS
        SELECT
            as_of_date::date AS dt,
            stage_label,
            COUNT(*) AS cnt
        FROM market_snapshot_history
        WHERE analysis_type = 'technical_snapshot'
        GROUP BY as_of_date::date, stage_label
        WITH NO DATA;
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_stage_dist_dt_label "
        "ON mv_stage_distribution (dt, stage_label);"
    )

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sector_performance AS
        SELECT
            sector,
            AVG(perf_20d) AS avg_perf_20d,
            AVG(rs_mansfield_pct) AS avg_rs,
            COUNT(*) AS cnt
        FROM market_snapshot
        WHERE analysis_type = 'technical_snapshot'
          AND sector IS NOT NULL
        GROUP BY sector
        WITH NO DATA;
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_sector_perf_sector "
        "ON mv_sector_performance (sector);"
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_sector_performance;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_stage_distribution;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_breadth_daily;")
    op.execute("DROP INDEX IF EXISTS idx_hist_type_date;")
