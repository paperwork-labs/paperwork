"""
Entitlement Service
===================

The only sanctioned read/write path for ``Entitlement`` rows.

Conventions (per ``engineering.mdc``):

* Sessions are passed as parameters; never created here.
* All writes go through helpers in this module so the audit trail in
  ``Entitlement.metadata_json`` stays consistent.
* No Stripe API calls happen in this module — Stripe webhook handlers in
  ``backend/services/billing/stripe_handler.py`` translate Stripe objects
  into calls to ``EntitlementService.apply_subscription_state``.

Why a service and not just CRUD on the model
--------------------------------------------

We want a single place that:

1. Lazily creates an entitlement row at FREE the first time a user is
   seen (so existing accounts don't 500 the moment the column is checked).
2. Records *why* a tier change happened (Stripe event id, operator who
   issued a comp upgrade, etc.) without scattering audit code everywhere.
3. Exposes a one-call ``check_feature_access`` so route code stays a
   one-liner.

medallion: ops
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from backend.models import Entitlement, EntitlementStatus, SubscriptionTier, User
from backend.services.billing.feature_catalog import (
    Feature,
    get_feature,
    is_allowed,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccessDecision:
    """Result of a feature check.

    ``allowed`` is the only field most callers need. ``reason`` is a
    short, user-safe string suitable for an upgrade-prompt tooltip.
    ``required_tier`` lets the frontend render the right CTA without a
    second round-trip to the catalog.
    """

    allowed: bool
    feature: Feature
    current_tier: SubscriptionTier
    required_tier: SubscriptionTier
    reason: str


class EntitlementService:
    """Stateless helper. Methods are static so the service can be used
    from FastAPI dependencies, Celery tasks, and the Brain without
    instantiation overhead."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_or_create(db: Session, user: User) -> Entitlement:
        """Fetch the user's entitlement row, creating a FREE/ACTIVE row on
        first read.

        We do *not* commit here — the caller controls the transaction
        scope (per the sessions-as-parameters rule). If the caller never
        commits, a future request will create the row again, which is a
        no-op outcome (still FREE). That is acceptable for a row that
        never carries paid state at this stage of its lifecycle.
        """
        ent = (
            db.query(Entitlement)
            .filter(Entitlement.user_id == user.id)
            .one_or_none()
        )
        if ent is not None:
            return ent

        ent = Entitlement(
            user_id=user.id,
            tier=SubscriptionTier.FREE,
            status=EntitlementStatus.ACTIVE,
            metadata_json={"source": "auto_create_on_first_read"},
        )
        db.add(ent)
        db.flush()  # populate id; no commit
        logger.info(
            "Created default FREE entitlement for user_id=%s (auto on first read)",
            user.id,
        )
        return ent

    @staticmethod
    def effective_tier(db: Session, user: User) -> SubscriptionTier:
        """Return the tier we should *behave* as for ``user`` right now.

        Use this rather than ``user.entitlement.tier`` directly because it
        applies the grace-period and active-status rules baked into
        ``Entitlement.effective_tier()``.
        """
        ent = EntitlementService.get_or_create(db, user)
        return ent.effective_tier()

    @staticmethod
    def check(db: Session, user: User, feature_key: str) -> AccessDecision:
        """Decide whether ``user`` can use ``feature_key`` right now."""
        feature = get_feature(feature_key)
        current = EntitlementService.effective_tier(db, user)
        allowed = is_allowed(current, feature_key)
        if allowed:
            reason = f"Allowed at {current.value}"
        else:
            reason = (
                f"Requires {feature.min_tier.value}; you are on {current.value}"
            )
        return AccessDecision(
            allowed=allowed,
            feature=feature,
            current_tier=current,
            required_tier=feature.min_tier,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def manual_set_tier(
        db: Session,
        *,
        user: User,
        new_tier: SubscriptionTier,
        actor: str,
        note: Optional[str] = None,
    ) -> Entitlement:
        """Operator-issued tier change (comp accounts, validator pseudonyms,
        the founding partners). Marked with ``status=MANUAL`` so subsequent
        Stripe webhooks won't clobber it.

        Args:
            db: SQLAlchemy session (caller commits).
            user: target user.
            new_tier: tier to grant.
            actor: identifier for who issued the change (operator email,
                CI script name, etc.). Logged into ``metadata_json`` for
                audit.
            note: optional free-form context.
        """
        ent = EntitlementService.get_or_create(db, user)
        old_tier = ent.tier
        old_status = ent.status

        ent.tier = new_tier
        ent.status = EntitlementStatus.MANUAL
        ent.cancel_at_period_end = False
        ent.metadata_json = _append_audit(
            ent.metadata_json,
            {
                "event": "manual_set_tier",
                "actor": actor,
                "from_tier": old_tier.value if isinstance(old_tier, SubscriptionTier) else str(old_tier),
                "from_status": old_status.value if isinstance(old_status, EntitlementStatus) else str(old_status),
                "to_tier": new_tier.value,
                "note": note,
                "at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            },
        )
        db.flush()
        logger.info(
            "Manual tier change: user_id=%s %s -> %s (actor=%s)",
            user.id,
            ent.metadata_json["audit"][-1]["from_tier"],
            new_tier.value,
            actor,
        )
        return ent

    @staticmethod
    def apply_subscription_state(
        db: Session,
        *,
        user: User,
        tier: SubscriptionTier,
        status: EntitlementStatus,
        stripe_customer_id: Optional[str],
        stripe_subscription_id: Optional[str],
        stripe_price_id: Optional[str],
        current_period_start: Optional[datetime],
        current_period_end: Optional[datetime],
        trial_ends_at: Optional[datetime],
        cancel_at_period_end: bool,
        stripe_event_id: Optional[str] = None,
    ) -> Entitlement:
        """Apply a Stripe-driven state update.

        This is the only path Stripe webhooks should write through. If the
        current row is ``MANUAL``, we refuse to overwrite it from Stripe —
        that protects comp accounts from being silently downgraded if the
        user later starts a regular subscription.
        """
        ent = EntitlementService.get_or_create(db, user)

        if ent.status == EntitlementStatus.MANUAL:
            logger.warning(
                "Refusing to overwrite MANUAL entitlement for user_id=%s "
                "from Stripe event=%s (target tier=%s)",
                user.id,
                stripe_event_id,
                tier.value,
            )
            ent.metadata_json = _append_audit(
                ent.metadata_json,
                {
                    "event": "stripe_overwrite_blocked",
                    "stripe_event_id": stripe_event_id,
                    "attempted_tier": tier.value,
                    "attempted_status": status.value,
                    "at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                },
            )
            db.flush()
            return ent

        ent.tier = tier
        ent.status = status
        ent.stripe_customer_id = stripe_customer_id
        ent.stripe_subscription_id = stripe_subscription_id
        ent.stripe_price_id = stripe_price_id
        ent.current_period_start = current_period_start
        ent.current_period_end = current_period_end
        ent.trial_ends_at = trial_ends_at
        ent.cancel_at_period_end = cancel_at_period_end
        ent.metadata_json = _append_audit(
            ent.metadata_json,
            {
                "event": "stripe_apply",
                "stripe_event_id": stripe_event_id,
                "tier": tier.value,
                "status": status.value,
                "at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            },
        )
        db.flush()
        return ent


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------


def _append_audit(
    existing: Optional[Mapping[str, Any]], event: Mapping[str, Any]
) -> dict[str, Any]:
    """Append ``event`` to a bounded audit list inside the JSON column.

    We cap the list at the most recent 50 events to keep the row from
    growing unbounded; older events live in application logs and (later)
    the dedicated ``audit_log`` table. The whole audit array is rewritten
    on every change because SQLAlchemy can't detect in-place mutation of
    a dict / list inside a JSON column without ``MutableDict``/``MutableList``
    and we'd rather keep the model simple.
    """
    base: dict[str, Any] = dict(existing) if existing else {}
    audit: list[Any] = list(base.get("audit") or [])
    audit.append(dict(event))
    base["audit"] = audit[-50:]
    return base
