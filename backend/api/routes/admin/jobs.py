"""Admin ad-hoc job triggers.

Unlike :mod:`backend.api.routes.admin.scheduler` which manages the cron
catalog, these endpoints fire one-off background jobs (backfills,
reconciliation replays, etc.) that operators need to kick off manually.

All endpoints are admin-only and push the actual work to Celery via
``celery_app.send_task`` — callers get a 202-style envelope with the
task id and can poll ``JobRun`` for status.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.api.dependencies import get_admin_user
from backend.api.rate_limit import limiter
from backend.models.user import User
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter()


class BackfillOptionTaxLotsRequest(BaseModel):
    """Request payload for the option tax lots backfill.

    ``user_id`` is optional — when omitted, the backfill runs across every
    enabled broker account (all users). The endpoint deliberately does
    NOT accept a ``broker`` filter: the backfill is broker-agnostic by
    design so the Tax Center lights up for IBKR, Schwab, Tastytrade,
    E*TRADE, and every broker we add later without per-broker branches
    (``broker-agnostic.mdc``).
    """

    user_id: Optional[int] = Field(
        default=None,
        description=(
            "Restrict the backfill to one user. Omit to run across all "
            "enabled broker accounts (cross-tenant, admin-only)."
        ),
    )


@router.post("/jobs/backfill-option-tax-lots")
@limiter.limit("5/minute")
async def trigger_backfill_option_tax_lots(
    request: Request,
    payload: BackfillOptionTaxLotsRequest = BackfillOptionTaxLotsRequest(),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Enqueue the FIFO closing-lot matcher across enabled accounts.

    Produces ``OptionTaxLot`` rows and equity ``CLOSED_LOT`` trades from
    existing ``trades`` history — idempotent. Use this once after a
    matcher-related deploy so the Tax Center populates without waiting
    for the next broker sync cycle.

    Returns the Celery task id so the caller can follow up on
    ``/admin/scheduler/schedules/history`` or the ``JobRun`` table.
    """
    try:
        kwargs: Dict[str, Any] = {}
        if payload.user_id is not None:
            kwargs["user_id"] = payload.user_id
        res = celery_app.send_task(
            "backend.tasks.portfolio.reconciliation.backfill_option_tax_lots",
            kwargs=kwargs,
        )
    except Exception as exc:
        logger.exception(
            "backfill_option_tax_lots enqueue failed (admin=%s user_id=%s)",
            admin_user.id,
            payload.user_id,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "backfill_option_tax_lots enqueued by admin=%s user_id=%s task_id=%s",
        admin_user.id,
        payload.user_id,
        res.id,
    )
    return {
        "status": "enqueued",
        "task": "backend.tasks.portfolio.reconciliation.backfill_option_tax_lots",
        "task_id": res.id,
        "user_id": payload.user_id,
    }
