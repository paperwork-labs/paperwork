"""Stripe webhook endpoint.

Mounted at ``/api/v1/webhooks/stripe`` (see backend/api/routes/webhooks/__init__.py).

Behavior matrix (HTTP status -> Stripe behavior):

    200  acknowledged (Stripe stops retrying)
    400  bad signature / malformed body (Stripe stops retrying)
    402  Stripe not configured for this env (Stripe stops retrying)
    500  sink failed (Stripe retries up to 3 days)

Read raw bytes (``await request.body()``) before parsing; Stripe signatures
are computed over the *exact* request body, so do NOT use FastAPI's body
parser here.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.services.billing.price_catalog import PriceCatalog
from backend.services.billing.stripe_client import StripeNotConfigured
from backend.services.billing.stripe_webhook import (
    RedisIdempotencyStore,
    StripeSignatureError,
    StripeWebhookError,
    StripeWebhookProcessor,
    SubscriptionState,
    SubscriptionStateSink,
)
from backend.services.billing.user_resolver import DBUserResolver

logger = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Default sink                                                                #
# --------------------------------------------------------------------------- #


class _LoggingSink:
    """Fallback sink used when EntitlementService isn't available yet.

    Logs the would-be state change at INFO so operators can observe webhook
    flow before PR #326 is merged. Stripe still gets a 200, so we don't
    accumulate retries.
    """

    def apply(self, state: SubscriptionState) -> None:
        logger.info(
            "stripe webhook (no-sink): would set user_id=%s tier=%s status=%s subscription_id=%s",
            state.user_id,
            state.tier.value,
            state.status.value,
            state.stripe_subscription_id,
        )


def _resolve_sink(session: Session) -> SubscriptionStateSink:
    """Wire EntitlementService if it exists; otherwise log-only."""
    try:
        from backend.services.billing.entitlement_service import (  # type: ignore[import-not-found]
            EntitlementService,
        )
        from backend.services.billing.entitlement_sink import (  # type: ignore[import-not-found]
            EntitlementWebhookSink,
        )
    except ImportError:
        return _LoggingSink()
    return EntitlementWebhookSink(EntitlementService(session))


def _build_idempotency_store():
    """Return a Redis-backed store when Redis is wired, else fall back to
    the in-process dict (which is only safe for single-worker dev/test).

    We import lazily so this module stays usable in unit tests that mock
    out Redis entirely. Any failure to construct the store degrades to the
    default dict store inside the processor — never blocks the webhook.
    """
    try:
        from backend.services.market.market_infra import MarketInfra
    except ImportError:
        return None
    try:
        client = MarketInfra().redis_client
    except Exception as exc:  # noqa: BLE001 - REDIS_URL missing, etc.
        logger.warning(
            "stripe webhook: Redis unavailable, falling back to in-process "
            "idempotency: %s",
            exc,
        )
        return None
    try:
        return RedisIdempotencyStore(client)
    except Exception as exc:  # noqa: BLE001 - never fail webhook on infra
        logger.warning(
            "stripe webhook: idempotency store construction failed: %s", exc
        )
        return None


def _build_processor(session: Session) -> StripeWebhookProcessor:
    return StripeWebhookProcessor(
        webhook_secret=getattr(settings, "STRIPE_WEBHOOK_SECRET", None),
        catalog=PriceCatalog.from_env(),
        user_resolver=DBUserResolver(session),
        sink=_resolve_sink(session),
        idempotency=_build_idempotency_store(),
    )


# --------------------------------------------------------------------------- #
# Route                                                                       #
# --------------------------------------------------------------------------- #


@router.post("/stripe", include_in_schema=True)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Receive and process a Stripe webhook event."""
    payload = await request.body()

    processor = _build_processor(db)

    try:
        event = processor.verify_and_parse(payload, stripe_signature)
    except StripeNotConfigured as exc:
        logger.warning("stripe webhook rejected: not configured: %s", exc)
        return JSONResponse(
            status_code=402,
            content={
                "error": "stripe_not_configured",
                "detail": "Stripe webhook secret is not set in this environment.",
            },
        )
    except StripeSignatureError as exc:
        logger.warning("stripe webhook rejected: bad signature: %s", exc)
        return JSONResponse(
            status_code=400,
            content={"error": "bad_signature", "detail": str(exc)},
        )

    try:
        result = processor.handle(event)
    except StripeWebhookError as exc:
        # 500 -> Stripe retries.
        logger.exception("stripe webhook 500 (will retry): %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "processing_failed", "detail": str(exc)},
        )

    return JSONResponse(
        status_code=200,
        content={
            "received": True,
            "acted": result.acted,
            "reason": result.reason,
        },
    )
