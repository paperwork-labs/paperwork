"""
Daily Celery task: backfill TradeDecisionExplanation rows.

Runs once per day (job_catalog: ``explain_recent_trades`` @ 04:30 UTC).
Walks every executed order from the past ``lookback_hours`` (default 24)
and runs the explainer on the orders that don't yet have an
explanation row.

Idempotency
-----------

The "already has a row" check is done per-order before invoking the
explainer, so re-running the task is safe and cheap. We never call the
LLM for an order that has *any* persisted version row -- regenerate is
an explicit user action, not a backfill behavior.

Failure model
-------------

Per-order errors are caught and counted, never re-raised. The task
returns a structured counter dict (``{"considered", "explained",
"skipped_cached", "failed"}``) and the assertion ``considered ==
explained + skipped_cached + failed`` holds. This satisfies the
no-silent-fallback rule: counter drift is logged loudly so an operator
notices when the explainer is silently dropping orders.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Order, TradeDecisionExplanation
from app.services.agent.trade_decision_explainer import (
    OrderNotFoundError,
    TradeDecisionExplainer,
    TradeDecisionExplainerError,
)
from app.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


# Order statuses that count as "executed" for the purpose of explaining
# why a trade happened. Cancelled / rejected / preview rows have no
# trade decision to explain.
_EXECUTED_STATUSES = ("filled", "partially_filled")


def _filled_window_filter(since: datetime):
    """Build the SQLAlchemy filter for "filled inside the lookback".

    We accept ``filled_at`` (post-fill) OR ``submitted_at`` (in case the
    fill timestamp is missing) so a partially-filled order with NULL
    ``filled_at`` doesn't fall through the cracks. The status filter
    above guarantees we don't pick up unfilled rows.
    """
    return or_(
        Order.filled_at >= since,
        Order.submitted_at >= since,
    )


def _has_explanation(db: Session, order_id: int) -> bool:
    return (
        db.query(TradeDecisionExplanation.id)
        .filter(TradeDecisionExplanation.order_id == order_id)
        .first()
        is not None
    )


def _run_backfill(
    *,
    lookback_hours: int = 24,
    explainer: TradeDecisionExplainer | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Pure function so the Celery task and tests share one code path.

    Caller may pass ``db`` to drive the function inside an existing
    test transaction; otherwise a new session is opened and committed
    per order so a single bad order can't poison the rest of the batch.
    """
    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")

    own_session = db is None
    session = db or SessionLocal()
    explainer = explainer or TradeDecisionExplainer()

    since = datetime.now(UTC) - timedelta(hours=lookback_hours)

    counters = {
        "considered": 0,
        "explained": 0,
        "skipped_cached": 0,
        "skipped_no_user": 0,
        "failed": 0,
    }

    try:
        orders = (
            session.query(Order)
            .filter(Order.status.in_(_EXECUTED_STATUSES))
            .filter(_filled_window_filter(since))
            .order_by(Order.id.asc())
            .all()
        )
        counters["considered"] = len(orders)

        for order in orders:
            if order.user_id is None:
                # No tenant -> no per-user explanation possible.
                # Counted explicitly so cross-tenant gap shows up in
                # ops counters rather than disappearing silently.
                counters["skipped_no_user"] += 1
                continue
            if _has_explanation(session, order.id):
                counters["skipped_cached"] += 1
                continue
            try:
                explainer.explain(session, order_id=order.id, user_id=order.user_id)
                if own_session:
                    session.commit()
                counters["explained"] += 1
            except OrderNotFoundError:
                # Race: order was deleted between query and explain.
                counters["failed"] += 1
                if own_session:
                    session.rollback()
            except TradeDecisionExplainerError as e:
                counters["failed"] += 1
                if own_session:
                    session.rollback()
                logger.warning(
                    "explain_recent_trades: explainer failed for order=%s user=%s: %s",
                    order.id,
                    order.user_id,
                    e,
                )
            except Exception as e:
                counters["failed"] += 1
                if own_session:
                    session.rollback()
                logger.exception(
                    "explain_recent_trades: unexpected error for order=%s user=%s: %s",
                    order.id,
                    order.user_id,
                    e,
                )
    finally:
        if own_session:
            session.close()

    summed = (
        counters["explained"]
        + counters["skipped_cached"]
        + counters["skipped_no_user"]
        + counters["failed"]
    )
    if summed != counters["considered"]:
        # Per the engineering rules, a per-symbol loop must sum
        # cleanly. If it doesn't, we want to see it loudly in the logs
        # rather than have it disappear into the cracks of "well, the
        # task succeeded so it must be fine".
        logger.error(
            "explain_recent_trades counter drift: considered=%s "
            "explained=%s skipped_cached=%s skipped_no_user=%s failed=%s",
            counters["considered"],
            counters["explained"],
            counters["skipped_cached"],
            counters["skipped_no_user"],
            counters["failed"],
        )

    logger.info(
        "explain_recent_trades: lookback_hours=%s considered=%s "
        "explained=%s skipped_cached=%s skipped_no_user=%s failed=%s",
        lookback_hours,
        counters["considered"],
        counters["explained"],
        counters["skipped_cached"],
        counters["skipped_no_user"],
        counters["failed"],
    )
    return {"lookback_hours": lookback_hours, **counters}


@shared_task(
    name="app.tasks.agent.explain_recent_trades.explain_recent_trades",
    soft_time_limit=870,
    time_limit=900,
    autoretry_for=(),
)
@task_run("explain_recent_trades")
def explain_recent_trades(lookback_hours: int = 24) -> dict[str, Any]:
    """Celery entry point — wraps :func:`_run_backfill`.

    ``time_limit`` matches the catalog's ``timeout_s=900`` per the
    iron law in :mod:`app.tasks.job_catalog`.
    """
    return _run_backfill(lookback_hours=lookback_hours)


__all__ = ["_run_backfill", "explain_recent_trades"]
