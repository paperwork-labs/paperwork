"""
Public Pricing Catalog API
==========================

``GET /api/v1/pricing/catalog`` — the wire format the public
``/pricing`` page renders. Intentionally **public** (no auth) so
logged-out visitors get the exact same data the in-app upgrade prompts
read.

Source of truth chain:

* Tier display data (price, tagline, "covers" copy) →
  ``tier_catalog.py``
* Feature catalog (which feature unlocks at which tier) →
  ``feature_catalog.py``

Both are re-rendered on every request through this endpoint, so the
frontend never duplicates either source. A 5-minute in-process cache
guards against a hot-loop of marketing-page hits hammering the worker
pool — but the cache is intentionally process-local (not Redis)
because the payload is sub-kilobyte and the catalog only changes on
deploy.

No new Stripe routes are introduced in this PR (per the v1 sprint plan
"do not invent new Stripe routes" constraint). Paid CTAs route to
``/register?upgrade=<tier>`` for unauthenticated visitors and remain
disabled with explanatory copy for signed-in visitors until the
checkout-session creation route lands.
"""
from __future__ import annotations

import threading
import time
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.rate_limit import limiter
from app.services.billing.feature_catalog import Feature
from app.services.billing.tier_catalog import (
    TierDisplay,
    all_tiers,
    features_for_tier,
    features_introduced_at_tier,
)

router = APIRouter(tags=["Pricing"])


# -----------------------------------------------------------------------------
# Wire schema
# -----------------------------------------------------------------------------


class PricingFeatureSchema(BaseModel):
    """One feature line as rendered on a tier card."""

    key: str
    title: str
    description: str
    category: str
    min_tier: str

    @classmethod
    def from_feature(cls, f: Feature) -> "PricingFeatureSchema":
        return cls(
            key=f.key,
            title=f.title,
            description=f.description,
            category=f.category,
            min_tier=f.min_tier.value,
        )


class PricingTierSchema(BaseModel):
    """One tier column on the pricing page.

    Prices are serialised as strings (rather than floats) so the
    frontend receives them with full ``Decimal`` precision and never
    accidentally rounds via JS ``Number`` parsing. Pricing display on
    the client uses ``Intl.NumberFormat`` directly on the string.
    """

    tier: str = Field(..., description="Canonical SubscriptionTier slug.")
    name: str
    tagline: str
    monthly_price_usd: Optional[str] = Field(
        None,
        description=(
            "Decimal price as a string (e.g. ``\"20.00\"``). Null only "
            "for tiers without a self-serve SKU (Enterprise)."
        ),
    )
    annual_price_usd: Optional[str] = Field(
        None,
        description=(
            "Annual total as a Decimal string. Null when no annual SKU "
            "exists. The frontend computes the savings badge from the "
            "monthly/annual pair; we don't ship a precomputed percent so "
            "the math stays inspectable in one place."
        ),
    )
    covers_copy: str = Field(
        ...,
        description=(
            "Transparent 'your subscription covers X' microcopy."
        ),
    )
    cta_label: str
    cta_route: Optional[str] = Field(
        None,
        description=(
            "Public route the CTA should navigate to "
            "(e.g. ``\"/register\"`` for Free). Null for paid tiers — "
            "the frontend owns the checkout integration."
        ),
    )
    is_contact_sales: bool = Field(
        False,
        description=(
            "True for tiers without self-serve checkout (Enterprise). "
            "Renders a ``mailto:`` CTA instead of an upgrade button."
        ),
    )
    features: List[PricingFeatureSchema] = Field(
        default_factory=list,
        description="Every feature included at this tier (cumulative).",
    )
    new_features: List[PricingFeatureSchema] = Field(
        default_factory=list,
        description=(
            "Features whose min_tier equals this tier — the diff vs "
            "the tier immediately below. Frontend uses this to mark "
            "'new' rows visually."
        ),
    )

    @classmethod
    def from_tier(cls, t: TierDisplay) -> "PricingTierSchema":
        return cls(
            tier=t.tier.value,
            name=t.name,
            tagline=t.tagline,
            monthly_price_usd=_format_decimal(t.monthly_price_usd),
            annual_price_usd=_format_decimal(t.annual_price_usd),
            covers_copy=t.covers_copy,
            cta_label=t.cta_label,
            cta_route=t.cta_route,
            is_contact_sales=t.is_contact_sales,
            features=[
                PricingFeatureSchema.from_feature(f)
                for f in features_for_tier(t.tier)
            ],
            new_features=[
                PricingFeatureSchema.from_feature(f)
                for f in features_introduced_at_tier(t.tier)
            ],
        )


class PricingCatalogResponse(BaseModel):
    """Top-level shape consumed by ``frontend/src/pages/Pricing.tsx``."""

    tiers: List[PricingTierSchema]
    currency: str = Field(
        default="USD", description="ISO 4217 currency code."
    )


def _format_decimal(value: Optional[Decimal]) -> Optional[str]:
    """Render a ``Decimal`` price as a normalised string.

    We standardise on two decimal places so the frontend never has to
    decide between ``"20"`` and ``"20.00"`` when formatting.
    """
    if value is None:
        return None
    return f"{value:.2f}"


# -----------------------------------------------------------------------------
# Cache (process-local, 5 minutes)
# -----------------------------------------------------------------------------
#
# The pricing payload is deterministic for the lifetime of the deployed
# image: it depends only on ``tier_catalog._TIERS`` +
# ``feature_catalog._FEATURES``, both of which are immutable
# module-level constants. A lock protects the initial build under
# concurrent first-hit traffic; subsequent reads are lock-free.

_CACHE_TTL_S: float = 300.0
_cache_lock = threading.Lock()
_cached_payload: Optional[PricingCatalogResponse] = None
_cached_at: float = 0.0


def _build_payload() -> PricingCatalogResponse:
    return PricingCatalogResponse(
        tiers=[PricingTierSchema.from_tier(t) for t in all_tiers()],
        currency="USD",
    )


def _get_or_build() -> PricingCatalogResponse:
    """Return the cached payload, rebuilding past TTL.

    Uses a coarse double-checked-lock pattern. The build is
    microseconds in practice (it's a few list comprehensions over ~25
    items), so we optimise for read clarity rather than write
    parallelism.
    """
    global _cached_payload, _cached_at
    now = time.monotonic()
    cached = _cached_payload
    if cached is not None and (now - _cached_at) < _CACHE_TTL_S:
        return cached
    with _cache_lock:
        now = time.monotonic()
        if (
            _cached_payload is None
            or (now - _cached_at) >= _CACHE_TTL_S
        ):
            _cached_payload = _build_payload()
            _cached_at = now
        return _cached_payload


def reset_cache() -> None:
    """Drop the in-process cache (test isolation only)."""
    global _cached_payload, _cached_at
    with _cache_lock:
        _cached_payload = None
        _cached_at = 0.0


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.get("/catalog", response_model=PricingCatalogResponse)
@limiter.limit("120/minute")
def get_pricing_catalog(request: Request) -> PricingCatalogResponse:
    """Public pricing catalog. Cached in-process for 5 minutes.

    No auth required — this is the same data the marketing page and
    the in-app upgrade prompts both render. Returning the catalog here
    (rather than reusing ``/api/v1/entitlements/catalog``) lets us add
    tier-side metadata (price, copy, CTA) without polluting the
    entitlements wire format that other clients already depend on.
    """
    return _get_or_build()
