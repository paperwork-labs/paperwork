"""Celery fan-out for E*TRADE account sync.

Mirrors the ``sync_all_schwab_accounts`` / ``sync_all_ibkr_accounts`` tasks
defined in ``app/tasks/portfolio/sync.py``: walks every
``is_enabled=True`` E*TRADE account, enqueues a
``sync_account_task(account.id, "comprehensive")`` for each, and returns a
summary. The per-account task handles Redis locking, status updates, and
routes into :class:`app.services.bronze.etrade.ETradeSyncService` via
the generic ``BrokerSyncService`` dispatcher.

Why its own module? Each broker fan-out lives in its own file so future
broker additions drop in alongside without touching ``sync.py``.
Pre-existing Schwab / IBKR fan-outs stay in ``sync.py`` — no big-bang
rename (decision D127).

Timing contract — the authoritative values live here and in
``job_catalog.py``. PR descriptions and runbooks must quote these, not
the other way around:

* ``time_limit=960`` and ``soft_time_limit=900`` match
  :data:`app.tasks.portfolio.sync.sync_account_task` hard/soft limits;
  this task only enqueues children so it's effectively instant, but we
  declare explicit limits to satisfy the engineering rule ("all Celery
  tasks must set explicit time_limit and soft_time_limit").
* Beat entry (``etrade-daily-sync`` in :data:`app.tasks.job_catalog.CATALOG`)
  declares ``timeout_s=960`` (iron-law: Beat ``timeout_s`` == task
  ``time_limit``) and runs at 02:45 UTC daily, staggered after the IBKR
  (02:15) and Schwab (02:30) fan-outs so worker pressure spreads evenly.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.database import SessionLocal
from app.models.broker_account import BrokerAccount, BrokerType

logger = logging.getLogger(__name__)


# Hard upper bound for the fan-out. Must be >= the Beat timeout_s declared
# in job_catalog.py for the matching entry (enforced implicitly — Celery
# kills the task at time_limit regardless of the scheduler). Children use
# their own time_limit (see sync.sync_account_task).
_TIME_LIMIT = 960
_SOFT_TIME_LIMIT = 900


@shared_task(
    name="app.tasks.account_sync.sync_all_etrade_accounts",
    soft_time_limit=_SOFT_TIME_LIMIT,
    time_limit=_TIME_LIMIT,
)
def sync_all_etrade_accounts() -> dict[str, Any]:
    """Enqueue per-account sync tasks for every enabled E*TRADE account.

    Multi-tenancy: we never carry a ``user_id`` parameter here (the Beat
    scheduler doesn't know about users). Each enqueued child task
    (``sync_account_task``) loads the account by id and the downstream
    :class:`ETradeSyncService` filters every DB query by
    ``account.user_id`` / broker — cross-tenant isolation is pinned by
    ``backend/tests/services/bronze/etrade/test_sync_service_isolation.py``.
    """

    session = SessionLocal()
    try:
        accounts = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.broker == BrokerType.ETRADE,
                BrokerAccount.is_enabled.is_(True),
            )
            .all()
        )
        enqueued = 0
        errors = 0
        results: list[dict[str, Any]] = []
        for acct in accounts:
            try:
                # Import here to keep module import cheap for Beat/worker
                # bootstrap (Celery app import cost is measurable).
                from app.tasks.celery_app import celery_app

                task = celery_app.send_task(
                    "app.tasks.account_sync.sync_account_task",
                    args=[acct.id, "comprehensive"],
                )
                results.append({"account_id": acct.id, "user_id": acct.user_id, "task_id": task.id})
                enqueued += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    "etrade fan-out: failed to enqueue sync for account %s (user %s): %s",
                    acct.id,
                    acct.user_id,
                    exc,
                )
                results.append({"account_id": acct.id, "user_id": acct.user_id, "error": str(exc)})

        # Structured counter logging per no-silent-fallback rule.
        logger.info(
            "etrade fan-out: total=%d enqueued=%d errors=%d",
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


__all__ = ["sync_all_etrade_accounts"]
