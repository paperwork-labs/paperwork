"""Benchmark history backfill for portfolio regression beta.

The :class:`PortfolioAnalyticsService` computes a portfolio-vs-SPY regression
beta by aligning :class:`PortfolioSnapshot.total_value` daily returns with
:class:`MarketSnapshotHistory` rows for ``SPY`` (fallback ``^GSPC``). If the
nightly market-data pipeline is still warming up — or SPY has drifted out of
the tracked universe — this task guarantees the benchmark series is fresh
enough to support the regression.

Idempotent fast path: when today's SPY row already exists in
``market_snapshot_history`` (see :data:`BENCHMARK_ANALYSIS_TYPE`), the task
exits immediately with
``status="skipped_fast_path"``. The real work only runs when coverage is
actually missing, so scheduling this daily is cheap.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from celery import shared_task

from app.database import SessionLocal
from app.models.market_data import MarketSnapshotHistory, PriceData
from app.services.silver.market.snapshot_history_writer import upsert_snapshot_history_row
from app.services.silver.portfolio.analytics import BENCHMARK_ANALYSIS_TYPE
from app.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)

# Iron law: ``time_limit`` matches ``job_catalog.timeout_s`` (300s for this
# task). ``soft_time_limit`` leaves a 30s graceful-shutdown window.
_SOFT_TIME_LIMIT: int = 270
_HARD_TIME_LIMIT: int = 300

# Default lookback when the table is empty — enough to support the
# ``MIN_RETURNS_FOR_BETA`` threshold in the analytics service plus a buffer.
_DEFAULT_LOOKBACK_DAYS: int = 365

# Primary + fallback benchmark symbols. Mirrors the analytics service so the
# two stay aligned without a cross-import.
_BENCHMARKS: tuple[str, ...] = ("SPY", "^GSPC")


def _latest_history_date(session, symbol: str) -> datetime | None:
    row = (
        session.query(MarketSnapshotHistory.as_of_date)
        .filter(
            MarketSnapshotHistory.symbol == symbol,
            MarketSnapshotHistory.analysis_type == BENCHMARK_ANALYSIS_TYPE,
        )
        .order_by(MarketSnapshotHistory.as_of_date.desc())
        .first()
    )
    return row[0] if row else None


def _today_utc_naive() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day)


@shared_task(
    soft_time_limit=_SOFT_TIME_LIMIT,
    time_limit=_HARD_TIME_LIMIT,
)
@task_run("market_benchmark_spy_history_backfill")
def backfill_spy_history(lookback_days: int = _DEFAULT_LOOKBACK_DAYS) -> Dict[str, Any]:
    """Ensure ``market_snapshot_history`` has daily SPY coverage for the last
    ``lookback_days`` days. When today's row already exists, exits fast.

    Returns a structured counter dict so the Celery beat log surfaces
    exactly how many rows were written / skipped / errored (no-silent-fallback).
    """
    session = SessionLocal()
    written = 0
    skipped = 0
    errors = 0
    chosen_symbol: str | None = None
    try:
        today = _today_utc_naive()
        cutoff = today - timedelta(days=lookback_days)

        # Fast path — if SPY already has a row for today, nothing to do.
        spy_latest = _latest_history_date(session, "SPY")
        if spy_latest is not None and spy_latest >= today:
            logger.info("backfill_spy_history: SPY up-to-date (%s); no-op", spy_latest.date())
            return {
                "status": "skipped_fast_path",
                "symbol": "SPY",
                "written": 0,
                "skipped": 0,
                "errors": 0,
                "latest": spy_latest.isoformat(),
            }

        # Resolve which benchmark we can backfill from ``price_data``.
        for symbol in _BENCHMARKS:
            exists = (
                session.query(PriceData.id)
                .filter(PriceData.symbol == symbol, PriceData.interval == "1d")
                .first()
            )
            if exists is not None:
                chosen_symbol = symbol
                break

        if chosen_symbol is None:
            logger.warning(
                "backfill_spy_history: no daily price_data rows for %s — "
                "cannot backfill benchmark history",
                "/".join(_BENCHMARKS),
            )
            return {
                "status": "no_source_data",
                "symbol": None,
                "written": 0,
                "skipped": 0,
                "errors": 0,
            }

        # Materialize to a list: ``yield_per`` streaming + ``session.commit()``
        # inside the same iteration can close the server-side cursor/transaction
        # mid-loop and truncate the backfill. A full year of daily bars is
        # a small, bounded in-memory set.
        rows = (
            session.query(PriceData)
            .filter(
                PriceData.symbol == chosen_symbol,
                PriceData.interval == "1d",
                PriceData.date >= cutoff,
            )
            .order_by(PriceData.date.asc())
            .all()
        )

        for row in rows:
            try:
                as_of = row.date
                if hasattr(as_of, "date"):
                    as_of = datetime(as_of.year, as_of.month, as_of.day)
                close = float(row.close_price) if row.close_price is not None else None
                if close is None or close <= 0:
                    skipped += 1
                    continue
                upsert_snapshot_history_row(
                    session,
                    symbol=chosen_symbol,
                    as_of_date=as_of,
                    snapshot={"current_price": close},
                    analysis_type=BENCHMARK_ANALYSIS_TYPE,
                )
                written += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    "backfill_spy_history: row %s failed: %s",
                    getattr(row, "date", None),
                    exc,
                )

        session.commit()
        logger.info(
            "backfill_spy_history: symbol=%s written=%d skipped=%d errors=%d",
            chosen_symbol,
            written,
            skipped,
            errors,
        )
        return {
            "status": "ok",
            "symbol": chosen_symbol,
            "written": written,
            "skipped": skipped,
            "errors": errors,
        }
    except Exception:
        session.rollback()
        logger.exception("backfill_spy_history failed")
        raise
    finally:
        session.close()
