"""Celery fan-out for Coinbase account sync.

``time_limit`` / ``soft_time_limit`` match ``job_catalog`` ``timeout_s=960``
for ``coinbase-daily-sync`` (iron law).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from celery import shared_task

from backend.database import SessionLocal
from backend.models.broker_account import BrokerAccount, BrokerType

logger = logging.getLogger(__name__)

_TIME_LIMIT = 960
_SOFT_TIME_LIMIT = 900


@shared_task(
    name="backend.tasks.account_sync.sync_all_coinbase_accounts",
    soft_time_limit=_SOFT_TIME_LIMIT,
    time_limit=_TIME_LIMIT,
)
def sync_all_coinbase_accounts() -> Dict[str, Any]:
    """Enqueue per-account comprehensive sync for every enabled Coinbase row."""

    session = SessionLocal()
    try:
        accounts = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.broker == BrokerType.COINBASE,
                BrokerAccount.is_enabled.is_(True),
            )
            .all()
        )
        enqueued = 0
        errors = 0
        results: List[Dict[str, Any]] = []
        for acct in accounts:
            try:
                from backend.tasks.celery_app import celery_app

                task = celery_app.send_task(
                    "backend.tasks.account_sync.sync_account_task",
                    args=[acct.id, "comprehensive"],
                )
                results.append(
                    {
                        "account_id": acct.id,
                        "user_id": acct.user_id,
                        "task_id": task.id,
                    }
                )
                enqueued += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.warning(
                    "coinbase fan-out: enqueue failed account %s user %s: %s",
                    acct.id,
                    acct.user_id,
                    exc,
                )
                results.append(
                    {
                        "account_id": acct.id,
                        "user_id": acct.user_id,
                        "error": str(exc),
                    }
                )

        logger.info(
            "coinbase fan-out: total=%d enqueued=%d errors=%d",
            len(accounts),
            enqueued,
            errors,
        )
        return {
            "status": "queued",
            "total": len(accounts),
            "enqueued": enqueued,
            "errors": errors,
            "results": results,
        }
    finally:
        session.close()


__all__ = ["sync_all_coinbase_accounts"]
