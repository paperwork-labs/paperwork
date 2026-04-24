"""
Entitlement & Subscription Tier Models
======================================

Single source of truth for what each user is allowed to do based on their
subscription tier. Ladder 3 uses five tiers:

    free        — anonymous-quality market data, watchlist, manual research
    pro         — signals and BYOK entry tier
    pro_plus    — deeper strategy surfaces + unlimited native chat
    quant_desk  — backtest/Jupyter/custom MCP tools
    enterprise  — SSO, admin scopes, dedicated SLA

Tiers are a *strict* monotonic ladder. A user with `pro_plus` automatically
satisfies any requirement of `pro` or `free`. Comparisons go through
`SubscriptionTier.rank()` rather than string equality so adding a tier in
the middle does not break existing checks.

Per `engineering.mdc` and the multi-tenancy section of `AGENTS.md`,
Entitlement is `1:1` with `User` (CASCADE delete). It is the only place the
billing system writes to in the application database — Stripe webhooks
update this row and nothing else. The tier check itself never touches
Stripe at request time; we trust the local mirror, and Stripe drives state
asynchronously.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base

# =============================================================================
# ENUMS
# =============================================================================


class SubscriptionTier(str, Enum):
    """Five-tier ladder. Stored as lowercase strings; compare via `rank()`.

    Ranks are spaced (10, 20, ...) so a future tier (e.g. ``team`` between
    ``pro_plus`` and ``quant_desk``) can be added without renumbering.
    """

    FREE = "free"
    PRO = "pro"
    PRO_PLUS = "pro_plus"
    QUANT_DESK = "quant_desk"
    ENTERPRISE = "enterprise"

    @classmethod
    def rank(cls, value: SubscriptionTier | str | None) -> int:
        """Return the ordinal rank of a tier. Unknown / None → 0 (FREE).

        Using a method rather than `auto()` so the persisted string values
        remain stable even if the enum order changes.
        """
        if value is None:
            return 0
        if isinstance(value, SubscriptionTier):
            key = value.value
        else:
            key = str(value).lower()
        return _TIER_RANK.get(key, 0)

    def __ge__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, SubscriptionTier):
            return SubscriptionTier.rank(self) >= SubscriptionTier.rank(other)
        return NotImplemented

    def __gt__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, SubscriptionTier):
            return SubscriptionTier.rank(self) > SubscriptionTier.rank(other)
        return NotImplemented

    def __le__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, SubscriptionTier):
            return SubscriptionTier.rank(self) <= SubscriptionTier.rank(other)
        return NotImplemented

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, SubscriptionTier):
            return SubscriptionTier.rank(self) < SubscriptionTier.rank(other)
        return NotImplemented


_TIER_RANK: dict[str, int] = {
    SubscriptionTier.FREE.value: 0,
    SubscriptionTier.PRO.value: 20,
    SubscriptionTier.PRO_PLUS.value: 30,
    SubscriptionTier.QUANT_DESK.value: 40,
    SubscriptionTier.ENTERPRISE.value: 50,
}


class EntitlementStatus(str, Enum):
    """Mirrors Stripe subscription status, with one extra value: ``manual``.

    ``manual`` covers internal grants (validator pseudonym holders, the
    founding hedge-fund partner, employee comp accounts) that should not be
    overwritten by Stripe webhook drift.
    """

    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    UNPAID = "unpaid"
    MANUAL = "manual"

    @classmethod
    def is_active_like(cls, value: EntitlementStatus | str | None) -> bool:
        """Return True if the status grants tier access right now.

        We treat ``trialing``, ``active``, and ``manual`` as access-granting.
        ``past_due`` keeps access for a short grace period handled by
        ``Entitlement.is_in_grace_period()``.
        """
        if value is None:
            return False
        key = value.value if isinstance(value, EntitlementStatus) else str(value).lower()
        return key in {
            cls.ACTIVE.value,
            cls.TRIALING.value,
            cls.MANUAL.value,
        }


# =============================================================================
# MODEL
# =============================================================================


class Entitlement(Base):
    """One row per user. The single source of truth for tier access.

    Reads are cheap (indexed lookup by user_id) and writes only happen from:

    * Stripe webhook handlers (``app/services/billing/stripe_webhook.py``)
    * Manual overrides by an operator (``EntitlementService.manual_set_tier``)
    * Auto-creation on first read (``EntitlementService.get_or_create``)
      defaults the row at ``FREE`` / ``ACTIVE``

    Critically, there is no other path. If you find yourself updating
    ``Entitlement.tier`` from a route handler or a Celery task other than the
    Stripe handler, stop and route the change through ``EntitlementService``
    so we keep the audit trail in ``metadata_json``.
    """

    __tablename__ = "entitlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    tier = Column(
        SQLEnum(
            SubscriptionTier,
            values_callable=lambda x: [m.value for m in SubscriptionTier],
            native_enum=False,
            length=20,
            name="subscription_tier",
        ),
        nullable=False,
        server_default=SubscriptionTier.FREE.value,
        default=SubscriptionTier.FREE,
    )
    status = Column(
        SQLEnum(
            EntitlementStatus,
            values_callable=lambda x: [m.value for m in EntitlementStatus],
            native_enum=False,
            length=24,
            name="entitlement_status",
        ),
        nullable=False,
        server_default=EntitlementStatus.ACTIVE.value,
        default=EntitlementStatus.ACTIVE,
    )

    # Stripe linkage (nullable — free tier has no Stripe object)
    stripe_customer_id = Column(String(64), nullable=True, index=True)
    stripe_subscription_id = Column(String(64), nullable=True, unique=True)
    stripe_price_id = Column(String(64), nullable=True)

    # Billing periods (timezone-aware, mirrored from Stripe)
    current_period_start = Column(TIMESTAMP(timezone=True), nullable=True)
    current_period_end = Column(TIMESTAMP(timezone=True), nullable=True)
    trial_ends_at = Column(TIMESTAMP(timezone=True), nullable=True)
    cancel_at_period_end = Column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
    )

    # Audit + free-form Stripe payload mirror
    metadata_json = Column("metadata", JSON, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", backref="entitlement", uselist=False)

    __table_args__ = (
        # We already have unique on user_id; this composite makes the common
        # "active subscriptions per tier" report cheap.
        Index("ix_entitlements_tier_status", "tier", "status"),
        UniqueConstraint("user_id", name="uq_entitlements_user_id"),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    GRACE_PERIOD_HOURS = 72  # past_due users keep access for 3 days

    def is_active(self, now: datetime | None = None) -> bool:
        """True if the subscription currently grants tier access.

        Past-due subscriptions retain access for ``GRACE_PERIOD_HOURS`` to
        avoid locking a user out the moment a card declines. After the grace
        period expires, the next access check downgrades them to FREE.
        """
        if EntitlementStatus.is_active_like(self.status):
            return True
        if self.status == EntitlementStatus.PAST_DUE:
            return self.is_in_grace_period(now)
        return False

    def is_in_grace_period(self, now: datetime | None = None) -> bool:
        """True if a past_due subscription is still inside its grace window.

        Grace is measured from ``current_period_end`` (when Stripe last
        billed) rather than from ``updated_at``, so a webhook hiccup cannot
        accidentally extend access.
        """
        if self.status != EntitlementStatus.PAST_DUE:
            return False
        if self.current_period_end is None:
            return False
        if now is None:
            now = datetime.now(self.current_period_end.tzinfo)
        delta = now - self.current_period_end
        return delta.total_seconds() <= self.GRACE_PERIOD_HOURS * 3600

    def effective_tier(self, now: datetime | None = None) -> SubscriptionTier:
        """The tier we should *behave* as for this user right now.

        Returns the persisted tier when active, otherwise FREE. This is the
        method route handlers and the FastAPI dependency call into; nothing
        else should be reading ``self.tier`` directly for access decisions.
        """
        if self.is_active(now):
            return self.tier
        return SubscriptionTier.FREE
