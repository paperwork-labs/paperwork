"""
Five-minute intraday bar backfill tasks.
"""

from __future__ import annotations

import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from app.database import SessionLocal
from app.services.market.fmp_5m_tier_gate import (
    fmp_5m_intraday_backfill_blocked_tier,
    log_skip_intraday_5m_backfill,
)
from app.services.market.market_data_service import infra, price_bars, provider_router
from app.tasks.utils.task_utils import (
    _get_tracked_universe_from_db,
    _increment_provider_usage,
    task_run,
)
from app.tasks.utils.task_utils import (
    setup_event_loop as _setup_event_loop,
)

logger = logging.getLogger(__name__)

_DEFAULT_SOFT = 3500
_DEFAULT_HARD = 3600


@shared_task(
    soft_time_limit=1800,
    time_limit=2100,
)
@task_run("admin_backfill_5m_symbols")
def bars_5m_symbols(symbols: list[str], n_days: int = 5) -> dict:
    """Delta backfill last N days of 5m bars for a provided symbol list."""
    blocked_tier = fmp_5m_intraday_backfill_blocked_tier()
    if blocked_tier is not None:
        log_skip_intraday_5m_backfill(blocked_tier)
        return {
            "status": "skipped",
            "reason": "tier_insufficient",
            "symbols": len(symbols or []),
            "processed": 0,
            "errors": 0,
            "provider_usage": {},
        }
    if not infra.is_backfill_5m_enabled():
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
        provider_usage: dict[str, int] = {}
        try:
            for sym in [s.upper() for s in symbols or []]:
                try:
                    res = loop.run_until_complete(
                        price_bars.backfill_intraday_5m(
                            session,
                            sym,
                            lookback_days=n_days,
                            provider=provider_router,
                        )
                    )
                    if (res or {}).get("status") != "empty":
                        processed += 1
                    _increment_provider_usage(provider_usage, res)
                except SoftTimeLimitExceeded:
                    raise
                except Exception as e:
                    errors += 1
                    session.rollback()
                    logger.warning("5m backfill failed for %s: %s", sym, e)
        except SoftTimeLimitExceeded:
            logger.warning(
                "bars_5m_symbols hit soft time limit after processing %d symbols",
                processed,
            )
            try:
                session.commit()
            except Exception as ce:
                logger.warning(
                    "bars_5m_symbols partial commit after soft limit failed: %s",
                    ce,
                    exc_info=True,
                )
                session.rollback()
            return {
                "status": "partial",
                "symbols": len(symbols or []),
                "processed": processed,
                "errors": errors,
                "provider_usage": provider_usage,
            }
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


@shared_task(
    soft_time_limit=1740,
    time_limit=1800,
)
@task_run("admin_backfill_5m")
def bars_5m_last_n_days(n_days: int = 5, batch_size: int = 50) -> dict:
    """Backfill last N days of 5m bars for tracked universe in batches."""
    blocked_tier = fmp_5m_intraday_backfill_blocked_tier()
    if blocked_tier is not None:
        log_skip_intraday_5m_backfill(blocked_tier)
        return {
            "status": "skipped",
            "reason": "tier_insufficient",
            "symbols": 0,
            "processed": 0,
            "errors": 0,
            "provider_usage": {},
        }
    if not infra.is_backfill_5m_enabled():
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
        provider_usage: dict[str, int] = {}
        try:
            for i in range(0, total, max(1, batch_size)):
                chunk = syms[i : i + batch_size]
                for sym in chunk:
                    try:
                        res = loop.run_until_complete(
                            price_bars.backfill_intraday_5m(
                                session,
                                sym,
                                lookback_days=n_days,
                                provider=provider_router,
                            )
                        )
                        if (res or {}).get("status") != "empty":
                            done += 1
                        _increment_provider_usage(provider_usage, res)
                    except SoftTimeLimitExceeded:
                        raise
                    except Exception as e:
                        errors += 1
                        session.rollback()
                        logger.warning("5m backfill failed for %s: %s", sym, e)
        except SoftTimeLimitExceeded:
            logger.warning(
                "bars_5m_last_n_days hit soft time limit after processing %d symbols",
                done,
            )
            try:
                session.commit()
            except Exception as ce:
                logger.warning(
                    "bars_5m_last_n_days partial commit after soft limit failed: %s",
                    ce,
                    exc_info=True,
                )
                session.rollback()
            return {
                "status": "partial",
                "symbols": total,
                "processed": done,
                "errors": errors,
                "provider_usage": provider_usage,
            }
        return {
            "status": "ok",
            "symbols": total,
            "processed": done,
            "errors": errors,
            "provider_usage": provider_usage,
        }
    finally:
        session.close()
        if loop:
            loop.close()
