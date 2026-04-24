"""Daily Plaid Investments sync task.

Scheduled at 05:00 UTC by ``backend/tasks/job_catalog.py`` entry
``plaid_daily_sync`` (queue ``heavy``, timeout 660s matching
``hard_time_limit`` per IRON LAW in ``AGENTS.md``).

Per-connection outcomes:

* ``written``            — one or more holdings synced successfully.
* ``skipped_no_holdings``— connection returned zero investable holdings
  (still counted as a "seen" connection; NOT an error).
* ``errors``             — transient failure (Plaid 5xx, rate limit,
  counter drift, DB commit failure). Exception is logged + the row's
  ``last_error`` persisted; the task never ``except Exception: pass``.

The loop asserts ``written + skipped_no_holdings + errors == total`` so
counter drift raises loudly (R32, no-silent-fallback).

Re-auth states (``needs_reauth``) are counted under ``skipped_no_holdings``
for the run-level counter because the task itself didn't fail — the user
must act. The admin health dimension surfaces them separately.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from celery import shared_task

from backend.database import SessionLocal
from backend.models.broker_account import BrokerAccount
from backend.models.plaid_connection import (
    PlaidConnection,
    PlaidConnectionStatus,
)
from backend.services.portfolio.plaid.sync_service import PlaidSyncService
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


def _sync_one_connection(
    session, connection: PlaidConnection, service: PlaidSyncService
) -> str:
    """Sync every Plaid-sourced account linked to one connection.

    Returns one of ``"written"`` / ``"skipped_no_holdings"`` / ``"errors"``.

    A connection with no Plaid-sourced BrokerAccount rows is counted as
    ``skipped_no_holdings`` — the Item exists at Plaid but we have
    nothing to sync (user disabled all accounts locally).
    """
    if connection.status == PlaidConnectionStatus.NEEDS_REAUTH.value:
        logger.info(
            "plaid_daily_sync: skipping user_id=%s conn_id=%s status=needs_reauth",
            connection.user_id,
            connection.id,
        )
        return "skipped_no_holdings"

    accounts: List[BrokerAccount] = (
        session.query(BrokerAccount)
        .filter(
            BrokerAccount.user_id == connection.user_id,
            BrokerAccount.connection_source == "plaid",
            BrokerAccount.is_enabled.is_(True),
        )
        .all()
    )
    if not accounts:
        return "skipped_no_holdings"

    any_success = False
    any_error = False
    for account in accounts:
        try:
            result = service.sync_account_comprehensive(
                account.account_number,
                session,
                user_id=connection.user_id,
            )
        except AssertionError:
            # Counter drift inside persist_holdings — abort loudly.
            raise
        except Exception as exc:  # noqa: BLE001 - structured counter loop
            logger.warning(
                "plaid_daily_sync: unexpected error user_id=%s "
                "account_id=%s: %s",
                connection.user_id,
                account.id,
                exc,
            )
            any_error = True
            continue

        status = str(result.get("status") or "").lower()
        if status == "success":
            any_success = True
        elif status == "partial":
            any_success = True
            any_error = True
        else:
            any_error = True

    if any_error and not any_success:
        return "errors"
    if any_success:
        return "written"
    return "skipped_no_holdings"


@shared_task(
    name="backend.tasks.portfolio.plaid_sync.daily_sync",
    soft_time_limit=600,
    time_limit=660,
    bind=False,
)
@task_run("plaid_daily_sync")
def daily_sync() -> Dict[str, int]:
    """Sync every active Plaid connection (run by Beat at 05:00 UTC).

    Returns a counter dict so ``task_run`` can persist it to JobRun +
    ``taskstatus:plaid_daily_sync:last`` for the admin health dimension.
    """
    counters: Dict[str, int] = {
        "total": 0,
        "written": 0,
        "skipped_no_holdings": 0,
        "errors": 0,
    }

    service = PlaidSyncService()
    session = SessionLocal()
    try:
        connections: List[PlaidConnection] = (
            session.query(PlaidConnection)
            .filter(
                PlaidConnection.status.in_(
                    [
                        PlaidConnectionStatus.ACTIVE.value,
                        PlaidConnectionStatus.ERROR.value,
                    ]
                )
            )
            .all()
        )
        counters["total"] = len(connections)

        for conn in connections:
            try:
                outcome = _sync_one_connection(session, conn, service)
            except Exception as exc:  # noqa: BLE001 - structured counter loop
                logger.exception(
                    "plaid_daily_sync: per-connection loop error user_id=%s "
                    "conn_id=%s",
                    conn.user_id,
                    conn.id,
                )
                conn.mark_error(f"{type(exc).__name__}: {exc}")
                try:
                    session.commit()
                except Exception:
                    session.rollback()
                counters["errors"] += 1
                continue

            try:
                session.commit()
            except Exception as commit_exc:
                logger.exception(
                    "plaid_daily_sync: commit failed user_id=%s conn_id=%s",
                    conn.user_id,
                    conn.id,
                )
                session.rollback()
                # If we thought we wrote, re-bucket as error to keep
                # the counters honest.
                if outcome == "written":
                    counters["errors"] += 1
                elif outcome == "skipped_no_holdings":
                    counters["skipped_no_holdings"] += 1
                else:
                    counters[outcome] = counters.get(outcome, 0) + 1
                continue

            counters[outcome] = counters.get(outcome, 0) + 1

        assert (
            counters["written"]
            + counters["skipped_no_holdings"]
            + counters["errors"]
            == counters["total"]
        ), f"plaid_daily_sync counter drift: {counters}"

        logger.info(
            "plaid_daily_sync complete total=%d written=%d "
            "skipped_no_holdings=%d errors=%d",
            counters["total"],
            counters["written"],
            counters["skipped_no_holdings"],
            counters["errors"],
        )
        return counters
    finally:
        session.close()


__all__ = ["daily_sync", "_sync_one_connection"]
