"""
Feature Catalog
===============

The canonical mapping from a feature key to the minimum subscription tier
required to use it. This module is the *only* place where tier-to-feature
policy is encoded. Both the backend (FastAPI dependencies, Celery tasks,
brain tools) and the frontend (``useEntitlement`` + ``TierGate``) read from
this catalog so the two sides cannot drift.

How to add a feature
--------------------

1. Pick a stable key in the form ``namespace.feature_name``. Use lowercase
   snake_case. Examples: ``picks.read``, ``picks.autotrade``,
   ``brain.native_chat``, ``broker.multi``.
2. Add it to ``_CATALOG`` below with the **minimum** tier that should see
   it.
3. Wrap the route or component using that key. Never inline a tier check
   (`if user.tier == "pro_plus"`) anywhere else in the codebase.

Why a catalog and not decorators on each route
----------------------------------------------

The product/pricing team needs to be able to read this file and answer
"what does Pro+ get?" without grepping the entire backend. Putting the
data here also lets us expose a public ``/entitlements/catalog`` endpoint
so the marketing site and frontend can render the pricing table without
duplicating the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from backend.models.entitlement import SubscriptionTier


@dataclass(frozen=True)
class Feature:
    """Definition of a gated feature.

    Attributes:
        key: stable identifier; never rename, only deprecate.
        min_tier: minimum tier that unlocks this feature.
        title: short user-facing label (used by upgrade prompts).
        description: one-line user-facing description.
        category: logical grouping for the pricing UI (``data``, ``picks``,
            ``brain``, ``execution``, ``ops``, ``research``).
    """

    key: str
    min_tier: SubscriptionTier
    title: str
    description: str
    category: str


# -----------------------------------------------------------------------------
# Catalog
# -----------------------------------------------------------------------------
# Order matters only for the public catalog response; group by category to
# make the rendered pricing page natural to read.

_FEATURES: tuple[Feature, ...] = (
    # ---- Market data & visualization (data) ---------------------------------
    Feature(
        key="data.cached_indicators",
        min_tier=SubscriptionTier.FREE,
        title="Cached indicators",
        description="Daily SMA, RSI, ATR, Stage on watched symbols.",
        category="data",
    ),
    Feature(
        key="data.realtime_pipeline",
        min_tier=SubscriptionTier.PRO,
        title="Real-time pipeline",
        description="Live recompute when prices update intraday.",
        category="data",
    ),
    Feature(
        key="data.snowball_viz",
        min_tier=SubscriptionTier.PRO,
        title="Snowball-class visualization",
        description="Sector heatmaps, return attribution, dividend timeline.",
        category="data",
    ),
    Feature(
        key="data.point_in_time_history",
        min_tier=SubscriptionTier.PRO_PLUS,
        title="Point-in-time history reads",
        description="As-of reads against MarketSnapshotHistory ledger.",
        category="data",
    ),
    # ---- Picks & validator (picks) -----------------------------------------
    Feature(
        key="picks.read",
        min_tier=SubscriptionTier.PRO,
        title="Validated picks",
        description="Curated buy/sell/trim ideas with rationale.",
        category="picks",
    ),
    Feature(
        key="picks.feed_full",
        min_tier=SubscriptionTier.LITE,
        title="Full picks feed",
        description="See every published pick in real time (not preview-only).",
        category="picks",
    ),
    Feature(
        key="picks.autotrade",
        min_tier=SubscriptionTier.PRO,
        title="One-click pick execution",
        description="Send a validated pick straight to your broker.",
        category="picks",
    ),
    Feature(
        key="picks.full_rationale",
        min_tier=SubscriptionTier.PRO_PLUS,
        title="Full pick rationale",
        description="Source emails, X threads, indicator deltas, regime context.",
        category="picks",
    ),
    # ---- Native AgentBrain chat (brain) ------------------------------------
    Feature(
        key="brain.native_chat",
        min_tier=SubscriptionTier.PRO_PLUS,
        title="Native AgentBrain chat",
        description="Ask the in-app brain about your portfolio and the market.",
        category="brain",
    ),
    Feature(
        key="brain.nl_query",
        min_tier=SubscriptionTier.PRO_PLUS,
        title="Natural-language screen",
        description="\"Show me Stage 2A under $50 with insider buying\".",
        category="brain",
    ),
    Feature(
        key="brain.incident_postmortem",
        min_tier=SubscriptionTier.QUANT_DESK,
        title="Incident postmortem",
        description="Auto-generated RCA when a red status persists.",
        category="brain",
    ),
    # ---- Execution & brokers (execution) -----------------------------------
    Feature(
        key="execution.single_broker",
        min_tier=SubscriptionTier.PRO,
        title="Single-broker autotrade",
        description="Connect one broker (IBKR, TastyTrade, or Schwab).",
        category="execution",
    ),
    Feature(
        key="execution.multi_broker",
        min_tier=SubscriptionTier.PRO_PLUS,
        title="Multi-broker aggregation",
        description="Connect every broker, see one unified portfolio.",
        category="execution",
    ),
    Feature(
        key="execution.tax_aware_exit",
        min_tier=SubscriptionTier.PRO_PLUS,
        title="Tax-aware exits",
        description="Exit cascade prefers long-term lots and harvests losses.",
        category="execution",
    ),
    Feature(
        key="execution.rebalance",
        min_tier=SubscriptionTier.PRO_PLUS,
        title="Rebalance engine",
        description="Trim/add to hit target weights without round-trips.",
        category="execution",
    ),
    # ---- Research kit (research) -------------------------------------------
    Feature(
        key="research.backtest_api",
        min_tier=SubscriptionTier.QUANT_DESK,
        title="Backtest API",
        description="Programmatic walk-forward backtests with cost models.",
        category="research",
    ),
    Feature(
        key="research.jupyter_kit",
        min_tier=SubscriptionTier.QUANT_DESK,
        title="Jupyter research kit",
        description="Read-only notebook env with point-in-time data.",
        category="research",
    ),
    Feature(
        key="research.custom_universe",
        min_tier=SubscriptionTier.QUANT_DESK,
        title="Custom universe",
        description="Bring your own symbol list / sector classification.",
        category="research",
    ),
    # ---- Ops & enterprise (ops) --------------------------------------------
    Feature(
        key="ops.audit_export",
        min_tier=SubscriptionTier.ENTERPRISE,
        title="Audit log export",
        description="Stream the full action log to your SIEM.",
        category="ops",
    ),
    Feature(
        key="ops.sso",
        min_tier=SubscriptionTier.ENTERPRISE,
        title="Single sign-on",
        description="SAML / OIDC.",
        category="ops",
    ),
    Feature(
        key="ops.dedicated_cluster",
        min_tier=SubscriptionTier.ENTERPRISE,
        title="Dedicated cluster",
        description="Isolated infra with custom SLA.",
        category="ops",
    ),
)


_CATALOG: Mapping[str, Feature] = {f.key: f for f in _FEATURES}


def get_feature(key: str) -> Feature:
    """Look up a feature by key.

    Raises:
        KeyError: if the feature is unknown. We raise rather than return
            None so a typo'd key fails loudly rather than silently
            granting access to everyone.
    """
    if key not in _CATALOG:
        raise KeyError(
            f"Unknown feature key '{key}'. "
            f"Add it to backend/services/billing/feature_catalog.py first."
        )
    return _CATALOG[key]


def all_features() -> tuple[Feature, ...]:
    """Return every feature as an ordered tuple. Used by the public catalog
    endpoint and the Vitest snapshot guard so the catalog never silently
    shrinks."""
    return _FEATURES


def is_allowed(tier: SubscriptionTier, feature_key: str) -> bool:
    """Return True if a user at ``tier`` can access ``feature_key``.

    A pro_plus user satisfies any pro/lite/free requirement, etc. (see
    ``SubscriptionTier.rank``).
    """
    feature = get_feature(feature_key)
    return SubscriptionTier.rank(tier) >= SubscriptionTier.rank(feature.min_tier)
