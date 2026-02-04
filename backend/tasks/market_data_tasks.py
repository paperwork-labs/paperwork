from __future__ import annotations

"""Market data task suite

Sections:
- Backfill: populate `price_data` with recent daily OHLCV (delta-only)
- Indicators: compute and persist `MarketSnapshot` for symbols
- History: write immutable daily `MarketAnalysisHistory`
- Chart metrics: TD Sequential, gaps and trendlines enrichment

All tasks are safe to run repeatedly (idempotent writes; ON CONFLICT for bars).
"""

from celery import shared_task
import asyncio
from datetime import datetime, timedelta
from typing import List, Set, Dict, Optional

from backend.database import SessionLocal
from backend.models import PriceData
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
from backend.models.market_data import MarketSnapshotHistory, MarketSnapshot
from backend.models import IndexConstituent
from backend.services.market.market_data_service import (
    market_data_service,
    compute_coverage_status,
)
from backend.services.market.backfill_params import daily_backfill_params
from backend.services.market.universe import tracked_symbols_from_db
from backend.models import Position
from backend.config import settings
from .task_utils import task_run

import json

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _setup_event_loop() -> asyncio.AbstractEventLoop:
    """Create a fresh event loop for sync task wrappers (caller must close).

    IMPORTANT: Do not set this loop as the global default via asyncio.set_event_loop().
    These tasks run loop.run_until_complete(...) explicitly, and setting a closed loop as
    the process-global default can break unrelated code/tests that use asyncio.
    """
    return asyncio.new_event_loop()


def _increment_provider_usage(usage: Dict[str, int], result: dict | None) -> None:
    provider = (result or {}).get("provider") or "unknown"
    usage[provider] = usage.get(provider, 0) + 1
# ============================= Single-Symbol Refresh =============================


@shared_task(name="backend.tasks.market_data_tasks.refresh_single_symbol")
@task_run("refresh_single_symbol", lock_key=lambda symbol: str(symbol).upper() if symbol else None)
def refresh_single_symbol(symbol: str) -> dict:
    """Delta backfill and recompute indicators for a single symbol (DB-first, no provider TA).

    Steps:
    - Backfill last ~200 bars for symbol (delta-only inserts)
    - Recompute indicators from local DB and persist snapshot
    """
    if not symbol:
        return {"status": "error", "error": "symbol required"}
    sym = str(symbol).upper()
    _set_task_status("refresh_single_symbol", "running", {"symbol": sym})
    session = SessionLocal()
    try:
        # Backfill (delta-only)
        backfill_symbols([sym])
        # Recompute from DB
        snap = market_data_service.compute_snapshot_from_db(session, sym)
        if snap:
            market_data_service.persist_snapshot(session, sym, snap)
            res = {"status": "ok", "symbol": sym, "recomputed": True}
        else:
            res = {"status": "ok", "symbol": sym, "recomputed": False}
        _set_task_status("refresh_single_symbol", "ok", res)
        return res
    finally:
        session.close()


# ============================= Index Fundamentals Enrichment =============================


@shared_task(name="backend.tasks.market_data_tasks.enrich_index_fundamentals")
@task_run("enrich_index_fundamentals")
def enrich_index_fundamentals(indices: List[str] | None = None, limit_per_run: int = 500) -> dict:
    """Fill sector/industry/market_cap on IndexConstituent using DB-first snapshots.

    - Reads latest MarketSnapshot for a symbol; if missing, computes snapshot from DB
    - Only if still missing, fetch fundamentals via providers (FMP/yfinance fallback)
    - Updates IndexConstituent rows with any available fundamentals
    """
    _set_task_status("enrich_index_fundamentals", "running")
    session = SessionLocal()
    try:
        q = session.query(IndexConstituent)
        if indices:
            q = q.filter(IndexConstituent.index_name.in_([i.upper() for i in indices]))
        # Prefer rows missing any of the fields
        rows = (
            q.filter(
                (IndexConstituent.sector.is_(None))
                | (IndexConstituent.industry.is_(None))
                | (IndexConstituent.market_cap.is_(None))
            )
            .order_by(IndexConstituent.symbol.asc())
            .limit(limit_per_run)
            .all()
        )
        updated = 0
        for r in rows:
            sym = (r.symbol or "").upper()
            if not sym:
                continue
            # Use snapshot if present; else compute from DB (fast)
            snap = market_data_service.get_snapshot_from_store(session, sym)
            if not snap:
                snap = market_data_service.compute_snapshot_from_db(session, sym)
            # If still missing, compute from providers (slow path) but only for fundamentals
            if not snap or (snap.get("sector") is None and snap.get("industry") is None and snap.get("market_cap") is None):
                try:
                    # Reuse provider fundamentals logic by triggering provider snapshot compute
                    # but we won't persist unless needed downstream
                    loop = _setup_event_loop()
                    try:
                        prov = loop.run_until_complete(market_data_service.compute_snapshot_from_providers(sym))
                    finally:
                        loop.close()
                    if prov:
                        for k in ("sector", "industry", "market_cap"):
                            if prov.get(k) is not None:
                                snap = snap or {}
                                snap[k] = prov.get(k)
                except Exception:
                    pass
            if not snap:
                continue
            changed = False
            if r.sector is None and snap.get("sector") is not None:
                r.sector = snap.get("sector")
                changed = True
            if r.industry is None and snap.get("industry") is not None:
                r.industry = snap.get("industry")
                changed = True
            if r.market_cap is None and snap.get("market_cap") is not None:
                try:
                    r.market_cap = int(snap.get("market_cap"))
                except Exception:
                    pass
                else:
                    changed = True
            if changed:
                updated += 1
        if updated:
            session.commit()
        res = {"status": "ok", "inspected": len(rows), "updated": updated}
        _set_task_status("enrich_index_fundamentals", "ok", res)
        return res
    finally:
        session.close()


# ============================= Snapshot Fundamentals Backfill =============================


@shared_task(name="backend.tasks.market_data_tasks.fill_missing_snapshot_fundamentals")
@task_run("fill_missing_snapshot_fundamentals")
def fill_missing_snapshot_fundamentals(limit_per_run: int = 500) -> dict:
    """Fill missing sector/industry/market_cap on MarketSnapshot rows.

    DB-first: try compute_snapshot_from_db; if still missing, fallback to providers.
    Persists updated snapshot via market_data_service.persist_snapshot.
    """
    _set_task_status("fill_missing_snapshot_fundamentals", "running")
    session = SessionLocal()
    try:
        from backend.models.market_data import MarketSnapshot as _MS

        rows = (
            session.query(_MS)
            .filter(
                _MS.analysis_type == "technical_snapshot",
                (
                    (_MS.sector.is_(None))
                    | (_MS.industry.is_(None))
                    | (_MS.market_cap.is_(None))
                ),
            )
            .order_by(_MS.analysis_timestamp.desc())
            .limit(limit_per_run)
            .all()
        )
        updated = 0
        for r in rows:
            sym = (r.symbol or "").upper()
            if not sym:
                continue
            # Build from DB first (no external calls)
            snap = market_data_service.compute_snapshot_from_db(session, sym)
            # If fundamentals still missing, fetch fundamentals only (FMP-first, no price fetch)
            needs_funda = (
                not snap
                or (
                    snap.get("name") is None
                    and snap.get("sector") is None
                    and snap.get("industry") is None
                    and snap.get("sub_industry") is None
                    and snap.get("market_cap") is None
                )
            )
            if needs_funda:
                funda = market_data_service.get_fundamentals_info(sym)
                if funda:
                    snap = snap or {}
                    for k in ("name", "sector", "industry", "sub_industry", "market_cap"):
                        if funda.get(k) is not None:
                            snap[k] = funda.get(k)
            if not snap:
                continue
            # Persist only if something new available
            if (
                (getattr(r, "name", None) is None and snap.get("name") is not None)
                or (r.sector is None and snap.get("sector") is not None)
                or (r.industry is None and snap.get("industry") is not None)
                or (getattr(r, "sub_industry", None) is None and snap.get("sub_industry") is not None)
                or (r.market_cap is None and snap.get("market_cap") is not None)
            ):
                market_data_service.persist_snapshot(session, sym, {**(r.raw_analysis or {}), **snap})
                updated += 1
        res = {"status": "ok", "inspected": len(rows), "updated": updated}
        _set_task_status("fill_missing_snapshot_fundamentals", "ok", res)
        return res
    finally:
        session.close()

# ============================= Task Status Helper =============================


def _set_task_status(task_name: str, status: str, payload: dict | None = None) -> None:
    try:
        r = market_data_service.redis_client
        r.set(
            f"taskstatus:{task_name}:last",
            json.dumps(
                {
                    "task": task_name,
                    "status": status,
                    "ts": datetime.utcnow().isoformat(),
                    "payload": payload or {},
                }
            ),
        )
    except Exception:
        pass


# ============================= Tracked Universe Cache =============================


def _get_tracked_universe_from_db(session: SessionLocal) -> set[str]:
    """Union of active index constituents and portfolio symbols.

    IMPORTANT:
    - We intentionally exclude inactive index constituents, otherwise the tracked universe
      accumulates delisted/removed tickers and coverage will look degraded forever.
    """
    # Keep return type for callers (set), but delegate the actual logic to the shared helper.
    return set(tracked_symbols_from_db(session))


@shared_task(name="backend.tasks.market_data_tasks.update_tracked_symbol_cache")
@task_run("update_tracked_symbol_cache")
def update_tracked_symbol_cache() -> dict:
    """Compute union of tracked symbols (index_constituents ∪ portfolio) and publish deltas.

    Writes two Redis keys:
    - tracked:all → full sorted list of tracked symbols
    - tracked:new → new additions since last run (expires 24h)
    """
    _set_task_status("update_tracked_symbol_cache", "running")
    session = SessionLocal()
    try:
        redis = market_data_service.redis_client
        current = sorted(_get_tracked_universe_from_db(session))
        # Bootstrap: if nothing tracked in DB yet, seed from live index constituents
        if not current:
            loop = None
            try:
                loop = _setup_event_loop()
                index_to_symbols: dict[str, set[str]] = {
                    "SP500": set(),
                    "NASDAQ100": set(),
                    "DOW30": set(),
                }
                for idx in ["SP500", "NASDAQ100", "DOW30"]:
                    try:
                        cons = loop.run_until_complete(
                            market_data_service.get_index_constituents(idx)
                        )
                        index_to_symbols[idx].update({s.upper() for s in cons if s})
                    except Exception:
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
            except Exception:
                pass
            finally:
                if loop:
                    loop.close()
        prev_raw = redis.get("tracked:all")
        prev = []
        if prev_raw:
            try:
                prev = json.loads(prev_raw)
            except Exception:
                prev = []
        prev_set = set(s.upper() for s in prev)
        additions = [s for s in current if s not in prev_set]
        redis.set("tracked:all", json.dumps(current))
        redis.setex("tracked:new", 24 * 3600, json.dumps(additions))
        res = {"status": "ok", "tracked_all": len(current), "new": len(additions)}
        _set_task_status("update_tracked_symbol_cache", "ok", res)
        return res
    finally:
        session.close()


# ============================= Backfill =============================


def _daily_backfill_concurrency() -> int:
    policy = str(getattr(settings, "MARKET_PROVIDER_POLICY", "paid")).lower()
    paid = policy == "paid"
    max_conc = int(getattr(settings, "MARKET_BACKFILL_CONCURRENCY_MAX", 100))
    conc_default = int(
        getattr(
            settings,
            "MARKET_BACKFILL_CONCURRENCY_PAID" if paid else "MARKET_BACKFILL_CONCURRENCY_FREE",
            25 if paid else 5,
        )
    )
    return max(1, min(max_conc, conc_default))


async def _fetch_daily_for_symbols(
    *,
    symbols: list[str],
    period: str,
    max_bars: int | None,
    concurrency: int,
) -> list[dict]:
    sem = asyncio.Semaphore(max(1, int(concurrency)))
    out: list[dict] = []

    async def _one(sym: str) -> dict:
        async with sem:
            df, provider = await market_data_service.get_historical_data(
                symbol=sym.upper(),
                period=period,
                interval="1d",
                max_bars=max_bars,
                return_provider=True,
            )
            return {"symbol": sym.upper(), "df": df, "provider": provider}

    tasks = [_one(s) for s in sorted({str(s).upper() for s in (symbols or []) if s})]
    for coro in asyncio.as_completed(tasks):
        try:
            out.append(await coro)
        except Exception as e:
            out.append({"symbol": "?", "df": None, "provider": None, "error": str(e)})
    return out


def _persist_daily_fetch_results(
    *,
    session: SessionLocal,
    fetched: list[dict],
    since_dt: object | None,
    use_delta_after: bool,
    error_samples_limit: int = 25,
) -> dict:
    import pandas as pd
    from backend.models import PriceData

    updated_total = 0
    up_to_date_total = 0
    bars_inserted_total = 0
    bars_attempted_total = 0
    processed_ok = 0
    skipped_empty = 0
    errors = 0
    error_samples: list[dict] = []
    provider_usage: Dict[str, int] = {}

    for item in fetched or []:
        sym = item.get("symbol")
        if not sym or sym == "?":
            errors += 1
            continue
        df = item.get("df")
        provider = item.get("provider")

        if df is None or getattr(df, "empty", True):
            skipped_empty += 1
            errors += 1
            if len(error_samples) < error_samples_limit:
                error_samples.append(
                    {"symbol": sym, "provider": provider or "unknown", "error": "empty_response"}
                )
            _increment_provider_usage(provider_usage, {"provider": provider})
            continue

        try:
            df2 = df
            if since_dt is not None:
                # Normalize index and filter (UTC -> naive) to match DB semantics.
                df2 = df.copy()
                df2.index = (
                    pd.to_datetime(df2.index, utc=True, errors="coerce")
                    .tz_convert(None)
                )
                df2 = df2[df2.index >= since_dt]
                if df2 is None or df2.empty:
                    processed_ok += 1
                    _increment_provider_usage(provider_usage, {"provider": provider})
                    continue

            bars_attempted_total += int(len(df2))
            last_date = None
            if use_delta_after:
                last_date = (
                    session.query(PriceData.date)
                    .filter(PriceData.symbol == sym, PriceData.interval == "1d")
                    .order_by(PriceData.date.desc())
                    .limit(1)
                    .scalar()
                )

            inserted = market_data_service.persist_price_bars(
                session,
                sym,
                df2,
                interval="1d",
                data_source=provider or "unknown",
                is_adjusted=True,
                delta_after=last_date if use_delta_after else None,
            )
            _increment_provider_usage(provider_usage, {"provider": provider})
            processed_ok += 1
            if inserted and int(inserted) > 0:
                updated_total += 1
                bars_inserted_total += int(inserted)
            else:
                up_to_date_total += 1
        except Exception as exc:
            errors += 1
            session.rollback()
            if len(error_samples) < error_samples_limit:
                error_samples.append(
                    {"symbol": sym, "provider": provider or "unknown", "error": str(exc)}
                )

    return {
        "updated_total": updated_total,
        "up_to_date_total": up_to_date_total,
        "bars_inserted_total": bars_inserted_total,
        "bars_attempted_total": bars_attempted_total,
        "processed_ok": processed_ok,
        "skipped_empty": skipped_empty,
        "errors": errors,
        "error_samples": error_samples,
        "provider_usage": provider_usage,
    }


@shared_task(name="backend.tasks.market_data_tasks.backfill_last_bars")
@task_run("backfill_last_bars")
def backfill_last_bars(days: int = 200) -> dict:
    """Delta backfill last N *trading days* (approx) of daily bars for the tracked universe.

    Returns detailed counters:
    - tracked_total, updated_total, up_to_date_total, skipped_empty, bars_inserted_total, errors, error_samples
    """
    _set_task_status("backfill_last_bars", "running", {"days": int(days)})
    session = SessionLocal()
    try:
        # Use durable tracked universe (index_constituents ∪ portfolio)
        symbols = _get_tracked_universe_from_db(session)
        loop = _setup_event_loop()
        try:
            tracked_total = len(symbols)
            concurrency = _daily_backfill_concurrency()
            params = daily_backfill_params(days=days)
            fetched = loop.run_until_complete(
                _fetch_daily_for_symbols(
                    symbols=list(symbols),
                    period=params.period,
                    max_bars=params.max_bars,
                    concurrency=concurrency,
                )
            )
            # Second pass: retry empties with lower concurrency to reduce transient provider flakiness.
            empties = sorted(
                {
                    str(i.get("symbol", "")).upper()
                    for i in fetched
                    if i.get("symbol")
                    and i.get("symbol") != "?"
                    and (i.get("df") is None or getattr(i.get("df"), "empty", True))
                }
            )
            if empties:
                retry_conc = max(1, min(10, max(1, concurrency // 5)))
                retried = loop.run_until_complete(
                    _fetch_daily_for_symbols(
                        symbols=empties,
                        period=params.period,
                        max_bars=params.max_bars,
                        concurrency=retry_conc,
                    )
                )
                retry_map = {r.get("symbol"): r for r in retried if r.get("symbol")}
                for i, item in enumerate(fetched):
                    sym = item.get("symbol")
                    if sym in retry_map and (item.get("df") is None or getattr(item.get("df"), "empty", True)):
                        fetched[i] = retry_map[sym]

            # Persist (delta insert after last_date)
            persist = _persist_daily_fetch_results(
                session=session,
                fetched=fetched,
                since_dt=None,
                use_delta_after=True,
            )
        finally:
            loop.close()
        res = {
            "status": "ok",
            "days": int(days),
            "period": params.period,
            "max_bars": params.max_bars,
            "tracked_total": tracked_total,
            "updated_total": persist["updated_total"],
            "up_to_date_total": persist["up_to_date_total"],
            "skipped_empty": persist["skipped_empty"],
            "bars_inserted_total": persist["bars_inserted_total"],
            "errors": persist["errors"],
            "error_samples": persist["error_samples"],
            "provider_usage": persist["provider_usage"],
        }
        _set_task_status("backfill_last_bars", "ok", res)
        return res
    finally:
        session.close()




@shared_task(name="backend.tasks.market_data_tasks.backfill_symbols")
@task_run("backfill_symbols")
def backfill_symbols(symbols: List[str], days: int = 200) -> dict:
    """Delta backfill last-year-ish daily bars for a provided symbol list (concurrent fetch, safe persist)."""
    session = SessionLocal()
    try:
        loop = _setup_event_loop()
        try:
            concurrency = _daily_backfill_concurrency()
            params = daily_backfill_params(days=days)
            fetched = loop.run_until_complete(
                _fetch_daily_for_symbols(
                    symbols=[s.upper() for s in (symbols or []) if s],
                    period=params.period,
                    max_bars=params.max_bars,
                    concurrency=concurrency,
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
            "rows_attempted": persist["bars_inserted_total"],
            "errors": persist["errors"],
            "error_samples": persist["error_samples"],
            "provider_usage": persist["provider_usage"],
        }
    finally:
        session.close()


# ============================= Index Constituents =============================


@shared_task(name="backend.tasks.market_data_tasks.refresh_index_constituents")
@task_run("refresh_index_constituents")
def refresh_index_constituents() -> dict:
    """Refresh index constituents table for SP500, NASDAQ100, DOW30 (and keep inactive).

    - Inserts new symbols and marks them active
    - If a symbol disappears from a list, we mark it inactive and set became_inactive_at
    """
    _set_task_status("refresh_index_constituents", "running")
    loop = _setup_event_loop()
    results = {}
    session = SessionLocal()
    try:
        from datetime import datetime

        now = datetime.utcnow()
        # Preflight: ensure at least one provider path is available
        from backend.config import settings as _settings
        preflight = {
            "has_fmp_key": bool(getattr(_settings, "FMP_API_KEY", "")),
        }
        for idx in ["SP500", "NASDAQ100", "DOW30"]:
            try:
                symbols = set(loop.run_until_complete(market_data_service.get_index_constituents(idx)))
            except Exception as e:
                results[idx] = {"error": str(e)}
                continue
            # Read provider meta if present
            provider_used = "unknown"
            fallback_used = None
            try:
                meta_raw = market_data_service.redis_client.get(f"index_constituents:{idx}:meta")
                if meta_raw:
                    meta = json.loads(meta_raw)
                    provider_used = meta.get("provider_used", provider_used)
                    fallback_used = meta.get("fallback_used", False)
            except Exception:
                pass
            # existing rows
            existing_rows = (
                session.query(IndexConstituent)
                .filter(IndexConstituent.index_name == idx)
                .all()
            )
            existing_map = {r.symbol: r for r in existing_rows}
            # upsert new/active
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
            # mark inactive
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
        res = {"status": "ok", "preflight": preflight, "indices": results}
        _set_task_status("refresh_index_constituents", "ok", res)
        return res
    finally:
        session.close()


@shared_task(name="backend.tasks.market_data_tasks.backfill_daily_since_date")
@task_run("backfill_daily_since_date")
def backfill_daily_since_date(since_date: str = "2021-01-01", batch_size: int = 25) -> dict:
    """One-time (or occasional) deep backfill of DAILY bars since a given date for the tracked universe.

    This fetches provider daily history (FMP-first in paid mode) and persists into price_data.
    It is intentionally separate from the fast 'last 200 bars' flows.
    """
    _set_task_status("backfill_daily_since_date", "running", {"since_date": since_date})
    session = SessionLocal()
    try:
        import pandas as pd

        since_dt = pd.to_datetime(since_date, utc=True, errors="coerce")
        if since_dt is None or pd.isna(since_dt):
            raise ValueError(f"Invalid since_date: {since_date!r}")
        since_dt = since_dt.tz_convert(None).normalize()

        loop = _setup_event_loop()
        try:
            # Universe: prefer Redis tracked:all; fallback to DB-derived tracked universe.
            tracked: List[str] = []
            try:
                raw = market_data_service.redis_client.get("tracked:all")
                tracked = json.loads(raw) if raw else []
            except Exception:
                tracked = []
            symbols = sorted({str(s).upper() for s in (tracked or []) if s})
            if not symbols:
                symbols = sorted({s.upper() for s in _get_tracked_universe_from_db(session)})

            concurrency = _daily_backfill_concurrency()
            fetched = loop.run_until_complete(
                _fetch_daily_for_symbols(
                    symbols=symbols,
                    period="max",
                    max_bars=None,
                    concurrency=concurrency,
                )
            )
        finally:
            loop.close()

        persist = _persist_daily_fetch_results(
            session=session,
            fetched=fetched,
            since_dt=since_dt,
            use_delta_after=False,  # deep backfill; idempotent via ON CONFLICT
        )
        res = {
            "status": "ok" if persist["errors"] == 0 else "error",
            "since_date": since_date,
            "symbols": len(symbols),
            "processed_symbols": persist["processed_ok"],
            "bars_attempted_total": persist["bars_attempted_total"],
            "bars_inserted_total": persist["bars_inserted_total"],
            "errors": persist["errors"],
            "error_samples": persist["error_samples"],
            "provider_usage": persist["provider_usage"],
        }
        _set_task_status("backfill_daily_since_date", "ok" if persist["errors"] == 0 else "error", res)
        return res
    finally:
        session.close()


# ============================= Repair Since Date (Daily + Indicators + History) =============================
@shared_task(name="backend.tasks.market_data_tasks.repair_since_date")
@task_run("repair_since_date", lock_key=lambda since_date, **_: f"repair_since_date:{since_date}")
def repair_since_date(
    since_date: str = "2021-01-01",
    daily_batch_size: int = 25,
    history_batch_size: int = 50,
) -> dict:
    """Deep repair pipeline since a given date.

    Steps:
    - Backfill daily OHLCV since date (provider fetch)
    - Recompute indicators (MarketSnapshot) for tracked universe
    - Backfill snapshot history since date (DB-only)
    - Refresh coverage cache (monitor_coverage_health)
    """

    def _summarize(step: str, payload: dict | None) -> str:
        data = payload or {}
        if step == "backfill_daily_since_date":
            return f"Daily since {data.get('since_date', '?')}: {data.get('bars_inserted_total', 0)} bars"
        if step == "recompute_indicators_universe":
            return f"Recomputed {data.get('processed', data.get('symbols', 0))} / {data.get('symbols', 0)}"
        if step == "backfill_snapshot_history_last_n_days":
            return (
                f"Snapshot history: {data.get('processed_symbols', 0)} syms, "
                f"{data.get('written_rows', 0)} rows"
            )
        if step == "monitor_coverage_health":
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

    _set_task_status("repair_since_date", "running", {"since_date": since_date})

    res1 = backfill_daily_since_date(since_date=since_date, batch_size=int(daily_batch_size))
    _append("backfill_daily_since_date", res1)

    res2 = recompute_indicators_universe(batch_size=50)
    _append("recompute_indicators_universe", res2)

    try:
        res3 = backfill_snapshot_history_last_n_days(
            days=3000, since_date=since_date, batch_size=int(history_batch_size)
        )
    except Exception as exc:
        res3 = {"status": "error", "error": str(exc)}
    _append("backfill_snapshot_history_last_n_days", res3)

    res4 = monitor_coverage_health()
    _append("monitor_coverage_health", res4)

    statuses = [step.get("result", {}).get("status") for step in rollup["steps"]]
    rollup["status"] = "ok" if all(s in (None, "ok") for s in statuses) else "error"
    rollup["overall_summary"] = "; ".join(
        step["summary"] for step in rollup["steps"] if step.get("summary")
    )
    _set_task_status("repair_since_date", rollup["status"], rollup)
    return rollup


# ============================= Coverage Restore (Daily, Tracked Universe) =============================
@shared_task(name="backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked")
@task_run("bootstrap_daily_coverage_tracked", lock_key=lambda: "bootstrap_daily_coverage_tracked")
def bootstrap_daily_coverage_tracked(history_days: int = 20, history_batch_size: int = 25) -> dict:
    """Restore DAILY coverage for the tracked universe (no 5m).

    Steps:
    - Refresh index constituents (keeps constituents current)
    - Update tracked universe cache (tracked:all)
    - Backfill last ~200 daily bars for tracked universe
    - Recompute indicators for tracked universe
    - Backfill snapshot history (rolling window; default last 20 trading days) into MarketSnapshotHistory
    - Refresh coverage cache (monitor_coverage_health)
    """

    def _summarize(step: str, payload: dict | None) -> str:
        data = payload or {}
        if step == "refresh_index_constituents":
            idx = data.get("indices") or {}
            parts = [
                f"{name}: {stats.get('fetched', 0)} via {stats.get('provider_used', 'n/a')}"
                for name, stats in idx.items()
            ]
            return "; ".join(parts) or "Refreshed constituents"
        if step == "update_tracked_symbol_cache":
            return f"{data.get('tracked_all', 0)} tracked ({data.get('new', 0)} new)"
        if step == "backfill_last_bars":
            return f"Inserted {data.get('bars_inserted_total', 0)} bars across {data.get('tracked_total', 0)} tracked"
        if step == "recompute_indicators_universe":
            return f"Recomputed {data.get('processed', data.get('symbols', 0))} / {data.get('symbols', 0)}"
        if step == "backfill_snapshot_history_last_n_days":
            return (
                f"Snapshot history: {data.get('processed_symbols', 0)} syms, "
                f"{data.get('written_rows', 0)} rows (days={data.get('days', 0)})"
            )
        if step == "monitor_coverage_health":
            return f"Coverage: {data.get('daily_pct', 0)}% daily; stale={data.get('stale_daily', 0)}"
        return data.get("status", "ok")

    rollup: dict = {"steps": []}

    def _append(step_name: str, result: dict) -> None:
        rollup["steps"].append(
            {
                "name": step_name,
                "summary": _summarize(step_name, result),
                "result": result,
            }
        )

    res1 = refresh_index_constituents()
    _append("refresh_index_constituents", res1)

    res2 = update_tracked_symbol_cache()
    _append("update_tracked_symbol_cache", res2)

    res3 = backfill_last_bars(days=200)
    _append("backfill_last_bars", res3)

    res4 = recompute_indicators_universe(batch_size=50)
    _append("recompute_indicators_universe", res4)

    # Historical ledger: last N trading days into MarketSnapshotHistory.
    # This is best-effort: if it fails, still refresh coverage so the operator sees the latest state.
    try:
        res5 = backfill_snapshot_history_last_n_days(
            days=int(history_days), batch_size=int(history_batch_size)
        )
    except Exception as exc:
        res5 = {"status": "error", "error": str(exc)}
    _append("backfill_snapshot_history_last_n_days", res5)

    res6 = monitor_coverage_health()
    _append("monitor_coverage_health", res6)

    rollup["status"] = "ok"
    rollup["overall_summary"] = "; ".join(
        step["summary"] for step in rollup["steps"] if step.get("summary")
    )
    return rollup


# ============================= Backfill stale daily (Tracked universe) =============================
@shared_task(name="backend.tasks.market_data_tasks.backfill_stale_daily_tracked")
@task_run("backfill_stale_daily_tracked", lock_key=lambda: "backfill_stale_daily_tracked")
def backfill_stale_daily_tracked() -> dict:
    """Backfill daily bars for ALL stale/missing symbols in the tracked universe.

    This is the safe replacement for any UI/operator flow that previously used a sampled
    stale list (e.g., COVERAGE_STALE_SAMPLE). Here we compute the full stale+missing set.
    """
    _set_task_status("backfill_stale_daily_tracked", "running")
    session = SessionLocal()
    try:
        # Universe: prefer Redis tracked:all; fallback to DB-derived tracked universe.
        tracked: List[str] = []
        try:
            raw = market_data_service.redis_client.get("tracked:all")
            tracked = json.loads(raw) if raw else []
        except Exception:
            tracked = []
        tracked = sorted({str(s).upper() for s in (tracked or []) if s})
        if not tracked:
            tracked = sorted({s.upper() for s in _get_tracked_universe_from_db(session)})

        # Compute stale+missing using the same bucketing logic as coverage.
        section, stale_full = market_data_service._compute_interval_coverage_for_symbols(
            session,
            symbols=tracked,
            interval="1d",
            now_utc=datetime.utcnow(),
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
            _set_task_status("backfill_stale_daily_tracked", "ok", res)
            return res

        backfill_res = backfill_symbols(stale_symbols)
        monitor_res = monitor_coverage_health()
        res = {
            "status": "ok",
            "tracked_total": len(tracked),
            "stale_candidates": len(stale_symbols),
            "backfill": backfill_res,
            "monitor": monitor_res,
        }
        _set_task_status("backfill_stale_daily_tracked", "ok", res)
        return res
    finally:
        session.close()


# ============================= Recompute Indicators and Chart Metrics =============================


@shared_task(name="backend.tasks.market_data_tasks.recompute_indicators_universe")
@task_run("recompute_indicators_universe")
def recompute_indicators_universe(batch_size: int = 50) -> dict:
    """Recompute indicators for the tracked universe from local DB (orchestrator only).

    Observability:
    - Returns counters used by task_run() to persist JobRun.counters
    - Includes a bounded non-fatal error summary in the returned `error` field, which is
      captured into JobRun.error (without failing the whole run).
    """
    _set_task_status("recompute_indicators_universe", "running")
    session = SessionLocal()
    try:
        # Universe: prefer Redis tracked:all (source of truth for UI), fallback to DB-derived.
        tracked: List[str] = []
        try:
            raw = market_data_service.redis_client.get("tracked:all")
            tracked = json.loads(raw) if raw else []
        except Exception:
            tracked = []
        ordered = sorted({str(s).upper() for s in (tracked or []) if s})
        if not ordered:
            ordered = sorted({s.upper() for s in _get_tracked_universe_from_db(session)})

        processed_ok = 0
        skipped_no_data = 0
        errors = 0
        error_samples: list[dict] = []
        warnings: list[str] = []

        # Preflight: ensure benchmark (SPY) has enough daily bars for Stage/RS
        # and is not stale vs the latest daily OHLCV in the DB.
        benchmark_symbol = "SPY"
        required_bars = max(260, int(getattr(settings, "SNAPSHOT_DAILY_BARS_LIMIT", 400)))
        benchmark_count = session.query(PriceData).filter(
            PriceData.symbol == benchmark_symbol, PriceData.interval == "1d"
        ).count()
        benchmark_latest_dt = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.symbol == benchmark_symbol, PriceData.interval == "1d")
            .scalar()
        )
        latest_daily_dt = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.interval == "1d")
            .scalar()
        )
        benchmark_fetched = False
        benchmark_errors = 0
        benchmark_stale = False
        if latest_daily_dt and benchmark_latest_dt:
            benchmark_stale = benchmark_latest_dt.date() < latest_daily_dt.date()
        if benchmark_count < required_bars or benchmark_latest_dt is None or benchmark_stale:
            loop = _setup_event_loop()
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
            benchmark_count = session.query(PriceData).filter(
                PriceData.symbol == benchmark_symbol, PriceData.interval == "1d"
            ).count()
            benchmark_latest_dt = (
                session.query(func.max(PriceData.date))
                .filter(PriceData.symbol == benchmark_symbol, PriceData.interval == "1d")
                .scalar()
            )
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

        # Chunking by batch_size
        for i in range(0, len(ordered), max(1, batch_size)):
            chunk = ordered[i : i + batch_size]
            for sym in chunk:
                try:
                    snap = market_data_service.compute_snapshot_from_db(session, sym)
                    if not snap:
                        skipped_no_data += 1
                        continue
                    market_data_service.persist_snapshot(session, sym, snap)
                    processed_ok += 1
                except Exception as exc:
                    session.rollback()
                    errors += 1
                    if len(error_samples) < 25:
                        error_samples.append({"symbol": sym, "error": str(exc)})
        res = {
            "status": "ok",
            "symbols": len(ordered),
            "processed_ok": processed_ok,
            "skipped_no_data": skipped_no_data,
            "errors": errors,
            "error_samples": error_samples,
            "benchmark": {
                "symbol": benchmark_symbol,
                "required_bars": required_bars,
                "daily_bars": benchmark_count,
                "fetched": benchmark_fetched,
                "errors": benchmark_errors,
                "ok": benchmark_count >= required_bars,
            },
        }
        if warnings:
            res["warnings"] = warnings
        if error_samples:
            # Non-fatal, bounded summary captured into JobRun.error by task_run()
            res["error"] = "Sample errors:\n" + "\n".join(
                f"- {e.get('symbol')}: {e.get('error')}" for e in error_samples
            )
        _set_task_status("recompute_indicators_universe", "ok", res)
        return res
    finally:
        session.close()


# ============================= Snapshot History Backfill =============================


@shared_task(name="backend.tasks.market_data_tasks.backfill_snapshot_history_for_date")
@task_run("backfill_snapshot_history_for_date")
def backfill_snapshot_history_for_date(as_of_date: str, batch_size: int = 50) -> dict:
    """Backfill `market_snapshot_history` for a specific as-of date from local `price_data`.

    This is useful when history was not recorded for a day but OHLCV exists, and we want
    snapshot coverage dots to reflect that day.

    Notes:
    - DB-first only (no provider calls)
    - Does NOT update `market_snapshot` (latest cache)
    """
    session = SessionLocal()
    try:
        # Parse date (YYYY-MM-DD) into a naive timestamp to match price_data.date semantics.
        as_of_dt = datetime.fromisoformat(as_of_date).replace(hour=0, minute=0, second=0, microsecond=0)

        # Universe: prefer Redis tracked:all (source of truth for UI), fallback to DB-derived.
        tracked: List[str] = []
        try:
            raw = market_data_service.redis_client.get("tracked:all")
            tracked = json.loads(raw) if raw else []
        except Exception:
            tracked = []
        ordered = sorted({str(s).upper() for s in (tracked or []) if s})
        if not ordered:
            ordered = sorted({s.upper() for s in _get_tracked_universe_from_db(session)})

        processed_ok = 0
        skipped_no_data = 0
        upserted = 0
        errors = 0
        error_samples: list[dict] = []

        for i in range(0, len(ordered), max(1, batch_size)):
            chunk = ordered[i : i + batch_size]
            for sym in chunk:
                try:
                    snap = market_data_service.compute_snapshot_from_db(session, sym, as_of_dt=as_of_dt)
                    if not snap:
                        skipped_no_data += 1
                        continue
                    processed_ok += 1

                    # Upsert into history keyed by (symbol, type, as_of_date)
                    existing = (
                        session.query(MarketSnapshotHistory)
                        .filter(
                            MarketSnapshotHistory.symbol == sym,
                            MarketSnapshotHistory.analysis_type == "technical_snapshot",
                            MarketSnapshotHistory.as_of_date == as_of_dt,
                        )
                        .first()
                    )
                    if existing:
                        existing.current_price = snap.get("current_price")
                        existing.rsi = snap.get("rsi")
                        existing.atr_value = snap.get("atr_value")
                        existing.sma_50 = snap.get("sma_50")
                        existing.macd = snap.get("macd")
                        existing.macd_signal = snap.get("macd_signal")
                        for k, v in (snap or {}).items():
                            if hasattr(existing, k):
                                setattr(existing, k, v)
                    else:
                        _reserved = {
                            "id",
                            "symbol",
                            "analysis_type",
                            "as_of_date",
                            "analysis_timestamp",
                            "current_price",
                            "rsi",
                            "atr_value",
                            "sma_50",
                            "macd",
                            "macd_signal",
                        }
                        session.add(
                            MarketSnapshotHistory(
                                symbol=sym,
                                analysis_type="technical_snapshot",
                                as_of_date=as_of_dt,
                                current_price=snap.get("current_price"),
                                rsi=snap.get("rsi"),
                                atr_value=snap.get("atr_value"),
                                sma_50=snap.get("sma_50"),
                                macd=snap.get("macd"),
                                macd_signal=snap.get("macd_signal"),
                                **{
                                    k: v
                                    for k, v in (snap or {}).items()
                                    if k not in _reserved and hasattr(MarketSnapshotHistory, k)
                                },
                            )
                        )
                    session.commit()
                    upserted += 1
                except Exception as exc:
                    session.rollback()
                    errors += 1
                    if len(error_samples) < 25:
                        error_samples.append({"symbol": sym, "error": str(exc)})

        res = {
            "status": "ok",
            "as_of_date": as_of_date,
            "symbols": len(ordered),
            "processed_ok": processed_ok,
            "skipped_no_data": skipped_no_data,
            "upserted": upserted,
            "errors": errors,
            "error_samples": error_samples,
        }
        if error_samples:
            res["error"] = "Sample errors:\n" + "\n".join(
                f"- {e.get('symbol')}: {e.get('error')}" for e in error_samples
            )
        return res
    finally:
        session.close()


@shared_task(name="backend.tasks.market_data_tasks.backfill_snapshot_history_last_n_days")
@task_run("backfill_snapshot_history_last_n_days")
def backfill_snapshot_history_last_n_days(
    days: int = 200,
    batch_size: int = 25,
    since_date: str | None = None,
) -> dict:
    """Backfill `market_snapshot_history` for the last N trading days (SPY calendar) from local DB prices.

    This computes and stores indicators per day (ledger) so you can later view/backtest
    historical snapshots. `market_snapshot` remains the fast latest-view.
    """
    session = SessionLocal()
    try:
        # Universe: prefer Redis tracked:all (source of truth for UI), fallback to DB-derived.
        tracked: List[str] = []
        try:
            raw = market_data_service.redis_client.get("tracked:all")
            tracked = json.loads(raw) if raw else []
        except Exception:
            tracked = []
        ordered = sorted({str(s).upper() for s in (tracked or []) if s})
        if not ordered:
            ordered = sorted({s.upper() for s in _get_tracked_universe_from_db(session)})

        # Trading-day calendar:
        # Prefer SPY dates as canonical, but fall back to any symbol with 1d bars in the DB.
        # This keeps the backfill robust even when SPY isn't present yet or is stale.
        calendar_symbol = "SPY"
        since_dt = None
        if since_date:
            try:
                import pandas as _pd

                since_dt = _pd.to_datetime(since_date, utc=True).tz_convert(None).normalize().to_pydatetime()
            except Exception:
                since_dt = None
        cal_dates = (
            session.query(PriceData.date)
            .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d")
            .order_by(PriceData.date.desc())
            .limit(6000 if since_dt is not None else max(1, int(days)))
            .all()
        )
        as_of_dates = [r[0] for r in cal_dates if r and r[0] is not None and (since_dt is None or r[0] >= since_dt)]
        latest_daily_dt = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.interval == "1d")
            .scalar()
        )
        spy_latest_dt = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d")
            .scalar()
        )
        if latest_daily_dt and (spy_latest_dt is None or spy_latest_dt.date() < latest_daily_dt.date()):
            alt_query = session.query(PriceData.symbol).filter(
                PriceData.interval == "1d",
                PriceData.date == latest_daily_dt,
            )
            if ordered:
                alt_query = alt_query.filter(PriceData.symbol.in_(ordered))
            alt_symbol = alt_query.limit(1).scalar()
            if alt_symbol and alt_symbol != calendar_symbol:
                calendar_symbol = str(alt_symbol)
                cal_dates = (
                    session.query(PriceData.date)
                    .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d")
                    .order_by(PriceData.date.desc())
                    .limit(6000 if since_dt is not None else max(1, int(days)))
                    .all()
                )
                as_of_dates = [r[0] for r in cal_dates if r and r[0] is not None and (since_dt is None or r[0] >= since_dt)]
        if not as_of_dates:
            alt = (
                session.query(PriceData.symbol, func.count(PriceData.date).label("n"))
                .filter(PriceData.interval == "1d")
                .group_by(PriceData.symbol)
                .order_by(func.count(PriceData.date).desc())
                .limit(1)
                .all()
            )
            if alt:
                calendar_symbol = str(alt[0][0] or "")
                cal_dates = (
                    session.query(PriceData.date)
                    .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d")
                    .order_by(PriceData.date.desc())
                    .limit(6000 if since_dt is not None else max(1, int(days)))
                    .all()
                )
                as_of_dates = [r[0] for r in cal_dates if r and r[0] is not None and (since_dt is None or r[0] >= since_dt)]

        if not as_of_dates:
            err = "No daily bars found in price_data to establish a trading-day calendar (expected SPY or any 1d bars)."
            _set_task_status("backfill_snapshot_history_last_n_days", "error", {"status": "error", "error": err})
            return {"status": "error", "error": err}

        # Oldest->newest list (raw timestamps) + normalized midnight UTC keys (naive).
        as_of_dates = sorted(as_of_dates)
        start_dt = as_of_dates[0]

        import pandas as pd

        def _norm_midnight_utc(dt: object) -> datetime:
            # Ensure DatetimeIndex-compatible keys while avoiding tz mismatches.
            ts = pd.to_datetime(dt, utc=True, errors="coerce")
            if ts is None or pd.isna(ts):
                raise ValueError(f"Invalid as_of_date value: {dt!r}")
            return ts.tz_convert(None).normalize().to_pydatetime()

        as_of_days = [_norm_midnight_utc(d) for d in as_of_dates if d is not None]

        # Progress/observability: estimate total rows upfront (upper bound).
        estimated_rows = int(len(ordered) * len(as_of_days))
        _set_task_status(
            "backfill_snapshot_history_last_n_days",
            "running",
            {
                "days": int(days),
                "since_date": since_date,
                "symbols": len(ordered),
                "estimated_rows": estimated_rows,
                "processed_symbols": 0,
                "written_rows": 0,
                "errors": 0,
            },
        )

        processed_symbols = 0
        written_rows = 0
        skipped_no_data = 0
        errors = 0
        error_samples: list[dict] = []

        # Preload calendar bars covering the window (+ buffer for weekly stage)
        spy_rows = (
            session.query(
                PriceData.date,
                PriceData.open_price,
                PriceData.high_price,
                PriceData.low_price,
                PriceData.close_price,
                PriceData.volume,
            )
            .filter(PriceData.symbol == calendar_symbol, PriceData.interval == "1d", PriceData.date >= start_dt)
            .order_by(PriceData.date.asc())
            .all()
        )
        import pandas as pd
        import numpy as np
        from datetime import time as _time
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from backend.models.market_data import MarketSnapshotHistory
        from backend.services.market.indicator_engine import (
            compute_core_indicators_series,
            compute_weinstein_stage_series_from_daily,
            classify_ma_bucket_from_ma,
        )

        if spy_rows:
            spy_df = pd.DataFrame(
                [
                    {
                        "date": r[0],
                        "Open": float(r[1]) if r[1] is not None else float(r[4]),
                        "High": float(r[2]) if r[2] is not None else float(r[4]),
                        "Low": float(r[3]) if r[3] is not None else float(r[4]),
                        "Close": float(r[4]),
                        "Volume": int(r[5] or 0),
                    }
                    for r in spy_rows
                ]
            ).set_index("date")
            # Normalize to midnight UTC (naive) so membership checks align with as_of_days.
            spy_df.index = pd.to_datetime(spy_df.index, utc=True, errors="coerce").tz_convert(None).normalize()
        else:
            spy_df = pd.DataFrame()

        last_progress_emit = 0
        for i in range(0, len(ordered), max(1, batch_size)):
            chunk = ordered[i : i + batch_size]
            for sym in chunk:
                try:
                    rows = (
                        session.query(
                            PriceData.date,
                            PriceData.open_price,
                            PriceData.high_price,
                            PriceData.low_price,
                            PriceData.close_price,
                            PriceData.volume,
                        )
                        .filter(PriceData.symbol == sym, PriceData.interval == "1d", PriceData.date >= start_dt)
                        .order_by(PriceData.date.asc())
                        .all()
                    )
                    if not rows:
                        skipped_no_data += 1
                        continue

                    df = pd.DataFrame(
                        [
                            {
                                "date": r[0],
                                "Open": float(r[1]) if r[1] is not None else float(r[4]),
                                "High": float(r[2]) if r[2] is not None else float(r[4]),
                                "Low": float(r[3]) if r[3] is not None else float(r[4]),
                                "Close": float(r[4]),
                                "Volume": int(r[5] or 0),
                            }
                            for r in rows
                        ]
                    ).set_index("date")
                    # Normalize to midnight UTC (naive) so membership checks align with as_of_days.
                    df.index = pd.to_datetime(df.index, utc=True, errors="coerce").tz_convert(None).normalize()
                    if df.empty:
                        skipped_no_data += 1
                        continue

                    core = compute_core_indicators_series(df)
                    # Derived daily fields
                    close = df["Close"]
                    price = close
                    atr14 = core.get("atr_14")
                    atr30 = core.get("atr_30")
                    sma21 = core.get("sma_21")
                    sma50 = core.get("sma_50")
                    sma100 = core.get("sma_100")
                    sma150 = core.get("sma_150")
                    sma200 = core.get("sma_200")

                    def range_pos(window: int) -> pd.Series:
                        hi = df["High"].rolling(window).max()
                        lo = df["Low"].rolling(window).min()
                        denom = (hi - lo).replace(0, np.nan)
                        return ((price - lo) / denom) * 100.0

                    range20 = range_pos(20)
                    range50 = range_pos(50)
                    range252 = range_pos(252)

                    atrp14 = (atr14 / price) * 100.0
                    atrp30 = (atr30 / price) * 100.0
                    atr_distance = (price - sma50) / atr14

                    atrx_sma21 = (price - sma21) / atr14
                    atrx_sma50 = (price - sma50) / atr14
                    atrx_sma100 = (price - sma100) / atr14
                    atrx_sma150 = (price - sma150) / atr14

                    # Stage / RS (best-effort; may be NaN early if insufficient weekly history)
                    stage_daily = pd.DataFrame(index=df.index)
                    if not spy_df.empty:
                        stage_daily = compute_weinstein_stage_series_from_daily(
                            df.iloc[::-1].copy(),
                            spy_df.iloc[::-1].copy(),
                        )

                    # Build per-date payload rows for last N trading days
                    wanted = [d for d in as_of_days if d in df.index]
                    if not wanted:
                        skipped_no_data += 1
                        continue

                    payload_rows = []
                    for d in wanted:
                        # MA bucket (daily)
                        ma_bucket = None
                        try:
                            ma_bucket = classify_ma_bucket_from_ma(
                                {
                                    "price": float(price.loc[d]),
                                    "sma_5": float(core.loc[d, "sma_5"]) if not pd.isna(core.loc[d, "sma_5"]) else None,
                                    "sma_8": float(core.loc[d, "sma_8"]) if not pd.isna(core.loc[d, "sma_8"]) else None,
                                    "sma_21": float(core.loc[d, "sma_21"]) if not pd.isna(core.loc[d, "sma_21"]) else None,
                                    "sma_50": float(core.loc[d, "sma_50"]) if not pd.isna(core.loc[d, "sma_50"]) else None,
                                    "sma_100": float(core.loc[d, "sma_100"]) if not pd.isna(core.loc[d, "sma_100"]) else None,
                                    "sma_200": float(core.loc[d, "sma_200"]) if not pd.isna(core.loc[d, "sma_200"]) else None,
                                }
                            ).get("bucket")
                        except Exception:
                            ma_bucket = None

                        stage_label = None
                        stage_slope_pct = None
                        stage_dist_pct = None
                        rs_mansfield_pct = None
                        try:
                            if not stage_daily.empty and d in stage_daily.index:
                                stage_label = stage_daily.loc[d, "stage_label"]
                                stage_slope_pct = (
                                    float(stage_daily.loc[d, "stage_slope_pct"])
                                    if "stage_slope_pct" in stage_daily.columns and not pd.isna(stage_daily.loc[d, "stage_slope_pct"])
                                    else None
                                )
                                stage_dist_pct = (
                                    float(stage_daily.loc[d, "stage_dist_pct"])
                                    if "stage_dist_pct" in stage_daily.columns and not pd.isna(stage_daily.loc[d, "stage_dist_pct"])
                                    else None
                                )
                                rs_mansfield_pct = (
                                    float(stage_daily.loc[d, "rs_mansfield_pct"])
                                    if "rs_mansfield_pct" in stage_daily.columns and not pd.isna(stage_daily.loc[d, "rs_mansfield_pct"])
                                    else None
                                )
                        except Exception:
                            pass

                        payload = {
                            "symbol": sym,
                            "analysis_type": "technical_snapshot",
                            "as_of_timestamp": d.isoformat() if hasattr(d, "isoformat") else str(d),
                            "current_price": float(price.loc[d]) if not pd.isna(price.loc[d]) else None,
                            "rsi": float(core.loc[d, "rsi"]) if "rsi" in core.columns and not pd.isna(core.loc[d, "rsi"]) else None,
                            "sma_5": float(core.loc[d, "sma_5"]) if not pd.isna(core.loc[d, "sma_5"]) else None,
                            "sma_14": float(core.loc[d, "sma_14"]) if not pd.isna(core.loc[d, "sma_14"]) else None,
                            "sma_21": float(core.loc[d, "sma_21"]) if not pd.isna(core.loc[d, "sma_21"]) else None,
                            "sma_50": float(core.loc[d, "sma_50"]) if not pd.isna(core.loc[d, "sma_50"]) else None,
                            "sma_100": float(core.loc[d, "sma_100"]) if not pd.isna(core.loc[d, "sma_100"]) else None,
                            "sma_150": float(core.loc[d, "sma_150"]) if not pd.isna(core.loc[d, "sma_150"]) else None,
                            "sma_200": float(core.loc[d, "sma_200"]) if not pd.isna(core.loc[d, "sma_200"]) else None,
                            "atr_14": float(atr14.loc[d]) if atr14 is not None and not pd.isna(atr14.loc[d]) else None,
                            "atr_30": float(atr30.loc[d]) if atr30 is not None and not pd.isna(atr30.loc[d]) else None,
                            "atrp_14": float(atrp14.loc[d]) if not pd.isna(atrp14.loc[d]) else None,
                            "atrp_30": float(atrp30.loc[d]) if not pd.isna(atrp30.loc[d]) else None,
                            "atr_distance": float(atr_distance.loc[d]) if not pd.isna(atr_distance.loc[d]) else None,
                            "range_pos_20d": float(range20.loc[d]) if not pd.isna(range20.loc[d]) else None,
                            "range_pos_50d": float(range50.loc[d]) if not pd.isna(range50.loc[d]) else None,
                            "range_pos_52w": float(range252.loc[d]) if not pd.isna(range252.loc[d]) else None,
                            "atrx_sma_21": float(atrx_sma21.loc[d]) if not pd.isna(atrx_sma21.loc[d]) else None,
                            "atrx_sma_50": float(atrx_sma50.loc[d]) if not pd.isna(atrx_sma50.loc[d]) else None,
                            "atrx_sma_100": float(atrx_sma100.loc[d]) if not pd.isna(atrx_sma100.loc[d]) else None,
                            "atrx_sma_150": float(atrx_sma150.loc[d]) if not pd.isna(atrx_sma150.loc[d]) else None,
                            "macd": float(core.loc[d, "macd"]) if "macd" in core.columns and not pd.isna(core.loc[d, "macd"]) else None,
                            "macd_signal": float(core.loc[d, "macd_signal"]) if "macd_signal" in core.columns and not pd.isna(core.loc[d, "macd_signal"]) else None,
                            "ma_bucket": ma_bucket,
                            "stage_label": stage_label if isinstance(stage_label, str) else None,
                            "stage_label_5d_ago": None,  # computed below
                            "stage_slope_pct": stage_slope_pct,
                            "stage_dist_pct": stage_dist_pct,
                            "rs_mansfield_pct": rs_mansfield_pct,
                        }
                        row = {
                            "symbol": sym,
                            "analysis_type": "technical_snapshot",
                            "as_of_date": d,
                            "current_price": payload.get("current_price"),
                            "rsi": payload.get("rsi"),
                            "atr_value": payload.get("atr_14"),
                            "sma_50": payload.get("sma_50"),
                            "macd": payload.get("macd"),
                            "macd_signal": payload.get("macd_signal"),
                        }
                        # Add any wide columns that exist on the model.
                        for k, v in payload.items():
                            if hasattr(MarketSnapshotHistory, k):
                                row[k] = v
                        payload_rows.append(row)

                    # Stage 5d ago: compute from daily mapped labels and attach to payloads
                    try:
                        if not stage_daily.empty and "stage_label" in stage_daily.columns:
                            stage_5d = stage_daily["stage_label"].shift(5)
                            for r in payload_rows:
                                d = r["as_of_date"]
                                if d in stage_5d.index:
                                    lbl = stage_5d.loc[d]
                                    if isinstance(lbl, str):
                                        r["stage_label_5d_ago"] = lbl
                    except Exception:
                        pass

                    stmt = pg_insert(MarketSnapshotHistory).values(payload_rows)
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_symbol_type_asof",
                        set_={
                            "current_price": stmt.excluded.current_price,
                            "rsi": stmt.excluded.rsi,
                            "atr_value": stmt.excluded.atr_value,
                            "sma_50": stmt.excluded.sma_50,
                            "macd": stmt.excluded.macd,
                            "macd_signal": stmt.excluded.macd_signal,
                            # Wide columns: update everything we provided (excluding identity cols).
                            **{
                                c.name: getattr(stmt.excluded, c.name)
                                for c in MarketSnapshotHistory.__table__.columns
                                if c.name
                                not in {
                                    "id",
                                    "symbol",
                                    "analysis_type",
                                    "as_of_date",
                                    "analysis_timestamp",
                                }
                            },
                        },
                    )
                    session.execute(stmt)
                    session.commit()
                    written_rows += len(payload_rows)
                    processed_symbols += 1

                    # Emit progress every ~10 symbols to keep UI responsive without spamming Redis.
                    if processed_symbols - last_progress_emit >= 10:
                        last_progress_emit = processed_symbols
                        _set_task_status(
                            "backfill_snapshot_history_last_n_days",
                            "running",
                            {
                                "days": int(days),
                                "symbols": len(ordered),
                                "estimated_rows": estimated_rows,
                                "processed_symbols": processed_symbols,
                                "written_rows": written_rows,
                                "skipped_no_data": skipped_no_data,
                                "errors": errors,
                            },
                        )
                except Exception as exc:
                    session.rollback()
                    errors += 1
                    if len(error_samples) < 25:
                        error_samples.append({"symbol": sym, "error": str(exc)})

        res = {
            "status": "ok" if errors == 0 else "error",
            "days": int(days),
            "symbols": len(ordered),
            "calendar_symbol": calendar_symbol,
            "processed_symbols": processed_symbols,
            "written_rows": written_rows,
            "skipped_no_data": skipped_no_data,
            "errors": errors,
            "error_samples": error_samples,
        }
        if error_samples:
            res["error"] = "Sample errors:\n" + "\n".join(
                f"- {e.get('symbol')}: {e.get('error')}" for e in error_samples
            )
        _set_task_status(
            "backfill_snapshot_history_last_n_days",
            "ok" if errors == 0 else "error",
            res,
        )
        return res
    finally:
        session.close()


# ============================= Daily Analysis History =============================


@shared_task(name="backend.tasks.market_data_tasks.record_daily_history")
@task_run("record_daily_history")
def record_daily_history(symbols: List[str] | None = None) -> dict:
    """Persist immutable daily snapshots to MarketAnalysisHistory.

    Reads the latest computed snapshot from MarketAnalysisCache (no provider calls).
    Falls back to compute from local DB if a snapshot row doesn't exist yet.
    """
    _set_task_status("record_daily_history", "running")
    session = SessionLocal()
    try:
        if not symbols:
            # Default to tracked universe (Redis tracked:all, fallback to DB-derived tracked symbols)
            symbols = []
            try:
                raw = market_data_service.redis_client.get("tracked:all")
                symbols = json.loads(raw) if raw else []
            except Exception:
                symbols = []
            if not symbols:
                symbols = _get_tracked_universe_from_db(session)
        written = 0
        skipped_no_snapshot = 0
        errors = 0
        error_samples: list[dict] = []
        for sym in sorted(set(s.upper() for s in symbols)):
            try:
                # Prefer the latest stored snapshot from cache
                row = (
                    session.query(MarketSnapshot)
                    .filter(
                        MarketSnapshot.symbol == sym,
                        MarketSnapshot.analysis_type == "technical_snapshot",
                    )
                    .order_by(MarketSnapshot.analysis_timestamp.desc())
                    .first()
                )
                if row and isinstance(row.raw_analysis, dict):
                    snapshot = dict(row.raw_analysis)
                else:
                    # Fallback: compute from local DB only (fast, no provider)
                    snapshot = market_data_service.compute_snapshot_from_db(session, sym)
                    if not snapshot:
                        skipped_no_snapshot += 1
                        continue
                # Determine as-of date, preferring snapshot as-of timestamp if present.
                as_of_dt = None
                try:
                    as_of_dt = getattr(row, "as_of_timestamp", None) if row is not None else None
                except Exception:
                    as_of_dt = None
                if as_of_dt is None:
                    as_of_dt = (
                        session.query(PriceData.date)
                        .filter(PriceData.symbol == sym, PriceData.interval == "1d")
                        .order_by(PriceData.date.desc())
                        .limit(1)
                        .scalar()
                    )
                from datetime import datetime as _dt

                as_of_date = as_of_dt or _dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                # Upsert-like: unique on (symbol, type, as_of_date)
                existing = (
                    session.query(MarketSnapshotHistory)
                    .filter(
                        MarketSnapshotHistory.symbol == sym,
                        MarketSnapshotHistory.analysis_type == "technical_snapshot",
                        MarketSnapshotHistory.as_of_date == as_of_date,
                    )
                    .first()
                )
                if existing:
                    existing.current_price = snapshot.get("current_price")
                    existing.rsi = snapshot.get("rsi")
                    existing.atr_value = snapshot.get("atr_value")
                    existing.sma_50 = snapshot.get("sma_50")
                    existing.macd = snapshot.get("macd")
                    existing.macd_signal = snapshot.get("macd_signal")
                    for k, v in (snapshot or {}).items():
                        if hasattr(existing, k):
                            setattr(existing, k, v)
                else:
                    _reserved = {
                        "id",
                        "symbol",
                        "analysis_type",
                        "as_of_date",
                        "analysis_timestamp",
                        "current_price",
                        "rsi",
                        "atr_value",
                        "sma_50",
                        "macd",
                        "macd_signal",
                    }
                    row = MarketSnapshotHistory(
                        symbol=sym,
                        analysis_type="technical_snapshot",
                        as_of_date=as_of_date,
                        current_price=snapshot.get("current_price"),
                        rsi=snapshot.get("rsi"),
                        atr_value=snapshot.get("atr_value"),
                        sma_50=snapshot.get("sma_50"),
                        macd=snapshot.get("macd"),
                        macd_signal=snapshot.get("macd_signal"),
                        **{
                            k: v
                            for k, v in (snapshot or {}).items()
                            if k not in _reserved and hasattr(MarketSnapshotHistory, k)
                        },
                    )
                    session.add(row)
                session.commit()
                written += 1
            except Exception:
                session.rollback()
                errors += 1
                if len(error_samples) < 25:
                    error_samples.append({"symbol": sym, "error": "write_failed"})
        res = {
            "status": "ok",
            "symbols": len(symbols),
            "written": written,
            "skipped_no_snapshot": skipped_no_snapshot,
            "errors": errors,
            "error_samples": error_samples,
        }
        _set_task_status("record_daily_history", "ok", res)
        return res
    finally:
        session.close()


# ============================= 5m Intraday Backfill and Retention =============================


def _is_5m_backfill_enabled() -> bool:
    """Check admin toggle stored in Redis; default to enabled on errors."""
    try:
        raw = market_data_service.redis_client.get("coverage:backfill_5m_enabled")
        if raw is None:
            return True
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode()
        return str(raw).strip().lower() not in ("0", "false", "off", "disabled")
    except Exception:
        # Fail open if Redis unavailable so daily flows aren't blocked
        return True


@shared_task(name="backend.tasks.market_data_tasks.backfill_5m_for_symbols")
@task_run("backfill_5m_for_symbols")
def backfill_5m_for_symbols(symbols: List[str], n_days: int = 5) -> dict:
    """Delta backfill last N days of 5m bars for a provided symbol list."""
    if not _is_5m_backfill_enabled():
        return {
            "status": "skipped",
            "reason": "5m backfill disabled by admin toggle",
            "symbols": len(symbols or []),
            "processed": 0,
            "errors": 0,
            "provider_usage": {},
        }
    session = SessionLocal()
    loop = None
    try:
        loop = _setup_event_loop()
        processed = 0
        errors = 0
        provider_usage: Dict[str, int] = {}
        for sym in [s.upper() for s in symbols or []]:
            try:
                res = loop.run_until_complete(
                    market_data_service.backfill_intraday_5m(session, sym, lookback_days=n_days)
                )
                if (res or {}).get("status") != "empty":
                    processed += 1
                _increment_provider_usage(provider_usage, res)
            except Exception:
                errors += 1
                session.rollback()
        return {
            "status": "ok",
            "symbols": len(symbols or []),
            "processed": processed,
            "errors": errors,
            "provider_usage": provider_usage,
        }
    finally:
        session.close()
        if loop:
            loop.close()


@shared_task(name="backend.tasks.market_data_tasks.backfill_5m_last_n_days")
@task_run("backfill_5m_last_n_days")
def backfill_5m_last_n_days(n_days: int = 5, batch_size: int = 50) -> dict:
    """Backfill last N days of 5m bars for tracked universe in batches."""
    if not _is_5m_backfill_enabled():
        return {
            "status": "skipped",
            "reason": "5m backfill disabled by admin toggle",
            "symbols": 0,
            "processed": 0,
            "errors": 0,
            "provider_usage": {},
        }
    session = SessionLocal()
    loop = None
    try:
        syms = sorted(_get_tracked_universe_from_db(session))
        total = len(syms)
        done = 0
        errors = 0
        loop = _setup_event_loop()
        provider_usage: Dict[str, int] = {}
        for i in range(0, total, max(1, batch_size)):
            chunk = syms[i : i + batch_size]
            for sym in chunk:
                try:
                    res = loop.run_until_complete(
                        market_data_service.backfill_intraday_5m(session, sym, lookback_days=n_days)
                    )
                    if (res or {}).get("status") != "empty":
                        done += 1
                    _increment_provider_usage(provider_usage, res)
                except Exception:
                    errors += 1
                    session.rollback()
        return {"status": "ok", "symbols": total, "processed": done, "errors": errors, "provider_usage": provider_usage}
    finally:
        session.close()
        if loop:
            loop.close()


@shared_task(name="backend.tasks.market_data_tasks.enforce_price_data_retention")
@task_run("enforce_price_data_retention")
def enforce_price_data_retention(max_days_5m: int = 90) -> dict:
    """Delete 5m bars older than max_days_5m to control storage."""
    session = SessionLocal()
    try:
        from backend.models import PriceData
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=max_days_5m)
        deleted = (
            session.query(PriceData)
            .filter(PriceData.interval == "5m", PriceData.date < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        return {"status": "ok", "deleted": int(deleted or 0), "cutoff": cutoff.isoformat()}
    finally:
        session.close()


# ============================= Coverage instrumentation =============================


@shared_task(name="backend.tasks.market_data_tasks.monitor_coverage_health")
@task_run("monitor_coverage_health")
def monitor_coverage_health() -> dict:
    """Snapshot coverage health into Redis so the Admin UI can show stale counts."""
    session = SessionLocal()
    try:
        snapshot = market_data_service.coverage_snapshot(session)
        # Ensure status logic respects the 5m toggle (ignore-5m behavior).
        try:
            snapshot.setdefault("meta", {})["backfill_5m_enabled"] = _is_5m_backfill_enabled()
        except Exception:
            pass
        from backend.services.market.market_data_service import compute_coverage_status
        status_info = compute_coverage_status(snapshot)
        snapshot["status"] = status_info
        payload = {
            "snapshot": snapshot,
            "updated_at": datetime.utcnow().isoformat(),
            "status": status_info,
        }
        redis_client = market_data_service.redis_client
        history_entry = {
            "ts": payload["updated_at"],
            "daily_pct": status_info.get("daily_pct"),
            "m5_pct": status_info.get("m5_pct"),
            "stale_daily": status_info.get("stale_daily"),
            "stale_m5": status_info.get("stale_m5"),
            "label": status_info.get("label"),
        }
        try:
            pipe = redis_client.pipeline()
            pipe.set("coverage:health:last", json.dumps(payload), ex=86400)
            pipe.lpush("coverage:health:history", json.dumps(history_entry))
            pipe.ltrim("coverage:health:history", 0, 47)
            pipe.execute()
        except Exception:
            pass
        return {
            "status": status_info.get("label"),
            "daily_pct": status_info.get("daily_pct"),
            "m5_pct": status_info.get("m5_pct"),
            "stale_daily": status_info.get("stale_daily"),
            "stale_m5": status_info.get("stale_m5"),
            "tracked_count": snapshot.get("tracked_count", 0),
            "symbols": snapshot.get("symbols", 0),
        }
    finally:
        session.close()

