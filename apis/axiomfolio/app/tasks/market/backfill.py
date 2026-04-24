"""
Daily bar backfill, index constituents, and tracked-universe cache tasks.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

from celery import current_task, shared_task
from celery.exceptions import SoftTimeLimitExceeded

from app.database import SessionLocal
from app.models import IndexConstituent
from app.services.silver.math.backfill_params import daily_backfill_params
from app.services.market.universe import TRACKED_ALL_UPDATED_AT_KEY
from app.services.market.market_data_service import (
    coverage_analytics,
    index_universe,
    infra,
    snapshot_builder,
)
from app.tasks.utils.task_utils import (
    _daily_backfill_concurrency,
    _fetch_daily_for_symbols,
    _get_tracked_symbols_safe,
    _get_tracked_universe_from_db,
    _persist_daily_fetch_results,
    _set_task_status,
    setup_event_loop,
    task_run,
)

logger = logging.getLogger(__name__)


def _celery_task_id_short() -> str:
    try:
        req = getattr(current_task, "request", None)
        tid = getattr(req, "id", None) if req else None
        return str(tid)[:8] if tid else "?"
    except Exception:
        return "?"


_DEFAULT_SOFT = 3500
_DEFAULT_HARD = 3600


@shared_task(
    soft_time_limit=600,
    time_limit=720,
)
@task_run("market_symbol_refresh", lock_key=lambda symbol: str(symbol).upper() if symbol else None)
def symbol(symbol: str) -> dict:
    """Delta backfill and recompute indicators for a single symbol."""
    if not symbol:
        return {"status": "error", "error": "symbol required"}
    sym = str(symbol).upper()
    _set_task_status("market_symbol_refresh", "running", {"symbol": sym})
    session = SessionLocal()
    try:
        symbols([sym])
        snap = snapshot_builder.compute_snapshot_from_db(session, sym)
        if snap:
            snapshot_builder.persist_snapshot(session, sym, snap)
            res = {"status": "ok", "symbol": sym, "recomputed": True}
        else:
            res = {"status": "ok", "symbol": sym, "recomputed": False}
        _set_task_status("market_symbol_refresh", "ok", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=110,
    time_limit=120,
)
@task_run("market_universe_tracked_refresh")
def tracked_cache() -> dict:
    """Compute union of tracked symbols and publish to Redis."""
    _set_task_status("market_universe_tracked_refresh", "running")
    session = SessionLocal()
    try:
        redis = infra.redis_client
        current = sorted(_get_tracked_universe_from_db(session))
        if not current:
            loop = None
            try:
                loop = setup_event_loop()
                index_to_symbols: dict[str, set[str]] = {
                    "SP500": set(),
                    "NASDAQ100": set(),
                    "DOW30": set(),
                    "RUSSELL2000": set(),
                }
                for idx in ["SP500", "NASDAQ100", "DOW30", "RUSSELL2000"]:
                    try:
                        cons = loop.run_until_complete(
                            index_universe.get_index_constituents(idx)
                        )
                        index_to_symbols[idx].update({s.upper() for s in cons if s})
                    except SoftTimeLimitExceeded:
                        raise
                    except Exception as e:
                        logger.warning(
                            "tracked_cache: get_index_constituents failed for %s: %s",
                            idx,
                            e,
                        )
                        continue
                seed_syms: set[str] = set().union(*index_to_symbols.values())
                if seed_syms:
                    for idx, syms in index_to_symbols.items():
                        for sym in syms:
                            session.add(
                                IndexConstituent(
                                    index_name=idx, symbol=sym, is_active=True
                                )
                            )
                    session.commit()
                    current = sorted(seed_syms)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.warning("index_seed_from_providers failed: %s", e)
            finally:
                if loop:
                    loop.close()
        prev_raw = None
        try:
            prev_raw = redis.get("tracked:all")
        except Exception as e:
            logger.warning("tracked_cache: Redis get tracked:all failed: %s", e)
        prev = []
        if prev_raw:
            try:
                prev = json.loads(prev_raw)
            except Exception as e:
                logger.warning(
                    "tracked:all JSON parse failed, treating as empty: %s",
                    e,
                )
                prev = []
        prev_set = set(s.upper() for s in prev)
        additions = [s for s in current if s not in prev_set]
        try:
            redis.set("tracked:all", json.dumps(current))
            redis.set(TRACKED_ALL_UPDATED_AT_KEY, str(time.time()))
            redis.setex("tracked:new", 24 * 3600, json.dumps(additions))
        except Exception as e:
            logger.warning("tracked_cache: Redis write failed: %s", e)
        res = {"status": "ok", "tracked_all": len(current), "new": len(additions)}
        _set_task_status("market_universe_tracked_refresh", "ok", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("admin_backfill_daily_symbols")
def symbols(
    symbols: List[str],
    days: int = 200,
    min_bars: Optional[int] = None,
    buffer_bars: Optional[int] = None,
    skip_l2: bool = False,
) -> dict:
    """Delta backfill daily bars for a provided symbol list."""
    session = SessionLocal()
    try:
        loop = setup_event_loop()
        try:
            concurrency = _daily_backfill_concurrency()
            params_kw: dict = {"days": days}
            if min_bars is not None:
                params_kw["min_bars"] = min_bars
            if buffer_bars is not None:
                params_kw["buffer_bars"] = buffer_bars
            params = daily_backfill_params(**params_kw)
            fetched = loop.run_until_complete(
                _fetch_daily_for_symbols(
                    symbols=[s.upper() for s in (symbols or []) if s],
                    period=params.period,
                    max_bars=params.max_bars,
                    concurrency=concurrency,
                    skip_l2=skip_l2,
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

        return {
            "status": "ok",
            "days": int(days),
            "period": params.period,
            "max_bars": params.max_bars,
            "symbols": len(symbols or []),
            "processed": persist["processed_ok"],
            "updated_total": persist["updated_total"],
            "up_to_date_total": persist["up_to_date_total"],
            "skipped_empty": persist["skipped_empty"],
            "rows_attempted": persist["bars_inserted_total"],
            "errors": persist["errors"],
            "error_samples": persist["error_samples"],
            "provider_usage": persist["provider_usage"],
        }
    finally:
        session.close()


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("admin_backfill_daily")
def daily_bars(days: int = 200) -> dict:
    """Delta backfill last N trading days (approx) of daily bars for the tracked universe."""
    try:
        _set_task_status("admin_backfill_daily", "running", {"days": int(days)})
        session = SessionLocal()
        try:
            universe = _get_tracked_universe_from_db(session)
            tracked_total = len(universe)
        finally:
            session.close()

        result = symbols(list(universe), days=days)
        result["tracked_total"] = tracked_total
        _set_task_status("admin_backfill_daily", "ok", result)
        return result
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_backfill_daily")
        raise


@shared_task(
    soft_time_limit=280,
    time_limit=300,
)
@task_run("market_indices_constituents_refresh")
def constituents(index: str | None = None) -> dict:
    """Refresh index constituents for major US indices.
    
    Args:
        index: Optional specific index to refresh. One of: SP500, NASDAQ100,
               DOW30, RUSSELL2000, or "all". If None or "all", refreshes all indices.
    """
    _set_task_status("market_indices_constituents_refresh", "running")
    loop = setup_event_loop()
    results = {}
    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        from app.config import settings as _settings

        preflight = {
            "has_fmp_key": bool(getattr(_settings, "FMP_API_KEY", "")),
        }
        all_indices = ["SP500", "NASDAQ100", "DOW30", "RUSSELL2000"]
        indices_to_refresh = all_indices
        if index and index.upper() != "ALL":
            idx_upper = index.upper()
            if idx_upper in all_indices:
                indices_to_refresh = [idx_upper]
            else:
                _set_task_status("market_indices_constituents_refresh", "error")
                return {
                    "error": f"Unknown index: {index}. Valid: {', '.join(all_indices)} or 'all'",
                    "preflight": preflight,
                }
        for idx in indices_to_refresh:
            try:
                symbols = set(
                    loop.run_until_complete(index_universe.get_index_constituents(idx))
                )
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                results[idx] = {"error": str(e)}
                continue
            if not symbols:
                active_count = (
                    session.query(IndexConstituent)
                    .filter(IndexConstituent.index_name == idx, IndexConstituent.is_active.is_(True))
                    .count()
                )
                logger.warning(
                    "constituents: %s returned 0 symbols — skipping deactivation (%d active rows preserved)",
                    idx, active_count,
                )
                results[idx] = {
                    "fetched": 0,
                    "skipped": True,
                    "reason": "0 symbols returned; not deactivating existing rows",
                    "existing_active": active_count,
                }
                continue
            provider_used = "unknown"
            fallback_used = None
            try:
                meta_raw = infra.redis_client.get(f"index_constituents:{idx}:meta")
                if meta_raw:
                    meta = json.loads(meta_raw)
                    provider_used = meta.get("provider_used", provider_used)
                    fallback_used = meta.get("fallback_used", False)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.warning("redis_meta_read failed for %s: %s", idx, e)
            existing_rows = (
                session.query(IndexConstituent)
                .filter(IndexConstituent.index_name == idx)
                .all()
            )
            existing_map = {r.symbol: r for r in existing_rows}
            inserted = 0
            updated_active = 0
            for sym in symbols:
                row = existing_map.get(sym)
                if row:
                    if not row.is_active:
                        row.is_active = True
                        row.became_inactive_at = None
                        updated_active += 1
                    row.last_refreshed_at = now
                else:
                    session.add(
                        IndexConstituent(index_name=idx, symbol=sym, is_active=True)
                    )
                    inserted += 1
            inactivated = 0
            for sym, row in existing_map.items():
                if sym not in symbols and row.is_active:
                    row.is_active = False
                    row.became_inactive_at = now
                    row.last_refreshed_at = now
                    inactivated += 1
            session.commit()
            results[idx] = {
                "fetched": len(symbols),
                "inserted": inserted,
                "reactivated": updated_active,
                "inactivated": inactivated,
                "provider_used": provider_used,
                "fallback_used": fallback_used,
            }
        min_expected = {"SP500": 400, "NASDAQ100": 90, "DOW30": 25, "RUSSELL2000": 1500}
        warnings = []
        for idx_name, expected in min_expected.items():
            idx_result = results.get(idx_name, {})
            fetched = idx_result.get("fetched", 0)
            if fetched < expected:
                warnings.append(f"{idx_name}: only {fetched} constituents (expected >= {expected})")
            if idx_result.get("error"):
                warnings.append(f"{idx_name}: error - {idx_result['error']}")

        if warnings:
            try:
                from app.services.notifications.alerts import alert_service

                alert_service.send_alert(
                    "system_status",
                    title="Index Constituents Health Check Warning",
                    description="One or more indices have low/missing constituent counts after refresh.",
                    fields={w.split(":")[0]: w for w in warnings},
                    severity="warning",
                )
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.warning("ops_alert for constituents health check failed: %s", e)
            logger.warning("Index constituents health check: %s", "; ".join(warnings))

        res = {"status": "ok", "preflight": preflight, "indices": results, "health_warnings": warnings}
        _set_task_status("market_indices_constituents_refresh", "ok", res)
        return res
    finally:
        session.close()
        loop.close()


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run(
    "admin_backfill_daily_since_date",
    lock_key=lambda since_date="", batch_size=25, index=None: f"daily_since:{(index or 'all').upper()}",
)
def daily_since(since_date: str = "", batch_size: int = 25, index: Optional[str] = None) -> dict:
    """Deep backfill of daily bars since a given date.

    Args:
        since_date: YYYY-MM-DD start date (defaults to HISTORY_TARGET_YEARS ago).
        batch_size: Unused legacy param kept for API compat.
        index: Optional index filter — DOW30, NASDAQ100, SP500, RUSSELL2000.
               When provided, only backfills that index's active constituents.
    """
    from app.config import settings as _cfg
    if not _cfg.ALLOW_DEEP_BACKFILL or not _cfg.provider_policy.deep_backfill_allowed:
        logger.warning("daily_since blocked: ALLOW_DEEP_BACKFILL=False or policy disallows")
        return {"status": "blocked", "reason": "ALLOW_DEEP_BACKFILL is disabled or policy disallows deep backfill"}

    if not since_date:
        from datetime import timedelta

        since_date = (
            datetime.now(timezone.utc).date()
            - timedelta(days=_cfg.HISTORY_TARGET_YEARS * 365)
        ).isoformat()

    _VALID_INDICES = {"DOW30", "NASDAQ100", "SP500", "RUSSELL2000"}
    idx_upper = index.upper() if index else None
    if idx_upper and idx_upper not in _VALID_INDICES:
        raise ValueError(f"Unknown index: {index!r}. Valid: {', '.join(sorted(_VALID_INDICES))}")

    _set_task_status("admin_backfill_daily_since_date", "running", {
        "since_date": since_date, "index": idx_upper,
    })
    session = SessionLocal()
    try:
        task_id = _celery_task_id_short()
        t0 = time.monotonic()

        import pandas as pd

        since_dt = pd.to_datetime(since_date, utc=True, errors="coerce")
        if since_dt is None or pd.isna(since_dt):
            raise ValueError(f"Invalid since_date: {since_date!r}")
        since_dt = since_dt.tz_convert(None).normalize()

        if idx_upper:
            symbols = sorted({
                ic.symbol for ic in session.query(IndexConstituent)
                .filter(
                    IndexConstituent.index_name == idx_upper,
                    IndexConstituent.is_active.is_(True),
                ).all()
            })
            if not symbols:
                raise ValueError(f"No active constituents for index {idx_upper}")
        else:
            symbols = _get_tracked_symbols_safe(session)

        logger.info(
            "[%s] daily_since started since=%s index=%s symbols=%d",
            task_id,
            since_date,
            idx_upper or "all",
            len(symbols),
        )

        max_bars = 7500  # cap at ~30 years of daily bars
        loop = setup_event_loop()
        try:
            concurrency = _daily_backfill_concurrency()
            fetched = loop.run_until_complete(
                _fetch_daily_for_symbols(
                    symbols=symbols,
                    period="max",
                    max_bars=max_bars,
                    concurrency=concurrency,
                    skip_l2=True,
                )
            )
        finally:
            loop.close()

        n_fetch = len(fetched or [])
        for k, item in enumerate(fetched or [], 1):
            sym = item.get("symbol") or "?"
            prov = item.get("provider") or "unknown"
            df = item.get("df")
            bars = 0
            if df is not None and not getattr(df, "empty", True):
                bars = int(len(df))
            logger.debug(
                "[%s] daily_since fetched %s (%d/%d) provider=%s bars=%d",
                task_id,
                sym,
                k,
                n_fetch,
                prov,
                bars,
            )

        persist = _persist_daily_fetch_results(
            session=session,
            fetched=fetched,
            since_dt=since_dt,
            use_delta_after=False,
        )
        res = {
            "status": "ok" if persist["errors"] == 0 else "error",
            "since_date": since_date,
            "index": idx_upper,
            "symbols": len(symbols),
            "processed_symbols": persist["processed_ok"],
            "bars_attempted_total": persist["bars_attempted_total"],
            "bars_inserted_total": persist["bars_inserted_total"],
            "errors": persist["errors"],
            "error_samples": persist["error_samples"],
            "provider_usage": persist["provider_usage"],
        }
        _set_task_status(
            "admin_backfill_daily_since_date",
            "ok" if persist["errors"] == 0 else "error",
            res,
        )
        elapsed = time.monotonic() - t0
        logger.info(
            "[%s] daily_since completed in %.1fs (symbols=%d processed=%d errors=%d bars_inserted=%d)",
            task_id,
            elapsed,
            len(symbols),
            int(persist.get("processed_ok") or 0),
            int(persist.get("errors") or 0),
            int(persist.get("bars_inserted_total") or 0),
        )
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=10800,
    time_limit=14400,
)
@task_run("admin_backfill_since_date", lock_key=lambda since_date, **_: f"admin_backfill_since_date:{since_date}", lock_ttl_seconds=14700)
def full_historical(
    since_date: Optional[str] = None,
    daily_batch_size: int = 25,
    history_batch_size: int = 50,
) -> dict:
    """Deep backfill pipeline since a given date (daily, indicators, history, coverage).

    Defaults to HISTORY_TARGET_YEARS (10yr) when since_date is not provided.
    This is a one-time operation; the nightly pipeline handles daily deltas.
    """
    from app.config import settings as _settings

    if not _settings.ALLOW_DEEP_BACKFILL or not _settings.provider_policy.deep_backfill_allowed:
        logger.warning("full_historical blocked: ALLOW_DEEP_BACKFILL=False or policy disallows")
        return {"status": "blocked", "reason": "ALLOW_DEEP_BACKFILL is disabled or policy disallows deep backfill"}

    if not since_date:
        from datetime import timedelta

        since_date = (
            datetime.now(timezone.utc).date()
            - timedelta(days=_settings.HISTORY_TARGET_YEARS * 365)
        ).isoformat()
    from app.tasks.market.history import snapshot_last_n_days
    from app.tasks.market.indicators import recompute_universe

    def _summarize(step: str, payload: Optional[dict]) -> str:
        data = payload or {}
        if step == "admin_backfill_daily_since_date":
            return f"Daily since {data.get('since_date', '?')}: {data.get('bars_inserted_total', 0)} bars"
        if step == "admin_indicators_recompute_universe":
            return f"Recomputed {data.get('processed', data.get('symbols', 0))} / {data.get('symbols', 0)}"
        if step == "admin_snapshots_history_backfill":
            return (
                f"Snapshot history: {data.get('processed_symbols', 0)} syms, "
                f"{data.get('written_rows', 0)} rows"
            )
        if step == "admin_coverage_refresh":
            return f"Coverage: {data.get('daily_pct', 0)}% daily; stale={data.get('stale_daily', 0)}"
        return data.get("status", "ok")

    rollup: dict = {"steps": [], "since_date": since_date}

    def _append(step_name: str, result: dict) -> None:
        rollup["steps"].append(
            {
                "name": step_name,
                "summary": _summarize(step_name, result),
                "result": result,
            }
        )

    _set_task_status("admin_backfill_since_date", "running", {"since_date": since_date})

    res1 = daily_since(since_date=since_date, batch_size=int(daily_batch_size))
    if res1.get("status") == "skipped":
        logger.warning(
            "daily_since was skipped (locked by another task), data may not be refreshed"
        )
        rollup["daily_since_skipped"] = True
    _append("admin_backfill_daily_since_date", res1)

    res2 = recompute_universe(batch_size=50)
    _append("admin_indicators_recompute_universe", res2)

    try:
        res3 = snapshot_last_n_days(
            days=3000, since_date=since_date, batch_size=int(history_batch_size)
        )
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        res3 = {"status": "error", "error": str(exc)}
    _append("admin_snapshots_history_backfill", res3)

    from app.tasks.market.coverage import health_check

    res4 = health_check()
    _append("admin_coverage_refresh", res4)

    def _rollup_step_ok(step: dict) -> bool:
        res = step.get("result") or {}
        st = res.get("status")
        if st in (None, "ok"):
            return True
        if st == "skipped" and step.get("name") == "admin_backfill_daily_since_date":
            return True
        return False

    rollup["status"] = (
        "ok" if all(_rollup_step_ok(s) for s in rollup["steps"]) else "error"
    )
    rollup["overall_summary"] = "; ".join(
        step["summary"] for step in rollup["steps"] if step.get("summary")
    )
    _set_task_status("admin_backfill_since_date", rollup["status"], rollup)
    return rollup


@shared_task(
    soft_time_limit=7000,
    time_limit=7200,
)
@task_run("admin_coverage_backfill_stale", lock_key=lambda: "admin_coverage_backfill_stale", lock_ttl_seconds=7500)
def stale_daily() -> dict:
    """Backfill daily bars for stale/missing symbols in the tracked universe."""
    _set_task_status("admin_coverage_backfill_stale", "running")
    session = SessionLocal()
    try:
        tracked = _get_tracked_symbols_safe(session)
        section, stale_full = coverage_analytics._compute_interval_coverage_for_symbols(
            session,
            symbols=tracked,
            interval="1d",
            now_utc=datetime.now(timezone.utc),
            return_full_stale=True,
        )
        stale_symbols = stale_full or []

        if not stale_symbols:
            res = {
                "status": "ok",
                "tracked_total": len(tracked),
                "stale_candidates": 0,
                "note": "No stale/missing daily symbols detected",
                "daily": {
                    "freshness": section.get("freshness"),
                    "stale_48h": section.get("stale_48h"),
                    "missing": section.get("missing"),
                },
            }
            _set_task_status("admin_coverage_backfill_stale", "ok", res)
            return res

        backfill_res = symbols(stale_symbols, days=10, min_bars=15, buffer_bars=5, skip_l2=True)
        from app.tasks.market.coverage import health_check

        monitor_res = health_check()
        res = {
            "status": "ok",
            "tracked_total": len(tracked),
            "stale_candidates": len(stale_symbols),
            "backfill": backfill_res,
            "monitor": monitor_res,
        }
        _set_task_status("admin_coverage_backfill_stale", "ok", res)
        return res
    finally:
        session.close()


@shared_task(
    soft_time_limit=18000,
    time_limit=21600,
)
@task_run(
    "admin_recompute_since_date",
    lock_key=lambda since_date=None, **_: "admin_recompute_since_date",
    lock_ttl_seconds=21900,
)
def safe_recompute(
    since_date: Optional[str] = None,
    batch_size: int = 50,
    history_batch_size: int = 25,
) -> dict:
    """Recompute indicators + rebuild snapshot history from existing DB data.

    This avoids the bulk daily-bar download step of full_historical.
    Note: recompute_universe may fetch a small number of benchmark (SPY) bars
    if they are stale — this is a negligible API cost compared to a full backfill.
    """
    from app.tasks.market.history import snapshot_last_n_days
    from app.tasks.market.indicators import recompute_universe

    _set_task_status("admin_recompute_since_date", "running")

    rollup: dict = {"steps": [], "since_date": since_date}

    def _append(name: str, result: dict) -> None:
        rollup["steps"].append({"name": name, "result": result})

    res1 = recompute_universe(batch_size=int(batch_size), force=True)
    _append("recompute_indicators", res1)

    from app.config import settings as _cfg

    try:
        res2 = snapshot_last_n_days(
            days=_cfg.RECOMPUTE_HISTORY_MAX_DAYS,
            since_date=since_date,
            batch_size=int(history_batch_size),
        )
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        res2 = {"status": "error", "error": str(exc)}
    _append("snapshot_history_rebuild", res2)

    from app.tasks.market.coverage import health_check

    res3 = health_check()
    _append("coverage_refresh", res3)

    statuses = [s.get("result", {}).get("status") for s in rollup["steps"]]
    rollup["status"] = "ok" if all(s in (None, "ok") for s in statuses) else "error"
    _set_task_status("admin_recompute_since_date", rollup["status"], rollup)
    return rollup
