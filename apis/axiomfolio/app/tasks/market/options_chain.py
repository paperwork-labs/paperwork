"""
Celery tasks: refresh options chain snapshots for tracked names.
"""

from __future__ import annotations

import logging

from celery import shared_task

from app.database import SessionLocal
from app.services.gold.options_chain_surface import OptionsChainSurface
from app.services.silver.market.universe import tracked_symbols
from app.services.silver.market.market_data_service import infra
from app.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.market.options_chain.refresh_options_chain_for_symbol",
    soft_time_limit=55,
    time_limit=60,
)
@task_run(
    "options_chain_symbol",
    lock_key=lambda symbol, user_id, **k: f"{symbol}:{user_id}",
    lock_ttl_seconds=90,
)
def refresh_options_chain_for_symbol(symbol: str, user_id: int) -> dict:
    """Recompute and persist the options surface for one symbol (one user ctx)."""
    session = SessionLocal()
    try:
        surface = OptionsChainSurface()
        result = surface.compute(
            symbol,
            user_id,
            session=session,
        )
        return {
            "status": "ok",
            "symbol": result.symbol,
            "user_id": user_id,
            "source": result.source,
            "contracts_processed": result.contracts_processed,
            "contracts_persisted": result.contracts_persisted,
            "contracts_skipped_no_iv": result.contracts_skipped_no_iv,
            "contracts_errored": result.contracts_errored,
            "contracts_skipped_malformed": result.contracts_skipped_malformed,
            "iv_history_queries": result.iv_history_queries,
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("refresh_options_chain_for_symbol failed: %s", e)
        raise
    finally:
        session.close()


@shared_task(
    name="app.tasks.market.options_chain."
    "refresh_options_chains_for_tracked_universe",
    soft_time_limit=590,
    time_limit=600,
)
@task_run(
    "options_chain_universe",
    lock_key=lambda user_id, **k: f"u:{user_id}",
    lock_ttl_seconds=700,
)
def refresh_options_chains_for_tracked_universe(user_id: int) -> dict:
    """Enqueue one per-symbol task for the global tracked universe."""
    from app.models.user import User

    db = SessionLocal()
    enq = 0
    try:
        user = db.get(User, int(user_id))
        if not user:
            return {"status": "error", "error": "user not found", "user_id": user_id}
        syms = tracked_symbols(db, redis_client=infra.redis_client)
        for s in syms:
            if not s:
                continue
            refresh_options_chain_for_symbol.delay(str(s), int(user_id))
            enq += 1
        return {"status": "ok", "user_id": user_id, "enqueued": enq}
    finally:
        db.close()
