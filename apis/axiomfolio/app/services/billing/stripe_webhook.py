"""Stripe webhook event processor.

Strict separation of concerns:

    Route layer (webhooks/stripe.py)
        |
        |  raw bytes + Stripe-Signature header
        v
    StripeWebhookProcessor.verify_and_parse(payload, sig_header)  -> dict event
        |
        v
    StripeWebhookProcessor.handle(event)   # sink is wired in __init__
        |
        v
    SubscriptionStateSink.apply(state)   <-- impl provided by caller
                                              (in prod: EntitlementService)

The processor never imports `EntitlementService` directly. Instead callers
pass a ``SubscriptionStateSink`` callback (a Protocol). That keeps this PR
mergeable independently of PR #326 (entitlements service): the route just
wires whichever sink exists at deploy time.

We process exactly the events that affect tier state:

    - checkout.session.completed         (first paid signup)
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_failed             (downgrade -> past_due if grace expires)
    - invoice.payment_succeeded          (clear past_due)

All other events are acknowledged (200 OK) and ignored. Stripe will retry on
non-2xx responses for up to 3 days, so it is critical that:

    - signature verification failures return 400 (do NOT retry)
    - unknown / unsupported events return 200 (do NOT retry forever)
    - sink failures return 5xx (DO retry)

Idempotency: every event has a unique `event.id`. Callers should pass an
``IdempotencyStore`` (any mapping-like object) to skip already-processed IDs
on retries.

medallion: ops
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from .price_catalog import PriceCatalog, TierSlug
from .stripe_client import StripeNotConfigured, get_stripe

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Errors                                                                      #
# --------------------------------------------------------------------------- #


class StripeSignatureError(ValueError):
    """Raised when the Stripe-Signature header doesn't validate against the payload.

    Routes should map this to HTTP 400 (NOT 401) so Stripe stops retrying.
    """


class StripeWebhookError(RuntimeError):
    """Raised when an event is well-formed but cannot be processed.

    Routes should map this to HTTP 500 so Stripe retries.
    """


# --------------------------------------------------------------------------- #
# Subscription state shape                                                    #
# --------------------------------------------------------------------------- #


class SubscriptionStatus(str, Enum):
    """Stripe-aligned status values we care about.

    Mirrors app.models.entitlement.EntitlementStatus but redeclared here
    so this module is import-safe without that PR.
    """

    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"


@dataclass(frozen=True)
class SubscriptionState:
    """Normalized subscription state ready to be persisted by the sink.

    All times are timezone-aware UTC. Money / quantities are absent here on
    purpose — the entitlement model only cares about *tier* and *status*.
    """

    user_id: int
    tier: TierSlug
    status: SubscriptionStatus
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    source_event_id: str
    source_event_type: str
    raw_event_excerpt: Mapping[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Sink + idempotency protocols                                                #
# --------------------------------------------------------------------------- #


@runtime_checkable
class SubscriptionStateSink(Protocol):
    """Persistence boundary; the entitlements service implements this."""

    def apply(self, state: SubscriptionState) -> None:  # pragma: no cover - protocol
        ...


@runtime_checkable
class IdempotencyStore(Protocol):
    """Records processed Stripe event IDs.

    Production impl will likely be Redis-backed with a TTL of a few days
    (Stripe stops retrying after ~3 days). Tests use a plain dict.
    """

    def __contains__(self, event_id: object) -> bool: ...  # pragma: no cover

    def mark(self, event_id: str) -> None: ...  # pragma: no cover


class _DictIdempotencyStore:
    """Default in-process store. Not safe across worker processes."""

    def __init__(self) -> None:
        self._seen: dict[str, datetime] = {}

    def __contains__(self, event_id: object) -> bool:
        return isinstance(event_id, str) and event_id in self._seen

    def mark(self, event_id: str) -> None:
        self._seen[event_id] = datetime.now(UTC)


class RedisIdempotencyStore:
    """Cross-process idempotency keyed in Redis.

    Stripe retries failed webhooks for ~3 days. The default TTL covers
    that window with a small safety margin so we never accidentally
    process the same event twice across worker restarts.

    Tests that don't have Redis can keep using ``_DictIdempotencyStore``;
    production should always wire this in.
    """

    DEFAULT_TTL_SECONDS = 4 * 24 * 3600  # 4 days
    KEY_PREFIX = "billing:stripe_webhook:event:"

    def __init__(
        self,
        redis_client: Any,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        key_prefix: str = KEY_PREFIX,
    ) -> None:
        self._redis = redis_client
        self._ttl = int(ttl_seconds)
        self._prefix = key_prefix

    def _key(self, event_id: str) -> str:
        return f"{self._prefix}{event_id}"

    def __contains__(self, event_id: object) -> bool:
        if not isinstance(event_id, str) or not event_id:
            return False
        try:
            return bool(self._redis.exists(self._key(event_id)))
        except Exception as exc:
            logger.warning(
                "stripe webhook: idempotency lookup failed for %s: %s",
                event_id,
                exc,
            )
            # Fail open so we still process the event; double-processing
            # is preferable to silently dropping a paying customer's
            # subscription change.
            return False

    def mark(self, event_id: str) -> None:
        if not event_id:
            return
        try:
            self._redis.set(self._key(event_id), "1", ex=self._ttl)
        except Exception as exc:
            logger.warning(
                "stripe webhook: idempotency mark failed for %s: %s",
                event_id,
                exc,
            )


# --------------------------------------------------------------------------- #
# User resolver                                                               #
# --------------------------------------------------------------------------- #


@runtime_checkable
class UserResolver(Protocol):
    """Maps Stripe customer/email/metadata to internal user_id."""

    def resolve(
        self,
        *,
        stripe_customer_id: str | None,
        email: str | None,
        metadata: Mapping[str, Any],
    ) -> int | None: ...  # pragma: no cover


# --------------------------------------------------------------------------- #
# Processor                                                                   #
# --------------------------------------------------------------------------- #


_HANDLED_EVENT_TYPES = frozenset(
    {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.payment_failed",
        "invoice.payment_succeeded",
    }
)


@dataclass(frozen=True)
class ProcessResult:
    """What the route returns to Stripe.

    `acted` distinguishes "we processed this and changed state" from
    "we acknowledged but ignored". Useful for metrics dashboards.
    """

    acked: bool
    acted: bool
    reason: str
    state: SubscriptionState | None = None


class StripeWebhookProcessor:
    """Verify + dispatch Stripe webhook events.

    Construction:

        processor = StripeWebhookProcessor(
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
            catalog=PriceCatalog.from_env(),
            user_resolver=DBUserResolver(session),
            sink=EntitlementSink(session),  # PR #326
            idempotency=RedisIdempotency(redis),
        )

    Each request handled by a fresh processor (or one whose sink has its own
    request-scoped Session). Do NOT share sinks across requests with stateful
    transactions.
    """

    def __init__(
        self,
        *,
        webhook_secret: str | None,
        catalog: PriceCatalog,
        user_resolver: UserResolver,
        sink: SubscriptionStateSink,
        idempotency: IdempotencyStore | None = None,
        stripe_module: Any | None = None,
    ) -> None:
        self._webhook_secret = webhook_secret
        self._catalog = catalog
        self._user_resolver = user_resolver
        self._sink = sink
        self._idempotency = idempotency or _DictIdempotencyStore()
        self._stripe = stripe_module  # may be injected for tests

    # --------------------------------------------------------------------- #
    # Verification                                                          #
    # --------------------------------------------------------------------- #

    def verify_and_parse(self, payload: bytes, sig_header: str | None) -> dict[str, Any]:
        """Validate the Stripe-Signature header and return the parsed event.

        Raises:
            StripeNotConfigured: webhook secret not set.
            StripeSignatureError: header missing or signature mismatch.
        """
        if not self._webhook_secret:
            raise StripeNotConfigured(
                "STRIPE_WEBHOOK_SECRET is not configured; refusing to accept webhooks."
            )
        if not sig_header:
            raise StripeSignatureError("Missing Stripe-Signature header")

        stripe = self._stripe or get_stripe()
        # Whitelist the verification errors we know about. Anything else
        # (network glitch, OOM, ...) should bubble up as a 500 so Stripe
        # retries instead of being silently turned into a 400.
        sig_error_cls: tuple = (ValueError,)
        signature_verification_error = getattr(
            getattr(stripe, "error", None), "SignatureVerificationError", None
        )
        if signature_verification_error is not None:
            sig_error_cls = (ValueError, signature_verification_error)
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=self._webhook_secret,
            )
        except sig_error_cls as exc:
            # The route maps this to 400 so Stripe stops retrying.
            raise StripeSignatureError(str(exc)) from exc

        # `construct_event` returns a stripe.Event (dict-like).
        return dict(event)

    # --------------------------------------------------------------------- #
    # Dispatch                                                              #
    # --------------------------------------------------------------------- #

    def handle(self, event: Mapping[str, Any]) -> ProcessResult:
        """Apply the event to the sink. Idempotent on event.id."""
        event_id = str(event.get("id") or "")
        event_type = str(event.get("type") or "")

        if not event_id or not event_type:
            raise StripeWebhookError(f"Event missing id/type: id={event_id!r} type={event_type!r}")

        if event_id in self._idempotency:
            logger.info("stripe webhook: skipping already-processed event_id=%s", event_id)
            return ProcessResult(acked=True, acted=False, reason="duplicate")

        if event_type not in _HANDLED_EVENT_TYPES:
            # Acknowledge so Stripe stops retrying. Don't mark idempotent so
            # if we add the type later, the next replay will pick it up.
            logger.debug("stripe webhook: ignoring unhandled type=%s id=%s", event_type, event_id)
            return ProcessResult(acked=True, acted=False, reason=f"unhandled:{event_type}")

        try:
            state = self._build_state(event)
        except _SkipEvent as skip:
            self._idempotency.mark(event_id)
            return ProcessResult(acked=True, acted=False, reason=skip.reason)

        # Apply to sink. Sink failures must propagate so Stripe retries.
        try:
            self._sink.apply(state)
        except Exception as exc:
            logger.exception(
                "stripe webhook: sink failed for event_id=%s type=%s: %s",
                event_id,
                event_type,
                exc,
            )
            # Do NOT mark idempotent — we want Stripe to retry.
            raise StripeWebhookError(f"sink failed for {event_id}") from exc

        self._idempotency.mark(event_id)
        logger.info(
            "stripe webhook: applied event_id=%s type=%s user_id=%s tier=%s status=%s",
            event_id,
            event_type,
            state.user_id,
            state.tier.value,
            state.status.value,
        )
        return ProcessResult(acked=True, acted=True, reason="applied", state=state)

    # --------------------------------------------------------------------- #
    # Event -> SubscriptionState extraction                                 #
    # --------------------------------------------------------------------- #

    def _build_state(self, event: Mapping[str, Any]) -> SubscriptionState:
        event_id = str(event["id"])
        event_type = str(event["type"])
        obj = (event.get("data") or {}).get("object") or {}

        if event_type == "checkout.session.completed":
            return self._from_checkout_session(obj, event_id, event_type)

        if event_type.startswith("customer.subscription."):
            return self._from_subscription(obj, event_id, event_type)

        if event_type.startswith("invoice."):
            return self._from_invoice(obj, event_id, event_type)

        # Should be unreachable due to _HANDLED_EVENT_TYPES filter.
        raise _SkipEvent(f"unhandled-internal:{event_type}")

    # --- per-event extractors -------------------------------------------- #

    def _from_checkout_session(
        self, session: Mapping[str, Any], event_id: str, event_type: str
    ) -> SubscriptionState:
        # Only paid subscription checkouts touch entitlements.
        if session.get("mode") != "subscription":
            raise _SkipEvent(f"checkout-mode:{session.get('mode')!r}")
        if session.get("payment_status") not in ("paid", "no_payment_required"):
            raise _SkipEvent(f"checkout-payment-status:{session.get('payment_status')!r}")

        customer_id = self._get_customer_id(session)
        email = (session.get("customer_details") or {}).get("email") or session.get(
            "customer_email"
        )
        metadata = dict(session.get("metadata") or {})

        user_id = self._user_resolver.resolve(
            stripe_customer_id=customer_id, email=email, metadata=metadata
        )
        if user_id is None:
            raise StripeWebhookError(
                f"checkout.session.completed: cannot resolve user (customer={customer_id} email={email})"
            )

        # Tier comes from the line items' price IDs.
        line_items = (session.get("line_items") or {}).get("data") or []
        tier = self._tier_from_line_items(line_items)
        if tier is None:
            raise _SkipEvent("checkout-no-known-price")

        return SubscriptionState(
            user_id=user_id,
            tier=tier,
            status=SubscriptionStatus.ACTIVE,
            stripe_customer_id=customer_id,
            stripe_subscription_id=session.get("subscription"),
            current_period_end=None,  # subscription.created will fill this in
            cancel_at_period_end=False,
            source_event_id=event_id,
            source_event_type=event_type,
            raw_event_excerpt={
                "session_id": session.get("id"),
                "mode": session.get("mode"),
            },
        )

    def _from_subscription(
        self, sub: Mapping[str, Any], event_id: str, event_type: str
    ) -> SubscriptionState:
        customer_id = self._get_customer_id(sub)
        metadata = dict(sub.get("metadata") or {})
        user_id = self._user_resolver.resolve(
            stripe_customer_id=customer_id, email=None, metadata=metadata
        )
        if user_id is None:
            raise StripeWebhookError(
                f"customer.subscription.*: cannot resolve user (customer={customer_id})"
            )

        items = (sub.get("items") or {}).get("data") or []
        tier = self._tier_from_subscription_items(items)
        # If subscription is being deleted, we always downgrade to FREE,
        # regardless of price.
        if event_type == "customer.subscription.deleted":
            tier = TierSlug.FREE
            status = SubscriptionStatus.CANCELED
        else:
            if tier is None:
                raise _SkipEvent("subscription-no-known-price")
            status = self._coerce_status(sub.get("status"))

        return SubscriptionState(
            user_id=user_id,
            tier=tier,
            status=status,
            stripe_customer_id=customer_id,
            stripe_subscription_id=sub.get("id"),
            current_period_end=_unix_to_dt(sub.get("current_period_end")),
            cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
            source_event_id=event_id,
            source_event_type=event_type,
            raw_event_excerpt={
                "subscription_id": sub.get("id"),
                "status": sub.get("status"),
            },
        )

    def _from_invoice(
        self, invoice: Mapping[str, Any], event_id: str, event_type: str
    ) -> SubscriptionState:
        # Only subscription invoices affect entitlement state.
        sub_id = invoice.get("subscription")
        if not sub_id:
            raise _SkipEvent("invoice-no-subscription")

        customer_id = self._get_customer_id(invoice)
        metadata = dict(invoice.get("metadata") or {})
        user_id = self._user_resolver.resolve(
            stripe_customer_id=customer_id, email=None, metadata=metadata
        )
        if user_id is None:
            raise StripeWebhookError(f"invoice.*: cannot resolve user (customer={customer_id})")

        # Resolve current tier from the invoice line items.
        lines = (invoice.get("lines") or {}).get("data") or []
        tier = self._tier_from_invoice_lines(lines)
        if tier is None:
            # Invoice for a plan we no longer recognize. Don't change state.
            raise _SkipEvent("invoice-no-known-price")

        if event_type == "invoice.payment_failed":
            status = SubscriptionStatus.PAST_DUE
        else:  # invoice.payment_succeeded
            status = SubscriptionStatus.ACTIVE

        return SubscriptionState(
            user_id=user_id,
            tier=tier,
            status=status,
            stripe_customer_id=customer_id,
            stripe_subscription_id=str(sub_id),
            current_period_end=_unix_to_dt(invoice.get("period_end")),
            cancel_at_period_end=False,
            source_event_id=event_id,
            source_event_type=event_type,
            raw_event_excerpt={
                "invoice_id": invoice.get("id"),
                "billing_reason": invoice.get("billing_reason"),
            },
        )

    # --- helpers --------------------------------------------------------- #

    @staticmethod
    def _get_customer_id(obj: Mapping[str, Any]) -> str | None:
        # Stripe sometimes returns expanded customer objects; normalize.
        cust = obj.get("customer")
        if isinstance(cust, str):
            return cust
        if isinstance(cust, Mapping):
            cid = cust.get("id")
            return str(cid) if cid else None
        return None

    @staticmethod
    def _coerce_status(value: Any) -> SubscriptionStatus:
        try:
            return SubscriptionStatus(str(value))
        except ValueError:
            # Unknown Stripe status (e.g., "paused"). Treat as past_due so the
            # user keeps a graceful experience but we know to follow up.
            logger.warning(
                "stripe webhook: unknown subscription status=%r, mapping to past_due",
                value,
            )
            return SubscriptionStatus.PAST_DUE

    def _tier_from_line_items(self, line_items: Any) -> TierSlug | None:
        # Same rule as _tier_from_subscription_items: pick the highest tier
        # so a multi-line checkout (e.g. Pro+ + add-on) never accidentally
        # downgrades the user to whichever line happened to come first.
        best: TierSlug | None = None
        for li in line_items:
            price = li.get("price") or {}
            pid = price.get("id")
            if not pid:
                continue
            entry = self._catalog.resolve(str(pid))
            if not entry:
                continue
            best = _max_tier(best, entry.tier)
        return best

    def _tier_from_subscription_items(self, items: Any) -> TierSlug | None:
        # If a subscription has multiple items at different tiers (rare),
        # take the highest tier — never accidentally downgrade.
        best: TierSlug | None = None
        for item in items:
            price = item.get("price") or {}
            pid = price.get("id")
            if not pid:
                continue
            entry = self._catalog.resolve(str(pid))
            if not entry:
                continue
            best = _max_tier(best, entry.tier)
        return best

    def _tier_from_invoice_lines(self, lines: Any) -> TierSlug | None:
        best: TierSlug | None = None
        for line in lines:
            price = line.get("price") or {}
            pid = price.get("id")
            if not pid:
                continue
            entry = self._catalog.resolve(str(pid))
            if not entry:
                continue
            best = _max_tier(best, entry.tier)
        return best


# --------------------------------------------------------------------------- #
# Internal helpers                                                            #
# --------------------------------------------------------------------------- #


class _SkipEvent(Exception):
    """Sentinel: this event is well-formed but we deliberately don't act on it."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


_TIER_RANK = {
    TierSlug.FREE: 0,
    TierSlug.PRO: 20,
    TierSlug.PRO_PLUS: 30,
    TierSlug.QUANT_DESK: 40,
    TierSlug.ENTERPRISE: 50,
}


def _max_tier(a: TierSlug | None, b: TierSlug) -> TierSlug:
    if a is None:
        return b
    return a if _TIER_RANK[a] >= _TIER_RANK[b] else b


def _unix_to_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError):
        return None
