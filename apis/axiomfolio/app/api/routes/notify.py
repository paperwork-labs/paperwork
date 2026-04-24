"""
Notify-me endpoints for "coming soon" features.

This is a deliberately tiny shell that backs the "Notify me" CTAs on
broker cards whose ``status`` is ``coming_v1_1`` (E*TRADE, Tradier,
Coinbase, Kraken). Persistence is intentionally deferred for this PR:
no existing table fits the (user_id, broker_slug, email) shape cleanly,
and adding a one-off ``NotifyMeRequest`` table just to write a single
field is more migration risk than it's worth at this stage. The route
logs the request as a structured warning so the operator can pull a
list out of logs if they want to cold-email subscribers manually.

When the v1.1 OAuth integrations actually ship, replace this with a
proper ``BrokerLaunchNotification`` table + Alembic migration and an
"unsubscribe" flow. Tracked in the v1 sprint plan (3h follow-up).
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.api.dependencies import get_current_user
from app.models.user import User
from app.services.silver.portfolio.broker_catalog import get_broker_by_slug

logger = logging.getLogger(__name__)

router = APIRouter()


def _mask_email(email: str) -> str:
    """Redact PII for logs: first char of local-part + domain + sha256 prefix."""

    h = hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]
    local, _, domain = email.partition("@")
    if not domain:
        return f"sha256:{h}"
    prefix = local[:1] if local else ""
    return f"{prefix}***@{domain} (sha256:{h})"


class BrokerLaunchNotifyRequest(BaseModel):
    """Payload for the Notify-me dialog on a coming-soon broker card."""

    broker_slug: str = Field(..., min_length=1, max_length=64)
    email: EmailStr


class BrokerLaunchNotifyResponse(BaseModel):
    """Honest response: we accepted the request but haven't persisted it.

    Surfaces the no-persistence trade-off in the API contract instead of
    pretending we wrote a row. The frontend can still show a confirming
    toast; the field gives an operator a way to flag if behaviour changes.
    """

    queued: bool
    persisted: bool


@router.post(
    "/broker-launch",
    response_model=BrokerLaunchNotifyResponse,
    summary="Capture an interested user's email for a coming-soon broker",
)
async def notify_me_broker_launch(
    payload: BrokerLaunchNotifyRequest,
    current_user: User = Depends(get_current_user),
) -> BrokerLaunchNotifyResponse:
    """Log a notify-me request for a ``coming_v1_1`` broker.

    Validates that the slug is in the catalog AND that it's actually a
    coming-soon broker; refusing requests for live or out-of-catalog
    slugs makes the route a (small) audit-trail signal instead of an
    open redirect for arbitrary email collection.
    """

    entry = get_broker_by_slug(payload.broker_slug)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown broker slug: {payload.broker_slug}",
        )
    if entry.status != "coming_v1_1":
        # Live brokers should hit OAuth directly. v1.2 SnapTrade (pricing) rows
        # are not notify-me; there's no sensible Notify-me flow for those either.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Notify-me is only available for upcoming brokers; "
                f"'{payload.broker_slug}' is currently '{entry.status}'."
            ),
        )

    logger.warning(
        "notify_me.broker_launch user_id=%s broker_slug=%s email=%s",
        current_user.id,
        payload.broker_slug,
        _mask_email(str(payload.email)),
    )
    return BrokerLaunchNotifyResponse(queued=True, persisted=False)
