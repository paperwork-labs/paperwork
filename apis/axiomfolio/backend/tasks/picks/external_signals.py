"""Celery: aggregate auxiliary external signals (Finviz/Zacks stubs)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from backend.config import settings
from backend.database import SessionLocal
from backend.services.signals.external_aggregator import (
    fetch_finviz_signals,
    fetch_zacks_signals,
    persist_signals,
)
from backend.tasks.celery_app import celery_app
from backend.tasks.utils.task_utils import get_tracked_symbols_safe, task_run

logger = logging.getLogger(__name__)


@celery_app.task(
    name="backend.tasks.picks.aggregate_external_signals",
    soft_time_limit=840,
    time_limit=900,
    queue="celery",
)
@task_run("aggregate_external_signals", lock_ttl_seconds=960)
def aggregate_external_signals_task() -> Dict[str, Any]:
    """Daily: fetch stubbed external signals for the tracked universe and upsert."""
    if not settings.ENABLE_EXTERNAL_SIGNALS:
        logger.info("aggregate_external_signals: disabled (ENABLE_EXTERNAL_SIGNALS=false)")
        return {
            "status": "disabled",
            "written": 0,
            "symbols": 0,
        }

    db = SessionLocal()
    try:
        symbols = get_tracked_symbols_safe(db)
        if not symbols:
            logger.warning("aggregate_external_signals: no tracked symbols")
            return {
                "status": "ok",
                "written": 0,
                "symbols": 0,
            }

        batch = []
        batch.extend(fetch_finviz_signals(symbols))
        batch.extend(fetch_zacks_signals(symbols))
        written = persist_signals(db, batch)
        db.commit()
        logger.info(
            "aggregate_external_signals: written=%s symbols=%s",
            written,
            len(symbols),
        )
        return {
            "status": "ok",
            "written": written,
            "symbols": len(symbols),
        }
    except Exception:
        db.rollback()
        logger.exception("aggregate_external_signals failed")
        raise
    finally:
        db.close()
