"""
Pricing Tier Display Catalog
============================

Display-side companion to ``feature_catalog.py``. The feature catalog
answers "which tier unlocks feature X?". This module answers "what does
each tier look like on the public ``/pricing`` page?".

Single source of truth for:

* Tier price (monthly + annual), expressed as ``Decimal`` so we never
  introduce float imprecision into anything money-touching.
* Tagline + transparent "your subscription covers" microcopy
  (per Master Plan D106 + section 3l-iii).
* CTA label per tier.

Per-tier feature lists are derived from
``feature_catalog.all_features()`` — never duplicated here. A tier card
shows every feature whose ``min_tier.rank()`` is less than or equal to
that tier (the ladder is monotonic, so each higher tier sees everything
below plus its own additions).

Why a separate module rather than extending ``feature_catalog.py``?

The feature catalog is a *policy* file (which features gate which
tier). The tier catalog is a *marketing* file (price, copy, CTA
wording). They change at different rhythms; conflating them would mean
every copy tweak touches the policy file.

medallion: ops
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.entitlement import SubscriptionTier
from app.services.billing.feature_catalog import Feature, all_features

# -----------------------------------------------------------------------------
# Tier display dataclass
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class TierDisplay:
    """Marketing-side metadata for one tier on the public pricing page.

    Attributes:
        tier: The canonical tier slug (mirrors ``SubscriptionTier`` value).
        name: User-facing display name (e.g. ``"Pro+"`` not ``"pro_plus"``).
        tagline: One-line headline shown under the tier name.
        monthly_price_usd: Monthly price as ``Decimal``. ``Decimal("0")``
            for Free; ``None`` for Enterprise (contract-billed).
        annual_price_usd: Annual price (total, not monthly equivalent)
            as ``Decimal``. ``None`` when no annual SKU exists for the
            tier.
        covers_copy: The "Your subscription covers X" microcopy that
            turns the price into a transparent pass-through (D106).
            Free tier uses this slot for the "no ads / no data sale"
            promise.
        cta_label: Button text. ``"Get started"`` for Free,
            ``"Upgrade"`` for paid tiers, ``"Contact sales"`` for
            Enterprise.
        is_contact_sales: True for tiers that don't go through
            self-serve checkout (Enterprise). Drives a ``mailto:`` CTA
            instead of a checkout flow.
        cta_route: Public route a free CTA should navigate to.
            ``"/register"`` for Free; ``None`` for paid tiers (the
            frontend owns checkout wiring; see the route module docstring
            for why we don't ship a new Stripe route in this PR).
    """

    tier: SubscriptionTier
    name: str
    tagline: str
    monthly_price_usd: Decimal | None
    annual_price_usd: Decimal | None
    covers_copy: str
    cta_label: str
    is_contact_sales: bool
    cta_route: str | None
    mcp_tool_scope: tuple[str, ...]
    native_chat_daily_limit: int | None
    byok_enabled: bool


# -----------------------------------------------------------------------------
# Tier display table
# -----------------------------------------------------------------------------
#
# Prices below come from the v1 sprint plan ("Cost reality (locked
# answers)" section) and the inline transparency microcopy spec in
# 3l-iii. When prices change, update only this table — both the backend
# catalog endpoint and the frontend pricing page rerender from it
# automatically.
#
# Decimal literals are written as strings so we never accidentally
# inherit float imprecision from the parser.


_TIERS: tuple[TierDisplay, ...] = (
    TierDisplay(
        tier=SubscriptionTier.FREE,
        name="Free",
        tagline="Gorgeous charts. Forever free.",
        monthly_price_usd=Decimal("0"),
        annual_price_usd=Decimal("0"),
        covers_copy=("Built so we can stay free. No ads. No data sale. Ever."),
        cta_label="Get started",
        is_contact_sales=False,
        cta_route="/register",
        mcp_tool_scope=("mcp.read_portfolio",),
        native_chat_daily_limit=0,
        byok_enabled=False,
    ),
    TierDisplay(
        tier=SubscriptionTier.PRO,
        name="Pro",
        tagline="Signals and BYOK for active traders.",
        monthly_price_usd=Decimal("29"),
        annual_price_usd=Decimal("290"),
        covers_copy=(
            "Covers core compute and sync with native chat (20/day). "
            "Bring your own OpenAI/Anthropic key for heavier use."
        ),
        cta_label="Upgrade",
        is_contact_sales=False,
        cta_route=None,
        mcp_tool_scope=("mcp.read_portfolio", "mcp.read_signals"),
        native_chat_daily_limit=20,
        byok_enabled=True,
    ),
    TierDisplay(
        tier=SubscriptionTier.PRO_PLUS,
        name="Pro+",
        tagline="Trade cards, replay, tax engine, unlimited chat.",
        monthly_price_usd=Decimal("79"),
        annual_price_usd=Decimal("790"),
        covers_copy=(
            "Adds deeper MCP strategy tools and unlimited native AgentBrain "
            "for high-frequency workflows."
        ),
        cta_label="Upgrade",
        is_contact_sales=False,
        cta_route=None,
        mcp_tool_scope=(
            "mcp.read_portfolio",
            "mcp.read_signals",
            "mcp.read_trade_cards",
            "mcp.read_replay",
            "mcp.read_tax_engine",
        ),
        native_chat_daily_limit=None,
        byok_enabled=True,
    ),
    TierDisplay(
        tier=SubscriptionTier.QUANT_DESK,
        name="Quant Desk",
        tagline="Research kit, custom universes, plugin SDK.",
        monthly_price_usd=Decimal("299"),
        annual_price_usd=Decimal("2990"),
        covers_copy=(
            "Covers Jupyter compute, point-in-time history reads, and "
            "the backtest API. The same infra a small fund pays five "
            "figures a year for, billed at our cost plus headroom."
        ),
        cta_label="Upgrade",
        is_contact_sales=False,
        cta_route=None,
        mcp_tool_scope=(
            "mcp.read_portfolio",
            "mcp.read_signals",
            "mcp.read_trade_cards",
            "mcp.read_replay",
            "mcp.read_tax_engine",
            "mcp.read_backtest",
            "mcp.read_jupyter",
            "mcp.custom_tools",
        ),
        native_chat_daily_limit=None,
        byok_enabled=True,
    ),
    TierDisplay(
        tier=SubscriptionTier.ENTERPRISE,
        name="Enterprise",
        tagline="SSO, dedicated cluster, custom SLA.",
        monthly_price_usd=None,
        annual_price_usd=None,
        covers_copy=(
            "Covers SAML/OIDC, isolated infrastructure, audit log "
            "export, and a named on-call. Priced per engagement so your "
            "bill matches your footprint."
        ),
        cta_label="Contact sales",
        is_contact_sales=True,
        cta_route=None,
        mcp_tool_scope=(
            "mcp.read_portfolio",
            "mcp.read_signals",
            "mcp.read_trade_cards",
            "mcp.read_replay",
            "mcp.read_tax_engine",
            "mcp.read_backtest",
            "mcp.read_jupyter",
            "mcp.custom_tools",
            "mcp.admin_scopes",
        ),
        native_chat_daily_limit=None,
        byok_enabled=True,
    ),
)


# Defensive: catalog must enumerate every tier exactly once. A drift
# here would silently drop a column on the pricing page, which is
# exactly the kind of "looks fine in dev, missing in prod" failure the
# no-silent-fallback rule warns against.
def _validate_tier_coverage() -> None:
    expected = {t for t in SubscriptionTier}
    actual = {t.tier for t in _TIERS}
    if expected != actual:
        missing = expected - actual
        extra = actual - expected
        raise RuntimeError(
            "tier_catalog._TIERS does not cover every SubscriptionTier "
            f"exactly once. missing={sorted(t.value for t in missing)} "
            f"extra={sorted(t.value for t in extra)}"
        )


_validate_tier_coverage()


# -----------------------------------------------------------------------------
# Public accessors
# -----------------------------------------------------------------------------


def all_tiers() -> tuple[TierDisplay, ...]:
    """Return every tier in display order (Free → Enterprise)."""
    return _TIERS


def mcp_scopes_for_tier(tier: SubscriptionTier) -> tuple[str, ...]:
    """Return MCP scopes granted at the effective tier."""
    for row in _TIERS:
        if row.tier == tier:
            return row.mcp_tool_scope
    return ()


def mcp_daily_call_limit(tier: SubscriptionTier) -> int | None:
    """Daily MCP call caps by tier. None means unlimited."""
    limits = {
        SubscriptionTier.FREE: 100,
        SubscriptionTier.PRO: 1000,
        SubscriptionTier.PRO_PLUS: 10_000,
        SubscriptionTier.QUANT_DESK: None,
        SubscriptionTier.ENTERPRISE: None,
    }
    return limits.get(tier, 100)


def features_for_tier(tier: SubscriptionTier) -> tuple[Feature, ...]:
    """Return every feature included at ``tier`` (i.e. min_tier <= tier).

    Order follows the catalog's natural grouping (data, picks, brain,
    ...) so the rendered card reads top-to-bottom in the same order on
    every tier — consistency the eye relies on when scanning a
    comparison.
    """
    target_rank = SubscriptionTier.rank(tier)
    return tuple(f for f in all_features() if SubscriptionTier.rank(f.min_tier) <= target_rank)


def features_introduced_at_tier(
    tier: SubscriptionTier,
) -> tuple[Feature, ...]:
    """Return only the features whose ``min_tier`` equals ``tier``.

    Useful when rendering "What's new at this tier" highlight blocks so
    we don't repeat the entire ladder under every column.
    """
    return tuple(f for f in all_features() if f.min_tier == tier)
