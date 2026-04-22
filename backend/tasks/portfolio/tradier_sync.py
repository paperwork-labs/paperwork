"""Celery fan-out for Tradier account sync (live and sandbox account rows).

Mirrors :mod:`backend.tasks.portfolio.etrade_sync` — walks every
``is_enabled=True`` Tradier or Tradier sandbox account, enqueues
``sync_account_task(account.id, "comprehensive")`` for each, and returns a
summary. The per-account task handles Redis locking, status updates, and
routes into :class:`backend.services.bronze.tradier.TradierSyncService`
via the generic ``BrokerSyncService`` dispatcher.

``time_limit=960`` / ``soft_time_limit=900`` match
``job_catalog`` ``timeout_s=960`` (iron law). Kept in its own module so
per-broker fan-outs stay separate.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from celery import shared_task

from backend.database import SessionLocal
from backend.models.broker_account import BrokerAccount, BrokerType

logger = logging.getLogger(__name__)


# Hard upper bound for the fan-out. Must equal the Beat ``timeout_s``
# declared in ``job_catalog.py`` for the matching entry (iron law:
# ``time_limit == job_catalog.timeout_s``). Children use their own
# time_limit (see ``sync.sync_account_task``).
_TIME_LIMIT = 960
_SOFT_TIME_LIMIT = 900


@shared_task(
    name="backend.tasks.account_sync.sync_all_tradier_accounts",
    soft_time_limit=_SOFT_TIME_LIMIT,
    time_limit=_TIME_LIMIT,
)
def sync_all_tradier_accounts() -> Dict[str, Any]:
    """Enqueue per-account sync tasks for every enabled Tradier account.

    Multi-tenancy: we never carry a ``user_id`` parameter here (Beat
    doesn't know about users). Each enqueued child task
    (``sync_account_task``) loads the account by id and the downstream
    :class:`TradierSyncService` filters every DB query by
    ``account.user_id`` / broker — cross-tenant isolation is pinned by
    ``backend/tests/services/bronze/tradier/test_sync_service_isolation.py``.
    """

    session = SessionLocal()
    try:
        accounts = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.broker.in_(
                    (BrokerType.TRADIER, BrokerType.TRADIER_SANDBOX)
                ),
                BrokerAccount.is_enabled.is_(True),
            )
            .all()
        )
        enqueued = 0
        errors = 0
        results: List[Dict[str, Any]] = []
        for acct in accounts:
            try:
                # Import here to keep module import cheap for Beat/worker
                # bootstrap (Celery app import cost is measurable).
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
            except Exception as exc:  # noqa: BLE001 — per-account isolation
                errors += 1
                logger.warning(
                    "tradier fan-out: failed to enqueue sync for account %s "
                    "(user %s): %s",
                    acct.id, acct.user_id, exc,
                )
                results.append(
                    {
                        "account_id": acct.id,
                        "user_id": acct.user_id,
                        "error": str(exc),
                    }
                )

        # Structured counter logging per no-silent-fallback rule.
        logger.info(
            "tradier fan-out: total=%d enqueued=%d errors=%d",
            len(accounts), enqueued, errors,
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


__all__ = ["sync_all_tradier_accounts"]
