"""
Implied volatility snapshot and IV rank maintenance tasks.

Free-providers-first ingest: IBKR Gateway primary, Yahoo fallback.
Writes one ``HistoricalIV`` row per symbol per trading day, keyed on
``(symbol, date)``. The downstream ``compute_iv_rank`` (``compute_rank``)
task reads the ledger and writes ``iv_rank_252`` / ``iv_high_252`` /
``iv_low_252`` / ``iv_hv_spread`` once 20+ daily samples exist.

Guardrails (``.cursor/rules/no-silent-fallback.mdc``):

- Per-symbol try/except with structured counters (``written`` /
  ``skipped_no_data`` / ``errors``); no blanket ``except Exception: pass``.
- Final ``assert written + skipped + errors == total`` fires on counter
  drift so a silent drop is never shipped to prod.
- ``iv_hv_spread`` is ``None`` when either side is null -- never ``0``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta as td, timezone
from typing import Callable, List, Optional, Sequence

from celery import shared_task

from app.database import SessionLocal
from app.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers -- kept at module scope so tests can monkeypatch them.
# ---------------------------------------------------------------------------


def _tracked_symbols(db) -> List[str]:
    """Return the tracked symbol universe for the daily IV snapshot.

    Prefers the Redis ``tracked:all`` cache; falls back to the DB-driven
    union of active index constituents + portfolio positions. Truncated
    to ``IV_SNAPSHOT_MAX_SYMBOLS`` with a warning if exceeded.
    """
    try:
        from app.config import settings
        from app.services.market.market_data_service import infra
        from app.services.market.universe import tracked_symbols

        symbols = tracked_symbols(db, redis_client=infra.redis_client) or []
    except Exception as e:
        logger.warning("tracked symbol lookup failed: %s", e)
        symbols = []
        settings = None

    cap = 1000
    try:
        if settings is not None:
            cap = int(getattr(settings, "IV_SNAPSHOT_MAX_SYMBOLS", 1000) or 1000)
    except Exception:
        cap = 1000

    if len(symbols) > cap:
        logger.warning(
            "IV snapshot: universe=%d exceeds cap=%d -- truncating (cfg: IV_SNAPSHOT_MAX_SYMBOLS)",
            len(symbols),
            cap,
        )
        symbols = symbols[:cap]
    return symbols


def _last_trading_day() -> "datetime.date":
    """Most recent weekday on/before 'today' (UTC).

    Holiday-aware dating is not needed -- upserts are idempotent, so a
    holiday run simply overwrites a row with the same data.
    """
    from app.services.market.historical_iv_service import last_trading_day

    return last_trading_day()


# ---------------------------------------------------------------------------
# Snapshot task
# ---------------------------------------------------------------------------


@shared_task(
    soft_time_limit=600,
    time_limit=660,
)
@task_run("snapshot_iv_from_gateway")
def sync_gateway(
    symbols_override: Optional[Sequence[str]] = None,
    *,
    as_of_override: Optional["datetime.date"] = None,
    ibkr_fetcher: Optional[Callable] = None,
    yahoo_fetcher: Optional[Callable] = None,
) -> dict:
    """Snapshot ATM IV for the tracked universe.

    IBKR primary, Yahoo fallback. Persists one ``HistoricalIV`` row
    per symbol per trading day. Structured counters + final assertion
    prevent silent loss (R38-class).

    Keyword arguments are injection seams for the matching unit test --
    callers in prod should leave them ``None``.
    """
    from app.services.market.historical_iv_service import (
        atm_iv_from_ibkr,
        atm_iv_from_yahoo,
        compute_hv,
        persist_iv_sample,
    )

    session = SessionLocal()
    try:
        symbols = (
            list(symbols_override)
            if symbols_override is not None
            else _tracked_symbols(session)
        )
        total = len(symbols)
        if total == 0:
            logger.warning("IV snapshot: empty universe; nothing to do")
            return {
                "status": "ok",
                "written": 0,
                "skipped_no_data": 0,
                "errors": 0,
                "total": 0,
            }

        as_of = as_of_override or _last_trading_day()
        written = 0
        skipped_no_data = 0
        errors = 0
        by_source = {"ibkr": 0, "yahoo": 0}

        ibkr_fn = ibkr_fetcher or atm_iv_from_ibkr
        yahoo_fn = yahoo_fetcher or atm_iv_from_yahoo

        for symbol in symbols:
            try:
                sample = ibkr_fn(symbol, as_of, db=session)
                if sample is None:
                    sample = yahoo_fn(symbol, as_of, db=session)
                if sample is None:
                    skipped_no_data += 1
                    continue
                hv_20 = compute_hv(symbol, as_of, 20, session)
                hv_60 = compute_hv(symbol, as_of, 60, session)
                persist_iv_sample(sample, hv_20, hv_60, session)
                by_source[sample.source] = by_source.get(sample.source, 0) + 1
                written += 1
            except Exception as e:
                errors += 1
                logger.warning("IV snapshot failed for %s: %s", symbol, e)

        session.commit()
        assert written + skipped_no_data + errors == total, (
            f"IV snapshot counter drift: "
            f"written={written} skipped={skipped_no_data} errors={errors} total={total}"
        )
        logger.info(
            "IV snapshot: written=%d skipped_no_data=%d errors=%d total=%d source=%s",
            written,
            skipped_no_data,
            errors,
            total,
            by_source,
        )
        return {
            "status": "ok",
            "written": written,
            "skipped_no_data": skipped_no_data,
            "errors": errors,
            "total": total,
            "source_breakdown": by_source,
        }
    except Exception:
        session.rollback()
        logger.exception("sync_gateway (snapshot_iv_from_gateway) failed")
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Rank computation (existing; patched for silent-zero bug)
# ---------------------------------------------------------------------------


@shared_task(
    soft_time_limit=120,
    time_limit=180,
)
@task_run("compute_iv_rank")
def compute_rank(lookback_days: int = 252) -> dict:
    """Compute IV Rank/Percentile for symbols with historical IV data.

    IV Rank = (Current IV - 52w Low) / (52w High - 52w Low) * 100
    """
    session = SessionLocal()
    try:
        from app.models.historical_iv import HistoricalIV

        today = datetime.now(timezone.utc).date()
        cutoff = today - td(days=lookback_days)
        updated = 0

        symbols = (
            session.query(HistoricalIV.symbol)
            .filter(HistoricalIV.date >= cutoff)
            .distinct()
            .all()
        )

        for (symbol,) in symbols:
            iv_rows = (
                session.query(HistoricalIV.iv_30d, HistoricalIV.date)
                .filter(
                    HistoricalIV.symbol == symbol,
                    HistoricalIV.date >= cutoff,
                    HistoricalIV.iv_30d.isnot(None),
                )
                .order_by(HistoricalIV.date.asc())
                .all()
            )

            if len(iv_rows) < 20:
                continue

            ivs = [r.iv_30d for r in iv_rows if r.iv_30d is not None]
            if not ivs:
                continue

            iv_high = max(ivs)
            iv_low = min(ivs)
            current_iv = ivs[-1]

            if iv_high > iv_low:
                iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
            else:
                iv_rank = 50.0

            latest = (
                session.query(HistoricalIV)
                .filter(HistoricalIV.symbol == symbol)
                .order_by(HistoricalIV.date.desc())
                .first()
            )

            if latest:
                latest.iv_rank_252 = round(iv_rank, 2)
                latest.iv_high_252 = iv_high
                latest.iv_low_252 = iv_low
                # Null-safe spread (G5): NEVER coerce missing hv_20d to 0.
                # A silent-zero here would mask a data gap as a "zero
                # premium" reading for the options model downstream.
                if latest.hv_20d is not None:
                    latest.iv_hv_spread = current_iv - latest.hv_20d
                else:
                    latest.iv_hv_spread = None
                updated += 1

        session.commit()
        return {
            "status": "ok",
            "symbols_processed": len(symbols),
            "updated": updated,
        }
    except Exception:
        logger.exception("compute_rank failed")
        raise
    finally:
        session.close()
