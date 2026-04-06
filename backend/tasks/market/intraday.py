"""
Five-minute intraday bar backfill tasks.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from celery import shared_task

from backend.database import SessionLocal
from backend.services.market.market_data_service import market_data_service
from backend.tasks.utils.task_utils import (
    _get_tracked_universe_from_db,
    _increment_provider_usage,
    setup_event_loop as _setup_event_loop,
    task_run,
)

logger = logging.getLogger(__name__)

_DEFAULT_SOFT = 3500
_DEFAULT_HARD = 3600


@shared_task(
    soft_time_limit=1800,
    time_limit=2100,
)
@task_run("admin_backfill_5m_symbols")
def bars_5m_symbols(symbols: List[str], n_days: int = 5) -> dict:
    """Delta backfill last N days of 5m bars for a provided symbol list."""
    if not market_data_service.coverage.is_backfill_5m_enabled():
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
                    market_data_service.backfill_intraday_5m(
                        session, sym, lookback_days=n_days
                    )
                )
                if (res or {}).get("status") != "empty":
                    processed += 1
                _increment_provider_usage(provider_usage, res)
            except Exception as e:
                errors += 1
                session.rollback()
                logger.warning("5m backfill failed for %s: %s", sym, e)
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
    soft_time_limit=1800,
    time_limit=2100,
)
@task_run("admin_backfill_5m")
def bars_5m_last_n_days(n_days: int = 5, batch_size: int = 50) -> dict:
    """Backfill last N days of 5m bars for tracked universe in batches."""
    if not market_data_service.coverage.is_backfill_5m_enabled():
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
                        market_data_service.backfill_intraday_5m(
                            session, sym, lookback_days=n_days
                        )
                    )
                    if (res or {}).get("status") != "empty":
                        done += 1
                    _increment_provider_usage(provider_usage, res)
                except Exception as e:
                    errors += 1
                    session.rollback()
                    logger.warning("5m backfill failed for %s: %s", sym, e)
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
