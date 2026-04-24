"""Materialized view management for market data aggregations.

Provides pre-computed breadth, stage distribution, and sector performance
data with graceful fallback to raw table queries when MVs don't exist.
Follows the same pattern as ``ActivityAggregatorService``.

Both MV and raw-fallback paths compute breadth over the full
``analysis_type='technical_snapshot'`` universe (not filtered to
tracked symbols) so that results are identical regardless of which
path executes.

medallion: silver
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.models.market_data import MarketSnapshot, MarketSnapshotHistory

logger = logging.getLogger(__name__)

_BREADTH_CACHE_KEY = "dashboard:breadth_series"
_BREADTH_CACHE_TTL = 3600
_STAGE_DIST_CACHE_KEY = "dashboard:stage_distribution"
_STAGE_DIST_CACHE_TTL = 3600
_SECTOR_PERF_CACHE_KEY = "dashboard:sector_performance"
_SECTOR_PERF_CACHE_TTL = 300


def _redis():
    from app.services.market.market_data_service import infra

    return infra.redis_client


class MarketMVService:
    """Manages market data materialized views with graceful fallback.

    All query methods follow: Redis cache -> MV -> raw table fallback.
    """

    VIEWS = ("mv_breadth_daily", "mv_stage_distribution", "mv_sector_performance")

    @staticmethod
    def _mv_exists(db: Session, name: str) -> bool:
        sql = text("SELECT to_regclass(:name) IS NOT NULL AS exists;")
        row = db.execute(sql, {"name": name}).first()
        return bool(row and row[0])

    def any_mv_exists(self, db: Session) -> bool:
        """Return True if at least one MV is present (for warmup gating)."""
        return any(self._mv_exists(db, mv) for mv in self.VIEWS)

    @staticmethod
    def _mv_has_data(db: Session, name: str) -> bool:
        """Check if MV has been populated (has at least one row)."""
        try:
            sql = text(f"SELECT 1 FROM {name} LIMIT 1;")
            row = db.execute(sql).first()
            return row is not None
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh_all(self, db: Session) -> dict[str, Any]:
        """Refresh all market MVs. Safe to call periodically.

        Uses autocommit isolation (Postgres requirement for MV refresh).
        For empty MVs (created WITH NO DATA), uses non-concurrent refresh
        since CONCURRENTLY requires at least one prior population.
        """
        refreshed: list[str] = []
        errors: list[str] = []
        raw_conn = db.get_bind().connect()
        try:
            auto_conn = raw_conn.execution_options(isolation_level="AUTOCOMMIT")
            for mv in self.VIEWS:
                try:
                    if not self._mv_exists(db, mv):
                        logger.info("MV %s does not exist, skipping refresh", mv)
                        continue

                    if self._mv_has_data(db, mv):
                        auto_conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv};"))
                    else:
                        logger.info("MV %s is empty, using non-concurrent refresh", mv)
                        auto_conn.execute(text(f"REFRESH MATERIALIZED VIEW {mv};"))
                    refreshed.append(mv)
                except Exception as e:
                    logger.warning("Failed to refresh MV %s: %s", mv, e)
                    errors.append(f"{mv}: {e}")
        finally:
            raw_conn.close()

        try:
            _redis().set(
                "mv:last_refresh",
                datetime.now(UTC).isoformat(),
                ex=86400,
            )
        except Exception:
            pass

        return {"refreshed": refreshed, "errors": errors}

    # ------------------------------------------------------------------
    # Breadth series (% above SMA50 / SMA200 per day)
    # ------------------------------------------------------------------

    def get_breadth_series(
        self,
        db: Session,
        days: int = 120,
        *,
        skip_cache: bool = False,
    ) -> list[dict[str, Any]]:
        """Return daily breadth data. Uses Redis -> MV -> raw table."""
        if not skip_cache:
            cached = self._get_cached(_BREADTH_CACHE_KEY)
            if cached is not None:
                return cached

        if self._mv_exists(db, "mv_breadth_daily"):
            series = self._query_mv_breadth(db, days)
        else:
            series = self._query_raw_breadth(db, days)

        self._set_cached(_BREADTH_CACHE_KEY, series, _BREADTH_CACHE_TTL)
        return series

    def _query_mv_breadth(self, db: Session, days: int) -> list[dict[str, Any]]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).date()
        rows = db.execute(
            text(
                "SELECT dt, above_50, above_200, total "
                "FROM mv_breadth_daily "
                "WHERE dt >= :cutoff ORDER BY dt ASC"
            ),
            {"cutoff": cutoff},
        ).fetchall()
        return [
            {
                "date": str(r[0]),
                "above_sma50_pct": round(r[1] / r[3] * 100, 1) if r[3] else 0,
                "above_sma200_pct": round(r[2] / r[3] * 100, 1) if r[3] else 0,
                "total": r[3],
            }
            for r in rows
        ]

    def _query_raw_breadth(self, db: Session, days: int) -> list[dict[str, Any]]:
        """Fallback: direct query on market_snapshot_history (full universe)."""
        cutoff_date = (datetime.now(UTC) - timedelta(days=days)).date()
        stmt = (
            select(
                MarketSnapshotHistory.as_of_date,
                func.count()
                .filter(
                    and_(
                        MarketSnapshotHistory.sma_50.isnot(None),
                        MarketSnapshotHistory.current_price > MarketSnapshotHistory.sma_50,
                    )
                )
                .label("above_50"),
                func.count()
                .filter(
                    and_(
                        MarketSnapshotHistory.sma_200.isnot(None),
                        MarketSnapshotHistory.current_price > MarketSnapshotHistory.sma_200,
                    )
                )
                .label("above_200"),
                func.count().label("total"),
            )
            .where(
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
                MarketSnapshotHistory.as_of_date >= cutoff_date,
            )
            .group_by(MarketSnapshotHistory.as_of_date)
            .order_by(MarketSnapshotHistory.as_of_date.asc())
        )
        rows = db.execute(stmt).all()
        return [
            {
                "date": str(row[0]),
                "above_sma50_pct": round(int(row[1]) / int(row[3]) * 100, 1) if int(row[3]) else 0,
                "above_sma200_pct": round(int(row[2]) / int(row[3]) * 100, 1) if int(row[3]) else 0,
                "total": int(row[3]),
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Stage distribution (daily stage counts)
    # ------------------------------------------------------------------

    def get_stage_distribution(
        self,
        db: Session,
        days: int = 120,
        *,
        skip_cache: bool = False,
    ) -> list[dict[str, Any]]:
        if not skip_cache:
            cached = self._get_cached(_STAGE_DIST_CACHE_KEY)
            if cached is not None:
                return cached

        if self._mv_exists(db, "mv_stage_distribution"):
            data = self._query_mv_stage_dist(db, days)
        else:
            data = self._query_raw_stage_dist(db, days)

        self._set_cached(_STAGE_DIST_CACHE_KEY, data, _STAGE_DIST_CACHE_TTL)
        return data

    def _query_mv_stage_dist(self, db: Session, days: int) -> list[dict[str, Any]]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).date()
        rows = db.execute(
            text(
                "SELECT dt, stage_label, cnt "
                "FROM mv_stage_distribution "
                "WHERE dt >= :cutoff ORDER BY dt ASC, stage_label ASC"
            ),
            {"cutoff": cutoff},
        ).fetchall()
        return [{"date": str(r[0]), "stage_label": r[1], "count": r[2]} for r in rows]

    def _query_raw_stage_dist(self, db: Session, days: int) -> list[dict[str, Any]]:
        """Fallback: direct query on market_snapshot_history."""
        cutoff_date = (datetime.now(UTC) - timedelta(days=days)).date()
        stmt = (
            select(
                MarketSnapshotHistory.as_of_date,
                MarketSnapshotHistory.stage_label,
                func.count().label("cnt"),
            )
            .where(
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
                MarketSnapshotHistory.as_of_date >= cutoff_date,
            )
            .group_by(
                MarketSnapshotHistory.as_of_date,
                MarketSnapshotHistory.stage_label,
            )
            .order_by(
                MarketSnapshotHistory.as_of_date.asc(),
                MarketSnapshotHistory.stage_label.asc(),
            )
        )
        rows = db.execute(stmt).all()
        return [{"date": str(r[0]), "stage_label": r[1], "count": r[2]} for r in rows]

    # ------------------------------------------------------------------
    # Sector performance
    # ------------------------------------------------------------------

    def get_sector_performance(
        self,
        db: Session,
        *,
        skip_cache: bool = False,
    ) -> list[dict[str, Any]]:
        if not skip_cache:
            cached = self._get_cached(_SECTOR_PERF_CACHE_KEY)
            if cached is not None:
                return cached

        if self._mv_exists(db, "mv_sector_performance"):
            data = self._query_mv_sector_perf(db)
        else:
            data = self._query_raw_sector_perf(db)

        self._set_cached(_SECTOR_PERF_CACHE_KEY, data, _SECTOR_PERF_CACHE_TTL)
        return data

    def _query_mv_sector_perf(self, db: Session) -> list[dict[str, Any]]:
        rows = db.execute(
            text(
                "SELECT sector, avg_perf_20d, avg_rs, cnt "
                "FROM mv_sector_performance ORDER BY avg_perf_20d DESC"
            )
        ).fetchall()
        return [
            {
                "sector": r[0],
                "avg_perf_20d": round(float(r[1]), 2) if r[1] else None,
                "avg_rs_mansfield_pct": round(float(r[2]), 2) if r[2] else None,
                "count": r[3],
            }
            for r in rows
        ]

    def _query_raw_sector_perf(self, db: Session) -> list[dict[str, Any]]:
        """Fallback: direct query on market_snapshot (latest only)."""
        stmt = (
            select(
                MarketSnapshot.sector,
                func.avg(MarketSnapshot.perf_20d).label("avg_perf_20d"),
                func.avg(MarketSnapshot.rs_mansfield_pct).label("avg_rs"),
                func.count().label("cnt"),
            )
            .where(
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.sector.isnot(None),
            )
            .group_by(MarketSnapshot.sector)
            .order_by(func.avg(MarketSnapshot.perf_20d).desc())
        )
        rows = db.execute(stmt).all()
        return [
            {
                "sector": r[0],
                "avg_perf_20d": round(float(r[1]), 2) if r[1] else None,
                "avg_rs_mansfield_pct": round(float(r[2]), 2) if r[2] else None,
                "count": r[3],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Redis cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_cached(key: str) -> Any | None:
        try:
            raw = _redis().get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    @staticmethod
    def _set_cached(key: str, data: Any, ttl: int) -> None:
        try:
            _redis().setex(key, ttl, json.dumps(data, default=str))
        except Exception as e:
            logger.warning("Failed to cache %s: %s", key, e)


market_mv_service = MarketMVService()
