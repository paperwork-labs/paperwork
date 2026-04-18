"""
Indicator recompute, stage metadata, and related maintenance tasks.
"""

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Set

import pandas as pd
from celery import current_task, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import func

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Position, PriceData
from backend.models.market_data import JobRun, MarketSnapshot, MarketSnapshotHistory
from backend.services.market.dataframe_utils import price_data_rows_to_dataframe
from backend.services.market.market_data_service import (
    coverage_analytics,
    snapshot_builder,
    stage_quality,
)
from backend.services.market.stage_utils import compute_stage_run_lengths
from backend.tasks.utils.task_utils import (
    _fetch_daily_for_symbols,
    _get_tracked_symbols_safe,
    _persist_daily_fetch_results,
    _set_task_status,
    setup_event_loop,
    task_run,
)
from backend.services.market.backfill_params import daily_backfill_params

logger = logging.getLogger(__name__)


def _celery_task_id_short() -> str:
    try:
        req = getattr(current_task, "request", None)
        tid = getattr(req, "id", None) if req else None
        return str(tid)[:8] if tid else "?"
    except Exception:
        return "?"


_DEFAULT_SOFT = 3500


def _spy_daily_bars_stale_vs_ref(
    latest: Optional[datetime],
    ref_date: date,
    *,
    max_trailing_sessions: int = 2,
) -> bool:
    """True if the latest SPY 1d bar is missing or more than *max_trailing_sessions* sessions behind *ref_date*."""
    if latest is None:
        return True
    if isinstance(latest, datetime):
        latest_d = latest.date()
    elif isinstance(latest, date):
        latest_d = latest
    else:
        latest_d = pd.Timestamp(latest).date()
    if latest_d > ref_date:
        return False
    sessions_after = pd.bdate_range(
        start=pd.Timestamp(latest_d) + pd.offsets.BDay(1),
        end=pd.Timestamp(ref_date),
        inclusive="both",
    )
    return len(sessions_after) > max_trailing_sessions


_DEFAULT_BENCHMARK_SYMBOL = "SPY"
_DEFAULT_HARD = 3600


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("backfill_position_metadata")
def position_metadata() -> dict:
    """Backfill Position.sector and Position.market_cap from MarketSnapshot for NULL values."""
    _set_task_status("backfill_position_metadata", "running")
    session = SessionLocal()
    try:
        from backend.models.position import Position, PositionStatus
        from backend.models.market_data import MarketSnapshot as _MS

        positions = (
            session.query(Position)
            .filter(
                Position.status == PositionStatus.OPEN,
                (Position.sector.is_(None)) | (Position.market_cap.is_(None)),
            )
            .all()
        )
        if not positions:
            res = {"status": "ok", "updated": 0, "message": "no positions need backfill"}
            _set_task_status("backfill_position_metadata", "ok", res)
            return res

        symbols = list({p.symbol.upper() for p in positions if p.symbol})
        snapshots = (
            session.query(_MS)
            .filter(
                _MS.analysis_type == "technical_snapshot",
                _MS.symbol.in_(symbols),
            )
            .all()
        )
        snap_map: dict[str, _MS] = {}
        for s in snapshots:
            sym = (s.symbol or "").upper()
            if sym and sym not in snap_map:
                snap_map[sym] = s

        updated = 0
        for p in positions:
            sym = (p.symbol or "").upper()
            snap = snap_map.get(sym)
            if not snap:
                continue
            changed = False
            if p.sector is None and getattr(snap, "sector", None):
                p.sector = snap.sector
                changed = True
            if p.market_cap is None and getattr(snap, "market_cap", None):
                p.market_cap = snap.market_cap
                changed = True
            if changed:
                updated += 1

        if updated:
            session.commit()
        res = {"status": "ok", "inspected": len(positions), "updated": updated}
        _set_task_status("backfill_position_metadata", "ok", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=3600,
    time_limit=3700,
)
@task_run("admin_indicators_recompute_universe", lock_key=lambda **_: "recompute_universe")
def recompute_universe(batch_size: int = 50, force: bool = False) -> dict:
    """Recompute indicators for the tracked universe from local DB (orchestrator only).

    When *force* is True the 4-hour freshness check is bypassed so every
    symbol is recomputed regardless of when it was last updated.
    """
    _set_task_status("admin_indicators_recompute_universe", "running")
    task_id = _celery_task_id_short()
    t0 = time.monotonic()
    logger.info("[%s] recompute_universe started (batch_size=%d)", task_id, batch_size)
    session = SessionLocal()
    try:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        try:
            stuck = (
                session.query(JobRun)
                .filter(
                    JobRun.task_name == "admin_indicators_recompute_universe",
                    JobRun.status == "running",
                    JobRun.started_at < stale_cutoff,
                )
                .all()
            )
            for j in stuck:
                j.status = "error"
                j.error = "Marked as timed out by subsequent run"
                j.finished_at = j.started_at + timedelta(seconds=3600)
            if stuck:
                session.commit()
        except SoftTimeLimitExceeded:
            raise
        except Exception as e:
            logger.warning(
                "Failed to mark stale admin_indicators_recompute_universe JobRun rows: %s",
                e,
                exc_info=True,
            )
            session.rollback()

        warnings: List[str] = []

        ref_date = datetime.now(timezone.utc).date()
        spy_latest_pre = (
            session.query(func.max(PriceData.date))
            .filter(
                PriceData.symbol == _DEFAULT_BENCHMARK_SYMBOL,
                PriceData.interval == "1d",
            )
            .scalar()
        )
        spy_freshness_refresh_attempted = False
        spy_freshness_refresh_persist_errors = 0
        if _spy_daily_bars_stale_vs_ref(spy_latest_pre, ref_date):
            spy_freshness_refresh_attempted = True
            logger.warning(
                "SPY benchmark daily data is stale or missing (latest=%s, ref_date=%s); attempting refresh",
                spy_latest_pre,
                ref_date,
            )
            loop = setup_event_loop()
            try:
                params = daily_backfill_params(days=30)
                fetched = loop.run_until_complete(
                    _fetch_daily_for_symbols(
                        symbols=[_DEFAULT_BENCHMARK_SYMBOL],
                        period=params.period,
                        max_bars=params.max_bars,
                        concurrency=1,
                    )
                )
                persist_early = _persist_daily_fetch_results(
                    session=session,
                    fetched=fetched,
                    since_dt=None,
                    use_delta_after=True,
                )
                spy_freshness_refresh_persist_errors = int(persist_early.get("errors") or 0)
                if spy_freshness_refresh_persist_errors:
                    logger.error(
                        "SPY benchmark refresh persist reported %s error(s): %s",
                        spy_freshness_refresh_persist_errors,
                        persist_early.get("error_samples"),
                    )
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.error(
                    "SPY benchmark refresh failed; RS/Stage may be inaccurate: %s",
                    e,
                    exc_info=True,
                )
            finally:
                loop.close()

        ordered = _get_tracked_symbols_safe(session)
        total_syms = len(ordered)
        logger.info("[%s] recompute_universe universe symbols=%d", task_id, total_syms)

        processed_ok = 0
        skipped_no_data = 0
        errors = 0
        error_samples: List[dict] = []

        latest_daily_dt = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.interval == "1d")
            .scalar()
        )
        bench = coverage_analytics.benchmark_health(
            session, benchmark_symbol="SPY", latest_daily_dt=latest_daily_dt
        )
        benchmark_symbol = str(bench.get("symbol") or "SPY")
        required_bars = int(bench.get("required_bars") or 0)
        benchmark_count = int(bench.get("daily_bars") or 0)
        benchmark_latest_dt = bench.get("latest_daily_dt")
        benchmark_stale = bool(bench.get("stale"))
        benchmark_fetched = False
        benchmark_errors = 0
        if benchmark_count < required_bars or benchmark_latest_dt is None or benchmark_stale:
            loop = setup_event_loop()
            try:
                params = daily_backfill_params(days=required_bars)
                fetched = loop.run_until_complete(
                    _fetch_daily_for_symbols(
                        symbols=[benchmark_symbol],
                        period=params.period,
                        max_bars=params.max_bars,
                        concurrency=1,
                    )
                )
            finally:
                loop.close()
            persist = _persist_daily_fetch_results(
                session=session,
                fetched=fetched,
                since_dt=None,
                use_delta_after=True,
            )
            benchmark_fetched = True
            benchmark_errors = int(persist.get("errors") or 0)
            bench = coverage_analytics.benchmark_health(
                session, benchmark_symbol=benchmark_symbol, latest_daily_dt=latest_daily_dt
            )
            benchmark_count = int(bench.get("daily_bars") or 0)
            benchmark_latest_dt = bench.get("latest_daily_dt")
        if benchmark_count < required_bars:
            warnings.append(
                f"Benchmark {benchmark_symbol} has {benchmark_count} daily bars (<{required_bars}); "
                "Stage/RS may be UNKNOWN until benchmark history is backfilled."
            )
        if latest_daily_dt and benchmark_latest_dt and benchmark_latest_dt.date() < latest_daily_dt.date():
            warnings.append(
                f"Benchmark {benchmark_symbol} latest date {benchmark_latest_dt.date()} "
                f"lags latest daily {latest_daily_dt.date()}; RS may be stale."
            )

        spy_latest_for_compute = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.symbol == benchmark_symbol, PriceData.interval == "1d")
            .scalar()
        )
        spy_session_lag_stale = _spy_daily_bars_stale_vs_ref(spy_latest_for_compute, ref_date)
        if spy_session_lag_stale:
            warnings.append(
                f"Benchmark {benchmark_symbol} daily data is stale or missing (latest={spy_latest_for_compute}); "
                "Mansfield RS and Weinstein stages may be UNKNOWN or inaccurate."
            )

        spy_df = None
        try:
            spy_rows = (
                session.query(
                    PriceData.date,
                    PriceData.open_price,
                    PriceData.high_price,
                    PriceData.low_price,
                    PriceData.close_price,
                    PriceData.volume,
                )
                .filter(PriceData.symbol == benchmark_symbol, PriceData.interval == "1d")
                .order_by(PriceData.date.desc())
                .limit(int(getattr(settings, "SNAPSHOT_DAILY_BARS_LIMIT", 400)))
                .all()
            )
            if spy_rows:
                spy_df = price_data_rows_to_dataframe(spy_rows, ascending=False)
        except SoftTimeLimitExceeded:
            raise
        except Exception as e:
            logger.warning("spy_benchmark_fetch failed for %s: %s", benchmark_symbol, e)

        fresh_syms: Set[str] = set()
        if force:
            logger.info("[%s] force=True — bypassing freshness check", task_id)
        else:
            fresh_cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
            try:
                fresh_syms = {
                    str(s).upper()
                    for (s,) in session.query(MarketSnapshot.symbol).filter(
                        MarketSnapshot.analysis_type == "technical_snapshot",
                        MarketSnapshot.analysis_timestamp >= fresh_cutoff,
                    )
                }
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.warning("fresh_snapshot_query failed: %s", e)
        skipped_fresh = 0

        try:
            for i in range(0, len(ordered), max(1, batch_size)):
                chunk = ordered[i : i + batch_size]
                for j, sym in enumerate(chunk):
                    idx = i + j + 1
                    if sym in fresh_syms:
                        skipped_fresh += 1
                        continue
                    try:
                        snap = snapshot_builder.compute_snapshot_from_db(
                            session,
                            sym,
                            skip_fundamentals=True,
                            benchmark_df=spy_df,
                        )
                        if not snap:
                            skipped_no_data += 1
                            continue
                        snapshot_builder.persist_snapshot(
                            session,
                            sym,
                            snap,
                            auto_commit=False,
                        )
                        processed_ok += 1
                    except SoftTimeLimitExceeded:
                        raise
                    except Exception as exc:
                        session.rollback()
                        errors += 1
                        if len(error_samples) < 25:
                            error_samples.append({"symbol": sym, "error": str(exc)})
                        logger.warning(
                            "[%s] recompute_universe failed for %s (%d/%d): %s",
                            task_id,
                            sym,
                            idx,
                            total_syms,
                            exc,
                            exc_info=True,
                        )
                try:
                    session.commit()
                except SoftTimeLimitExceeded:
                    raise
                except Exception as e:
                    batch_end = min(i + len(chunk), total_syms)
                    logger.warning(
                        "[%s] recompute_universe batch commit failed (%d-%d/%d): %s",
                        task_id,
                        i + 1,
                        batch_end,
                        total_syms,
                        e,
                        exc_info=True,
                    )
                    session.rollback()
        except SoftTimeLimitExceeded:
            try:
                session.commit()
            except Exception as e:
                logger.warning(
                    "[%s] recompute_universe partial commit after soft time limit failed: %s",
                    task_id,
                    e,
                    exc_info=True,
                )
                session.rollback()
            warnings.append(
                f"Task hit soft time limit after processing {processed_ok} of {len(ordered)} symbols. "
                "Remaining symbols were skipped."
            )
        # Coverage accounting: per `no-silent-fallback.mdc`, the sum of all
        # per-symbol outcome counters must equal the universe size. Any
        # mismatch (e.g. a code path that forgets to increment a counter)
        # surfaces here so we don't silently report partial coverage as
        # success.
        accounted = processed_ok + skipped_no_data + skipped_fresh + errors
        skipped_unprocessed = max(0, total_syms - accounted)
        coverage_consistent = (accounted + skipped_unprocessed) == total_syms

        res = {
            "status": "ok",
            "symbols": len(ordered),
            "processed_ok": processed_ok,
            "skipped_no_data": skipped_no_data,
            "skipped_fresh": skipped_fresh,
            "skipped_unprocessed": skipped_unprocessed,
            "errors": errors,
            "coverage_consistent": coverage_consistent,
            "error_samples": error_samples,
            "benchmark": {
                "symbol": benchmark_symbol,
                "required_bars": required_bars,
                "daily_bars": benchmark_count,
                "fetched": benchmark_fetched,
                "errors": benchmark_errors,
                "ok": benchmark_count >= required_bars,
                "spy_session_lag_stale": spy_session_lag_stale,
                "spy_freshness_refresh_attempted": spy_freshness_refresh_attempted,
                "spy_freshness_refresh_persist_errors": spy_freshness_refresh_persist_errors,
            },
        }
        if not coverage_consistent:
            logger.error(
                "[%s] recompute_universe counter drift: total=%d accounted=%d "
                "(processed_ok=%d skipped_no_data=%d skipped_fresh=%d errors=%d skipped_unprocessed=%d)",
                task_id,
                total_syms,
                accounted + skipped_unprocessed,
                processed_ok,
                skipped_no_data,
                skipped_fresh,
                errors,
                skipped_unprocessed,
            )
            res["status"] = "warn"
            warnings.append(
                f"counter drift: accounted={accounted + skipped_unprocessed} expected={total_syms}"
            )
        if skipped_unprocessed > 0:
            warnings.append(
                f"{skipped_unprocessed} of {total_syms} symbols were not processed "
                "(soft time limit or early exit)."
            )
        if warnings:
            res["warnings"] = warnings
        if error_samples:
            res["error"] = "Sample errors:\n" + "\n".join(
                f"- {e.get('symbol')}: {e.get('error')}" for e in error_samples
            )
        elapsed = time.monotonic() - t0
        logger.info(
            "[%s] recompute_universe completed in %.1fs "
            "(symbols=%d ok=%d skipped_nd=%d skipped_fresh=%d skipped_unprocessed=%d errors=%d coverage_consistent=%s)",
            task_id,
            elapsed,
            total_syms,
            processed_ok,
            skipped_no_data,
            skipped_fresh,
            skipped_unprocessed,
            errors,
            coverage_consistent,
        )
        _set_task_status("admin_indicators_recompute_universe", "ok", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("admin_backfill_stage_durations")
def stage_durations() -> dict:
    """Backfill stage duration fields for snapshot history + latest snapshots."""
    _set_task_status("admin_backfill_stage_durations", "running")
    session = SessionLocal()
    try:
        symbols = (
            session.query(MarketSnapshotHistory.symbol)
            .filter(MarketSnapshotHistory.analysis_type == "technical_snapshot")
            .distinct()
            .all()
        )
        symbol_list = [s[0] for s in symbols if s and s[0]]
        processed = 0
        updated_rows = 0

        for sym in symbol_list:
            rows = (
                session.query(
                    MarketSnapshotHistory.id,
                    MarketSnapshotHistory.as_of_date,
                    MarketSnapshotHistory.stage_label,
                )
                .filter(
                    MarketSnapshotHistory.symbol == sym,
                    MarketSnapshotHistory.analysis_type == "technical_snapshot",
                )
                .order_by(MarketSnapshotHistory.as_of_date.asc())
                .all()
            )
            if not rows:
                continue

            run_info = compute_stage_run_lengths([r.stage_label for r in rows])
            mappings = []
            for row, info in zip(rows, run_info):
                mappings.append(
                    {
                        "id": row.id,
                        "current_stage_days": info.get("current_stage_days"),
                        "previous_stage_label": info.get("previous_stage_label"),
                        "previous_stage_days": info.get("previous_stage_days"),
                    }
                )
            session.bulk_update_mappings(MarketSnapshotHistory, mappings)
            updated_rows += len(mappings)

            latest_info = run_info[-1] if run_info else {}
            session.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == sym,
                MarketSnapshot.analysis_type == "technical_snapshot",
            ).update(
                {
                    "current_stage_days": latest_info.get("current_stage_days"),
                    "previous_stage_label": latest_info.get("previous_stage_label"),
                    "previous_stage_days": latest_info.get("previous_stage_days"),
                },
                synchronize_session=False,
            )
            processed += 1
            if processed % 200 == 0:
                session.commit()

        session.commit()
        res = {"status": "ok", "symbols": processed, "rows_updated": updated_rows}
        _set_task_status("admin_backfill_stage_durations", "ok", res)
        return res
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        session.rollback()
        res = {"status": "error", "error": str(exc)}
        _set_task_status("admin_backfill_stage_durations", "error", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=600,
    time_limit=720,
)
@task_run("admin_stage_change_alerts")
def stage_changes() -> dict:
    """Check for stage transitions in portfolio holdings and create alerts."""
    session = SessionLocal()
    try:
        symbols = [
            r[0]
            for r in session.query(Position.symbol)
            .filter(Position.quantity != 0)
            .distinct()
            .all()
        ]
        if not symbols:
            return {"status": "ok", "alerts_created": 0, "reason": "no_positions"}

        today = datetime.now(timezone.utc).date()
        recent_dates = (
            session.query(MarketSnapshotHistory.as_of_date)
            .filter(
                MarketSnapshotHistory.as_of_date <= today,
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
            )
            .distinct()
            .order_by(MarketSnapshotHistory.as_of_date.desc())
            .limit(2)
            .all()
        )
        if len(recent_dates) < 2:
            return {
                "status": "ok",
                "alerts_created": 0,
                "reason": "insufficient_snapshot_dates",
                "symbols_checked": len(symbols),
            }

        current_date = recent_dates[0][0]
        previous_date = recent_dates[1][0]

        current_rows = (
            session.query(
                MarketSnapshotHistory.symbol, MarketSnapshotHistory.stage_label
            )
            .filter(
                MarketSnapshotHistory.symbol.in_(symbols),
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
                MarketSnapshotHistory.as_of_date == current_date,
            )
            .all()
        )
        previous_rows = (
            session.query(
                MarketSnapshotHistory.symbol, MarketSnapshotHistory.stage_label
            )
            .filter(
                MarketSnapshotHistory.symbol.in_(symbols),
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
                MarketSnapshotHistory.as_of_date == previous_date,
            )
            .all()
        )

        current_map = {r[0]: r[1] for r in current_rows}
        previous_map = {r[0]: r[1] for r in previous_rows}

        changes = []
        for sym in symbols:
            cur_stage = current_map.get(sym)
            prev_stage = previous_map.get(sym)
            if cur_stage and prev_stage and cur_stage != prev_stage:
                changes.append(
                    {"symbol": sym, "from_stage": prev_stage, "to_stage": cur_stage}
                )

        if changes:
            try:
                from backend.services.notifications.alerts import alert_service

                fields = {
                    c["symbol"]: f'{c["from_stage"]} → {c["to_stage"]}'
                    for c in changes[:25]
                }
                alert_service.send_alert(
                    "portfolio_stage_change",
                    title="Portfolio Stage Changes",
                    description=(
                        f"{len(changes)} held symbol(s) changed stage between "
                        f"{previous_date.isoformat()} and {current_date.isoformat()}."
                    ),
                    fields=fields,
                    severity="warning",
                )
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.warning("stage_change_ops_alert failed: %s", e)

        return {
            "status": "ok",
            "symbols_checked": len(symbols),
            "changes": changes,
            "alerts_created": len(changes),
        }
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        session.close()


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("admin_repair_stage_history")
def repair_stage_history(days: int = 120) -> dict:
    """Walk MarketSnapshotHistory and repair current_stage_days monotonicity.

    The ``days`` parameter is the number of most recent snapshot history rows
    per symbol to inspect (trading days, not calendar days).  120 rows covers
    roughly 6 months of trading history.
    """
    _set_task_status("admin_repair_stage_history", "running", {"days": days})
    session = SessionLocal()
    try:
        result = stage_quality.repair_stage_history_window(session, days=days)
        _set_task_status("admin_repair_stage_history", "ok", result)
        return result
    except Exception as exc:
        _set_task_status("admin_repair_stage_history", "error", {"error": str(exc)})
        return {"status": "error", "error": str(exc)}
    finally:
        session.close()
