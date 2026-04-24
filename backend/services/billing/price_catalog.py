"""Stripe Price ID -> internal SubscriptionTier mapping.

This is the *only* place where Stripe price/product identifiers are mapped to
internal tier names. Webhook handlers and checkout-session creators must look
up tiers through ``resolve_tier_for_price()`` so we have one auditable list
when prices change.

Layout decision: the catalog is loaded from environment variables (one per
tier) rather than hard-coded so we can swap test/prod price IDs without a
code deploy. The frontend never sees these IDs; it only sees tier slugs from
the entitlements API.

Env vars consumed (all optional; missing entries simply don't resolve):

    STRIPE_PRICE_PRO_MONTHLY
    STRIPE_PRICE_PRO_ANNUAL
    STRIPE_PRICE_PRO_PLUS_MONTHLY
    STRIPE_PRICE_PRO_PLUS_ANNUAL
    STRIPE_PRICE_QUANT_DESK_MONTHLY
    STRIPE_PRICE_QUANT_DESK_ANNUAL
    STRIPE_PRICE_ENTERPRISE_MONTHLY  (rare; usually contract-billed)
    STRIPE_PRICE_ENTERPRISE_ANNUAL

Free tier never has a Stripe price (it's the implicit default).

medallion: ops
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)


# Mirror of backend.models.entitlement.SubscriptionTier values.
# Re-declared here as plain strings so this module stays import-safe even when
# the entitlements model isn't available (e.g., during the in-flight PR #326
# rebase). The webhook processor reconciles these via
# ``EntitlementService.apply_subscription_state``, which accepts the slug.
class TierSlug(str, Enum):
    FREE = "free"
    PRO = "pro"
    PRO_PLUS = "pro_plus"
    QUANT_DESK = "quant_desk"
    ENTERPRISE = "enterprise"


class BillingInterval(str, Enum):
    MONTHLY = "month"
    ANNUAL = "year"


@dataclass(frozen=True)
class PriceEntry:
    """One row in the catalog: which tier and which billing interval a Stripe Price ID buys."""

    price_id: str
    tier: TierSlug
    interval: BillingInterval


# (env_var_name, tier, interval)
_CATALOG_SPEC: Tuple[Tuple[str, TierSlug, BillingInterval], ...] = (
    ("STRIPE_PRICE_PRO_MONTHLY", TierSlug.PRO, BillingInterval.MONTHLY),
    ("STRIPE_PRICE_PRO_ANNUAL", TierSlug.PRO, BillingInterval.ANNUAL),
    ("STRIPE_PRICE_PRO_PLUS_MONTHLY", TierSlug.PRO_PLUS, BillingInterval.MONTHLY),
    ("STRIPE_PRICE_PRO_PLUS_ANNUAL", TierSlug.PRO_PLUS, BillingInterval.ANNUAL),
    ("STRIPE_PRICE_QUANT_DESK_MONTHLY", TierSlug.QUANT_DESK, BillingInterval.MONTHLY),
    ("STRIPE_PRICE_QUANT_DESK_ANNUAL", TierSlug.QUANT_DESK, BillingInterval.ANNUAL),
    ("STRIPE_PRICE_ENTERPRISE_MONTHLY", TierSlug.ENTERPRISE, BillingInterval.MONTHLY),
    ("STRIPE_PRICE_ENTERPRISE_ANNUAL", TierSlug.ENTERPRISE, BillingInterval.ANNUAL),
)


class PriceCatalog:
    """Resolves Stripe Price IDs to internal tier slugs.

    Use ``PriceCatalog.from_env()`` for production, or construct directly with
    a dict for tests.
    """

    def __init__(self, entries: Mapping[str, PriceEntry]):
        # Detect duplicate price_ids early; if two tiers point at the same
        # price we'd silently mis-grant.
        seen: Dict[str, PriceEntry] = {}
        for pid, entry in entries.items():
            if pid != entry.price_id:
                raise ValueError(
                    f"PriceCatalog key/entry mismatch: key={pid!r} entry.price_id={entry.price_id!r}"
                )
            if pid in seen:
                raise ValueError(
                    f"Duplicate Stripe price ID {pid!r} mapped to both "
                    f"{seen[pid].tier.value} and {entry.tier.value}"
                )
            seen[pid] = entry
        self._by_price_id: Dict[str, PriceEntry] = dict(entries)

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "PriceCatalog":
        """Build from environment variables (or any mapping for tests)."""
        if env is None:
            from backend.config import settings

            env = {
                spec[0]: getattr(settings, spec[0], None) or ""
                for spec in _CATALOG_SPEC
            }
        entries: Dict[str, PriceEntry] = {}
        for env_key, tier, interval in _CATALOG_SPEC:
            price_id = (env.get(env_key) or "").strip()
            if not price_id:
                continue
            if price_id in entries:
                # Same env value used in two slots; almost certainly a misconfig.
                logger.warning(
                    "stripe price catalog: %s reuses price_id=%s (already mapped to %s)",
                    env_key,
                    price_id,
                    entries[price_id].tier.value,
                )
                continue
            entries[price_id] = PriceEntry(
                price_id=price_id, tier=tier, interval=interval
            )
        return cls(entries)

    def resolve(self, price_id: str) -> Optional[PriceEntry]:
        """Return the catalog entry for a Stripe Price ID, or None if unknown.

        An unknown price ID is *not* an exception — Stripe customers may have
        legacy prices we no longer offer. The webhook processor decides what
        to do (typically: log + leave entitlement unchanged).
        """
        return self._by_price_id.get(price_id)

    def all_entries(self) -> Tuple[PriceEntry, ...]:
        return tuple(self._by_price_id.values())

    def __len__(self) -> int:
        return len(self._by_price_id)

    def __contains__(self, price_id: object) -> bool:
        return isinstance(price_id, str) and price_id in self._by_price_id


def resolve_tier_for_price(
    price_id: str, catalog: Optional[PriceCatalog] = None
) -> Optional[TierSlug]:
    """Convenience: return the tier slug for a price ID, or None if unknown."""
    cat = catalog or PriceCatalog.from_env()
    entry = cat.resolve(price_id)
    return entry.tier if entry else None
