"""
Broker catalog — single source of truth for the connection hub.
================================================================

This module defines the static catalog of brokers we surface in the
``/connect`` UI and the typed shape returned by the
``GET /api/v1/portfolio/connection-options`` endpoint.

The catalog is intentionally a static, typed list (not a DB table) for v1:
- The set of brokers changes on the order of weeks/months, not minutes.
- Storing it in the DB would add migration overhead with zero behavior win.
- Keeping it in code lets it evolve under code review and ship with frontend.

When a broker graduates from ``coming_v1_1`` to ``available`` (or new
brokers are added), update this file and the corresponding logo asset.

Per D100/D101b: connection hub is the v1 connectivity UX. The catalog
explicitly distinguishes (a) brokers we already integrate via OAuth,
(b) brokers gated behind CSV/statement import (the ~50% of US retail
behind brokers that refuse to expose APIs), (c) brokers queued for v1.1
OAuth, and (d) brokers gated behind v1.2 SnapTrade (Pro).

medallion: silver
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


BrokerCategory = Literal["stocks", "crypto", "retirement"]
ConnectionMethod = Literal["oauth", "import"]
BrokerStatus = Literal["available", "coming_v1_1", "coming_v1_2_snaptrade"]


class BrokerCatalogEntry(BaseModel):
    """One broker in the connection-hub catalog.

    ``slug`` is the stable identifier used by the frontend to dispatch
    per-broker flows (OAuth route, CSV import template, notify-me payload).
    Treat it like a primary key — never rename without a migration of any
    tables that reference it.
    """

    slug: str = Field(..., description="Stable identifier; do not rename.")
    name: str = Field(..., description="Human-readable broker name.")
    description: str = Field(
        ..., description="One-sentence pitch; rendered under the logo."
    )
    logo_url: str = Field(
        ...,
        description=(
            "Path under /broker-logos/<slug>.svg served from frontend/public. "
            "Frontend renders a fallback monogram if the asset is missing."
        ),
    )
    category: BrokerCategory
    method: ConnectionMethod
    status: BrokerStatus
    aum_rank: Optional[int] = Field(
        default=None,
        description=(
            "Rough US retail AUM ranking (1 = largest). Used by the frontend "
            "to sort 'Stocks' brokers by relevance, not alphabetically."
        ),
    )


# -----------------------------------------------------------------------------
# Catalog
# -----------------------------------------------------------------------------
# Order within each category roughly tracks US retail AUM (Fidelity #1, etc.)
# so the most-relevant brokers surface first when filters are applied. The
# frontend may re-sort, but this is the canonical declared order.

_CATALOG: List[BrokerCatalogEntry] = [
    # ---- Stocks: OAuth available (the three brokers we already integrate) ----
    BrokerCatalogEntry(
        slug="schwab",
        name="Charles Schwab",
        description="Connect via OAuth to sync positions, trades, and dividends.",
        logo_url="/broker-logos/schwab.svg",
        category="stocks",
        method="oauth",
        status="available",
        aum_rank=2,
    ),
    BrokerCatalogEntry(
        slug="ibkr",
        name="Interactive Brokers",
        description="Connect via FlexQuery to sync positions, trades, and tax lots.",
        logo_url="/broker-logos/ibkr.svg",
        category="stocks",
        method="oauth",
        status="available",
        aum_rank=6,
    ),
    BrokerCatalogEntry(
        slug="tastytrade",
        name="Tastytrade",
        description="Connect via OAuth to sync positions, trades, and options.",
        logo_url="/broker-logos/tastytrade.svg",
        category="stocks",
        method="oauth",
        status="available",
        aum_rank=7,
    ),
    # ---- Stocks: import-only (brokers without retail APIs) ----
    BrokerCatalogEntry(
        slug="fidelity",
        name="Fidelity",
        description="Largest US retail broker. Import via CSV or forward your statement.",
        logo_url="/broker-logos/fidelity.svg",
        category="stocks",
        method="import",
        status="available",
        aum_rank=1,
    ),
    BrokerCatalogEntry(
        slug="vanguard",
        name="Vanguard",
        description="Import via CSV or statement PDF. Vanguard does not expose a retail API.",
        logo_url="/broker-logos/vanguard.svg",
        category="stocks",
        method="import",
        status="available",
        aum_rank=3,
    ),
    BrokerCatalogEntry(
        slug="robinhood",
        name="Robinhood",
        description="Import via CSV. One-click via Pro (SnapTrade) ships in v1.2.",
        logo_url="/broker-logos/robinhood.svg",
        category="stocks",
        method="import",
        status="available",
        aum_rank=4,
    ),
    BrokerCatalogEntry(
        slug="jpmorgan",
        name="JPMorgan Self-Directed",
        description="Import via CSV or statement PDF. No retail API available.",
        logo_url="/broker-logos/jpmorgan.svg",
        category="stocks",
        method="import",
        status="available",
        aum_rank=5,
    ),
    BrokerCatalogEntry(
        slug="merrill",
        name="Merrill Edge",
        description="Import via CSV or statement PDF. No retail API available.",
        logo_url="/broker-logos/merrill.svg",
        category="stocks",
        method="import",
        status="available",
        aum_rank=8,
    ),
    BrokerCatalogEntry(
        slug="wells_fargo",
        name="Wells Fargo Advisors",
        description="Import via CSV or statement PDF. No retail API available.",
        logo_url="/broker-logos/wells_fargo.svg",
        category="stocks",
        method="import",
        status="available",
        aum_rank=9,
    ),
    BrokerCatalogEntry(
        slug="webull",
        name="Webull",
        description="Import via CSV. One-click via Pro (SnapTrade) ships in v1.2.",
        logo_url="/broker-logos/webull.svg",
        category="stocks",
        method="import",
        status="available",
    ),
    BrokerCatalogEntry(
        slug="m1_finance",
        name="M1 Finance",
        description="Import via CSV. One-click via Pro (SnapTrade) ships in v1.2.",
        logo_url="/broker-logos/m1_finance.svg",
        category="stocks",
        method="import",
        status="available",
    ),
    BrokerCatalogEntry(
        slug="sofi",
        name="SoFi Invest",
        description="Import via CSV. One-click via Pro (SnapTrade) ships in v1.2.",
        logo_url="/broker-logos/sofi.svg",
        category="stocks",
        method="import",
        status="available",
    ),
    BrokerCatalogEntry(
        slug="public",
        name="Public",
        description="Import via CSV. One-click via Pro (SnapTrade) ships in v1.2.",
        logo_url="/broker-logos/public.svg",
        category="stocks",
        method="import",
        status="available",
    ),
    BrokerCatalogEntry(
        slug="generic_csv",
        name="Generic CSV",
        description="Don't see your broker? Map columns from any CSV export.",
        logo_url="/broker-logos/generic_csv.svg",
        category="stocks",
        method="import",
        status="available",
    ),
    # ---- Retirement / robo (import) ----
    BrokerCatalogEntry(
        slug="wealthfront",
        name="Wealthfront",
        description="Import via CSV or statement PDF. No retail API available.",
        logo_url="/broker-logos/wealthfront.svg",
        category="retirement",
        method="import",
        status="available",
    ),
    BrokerCatalogEntry(
        slug="betterment",
        name="Betterment",
        description="Import via CSV or statement PDF. No retail API available.",
        logo_url="/broker-logos/betterment.svg",
        category="retirement",
        method="import",
        status="available",
    ),
    # ---- Crypto (import for now; Coinbase OAuth queued) ----
    BrokerCatalogEntry(
        slug="coinbase_pro",
        name="Coinbase Pro (Advanced)",
        description="Import via CSV today. OAuth ships in v1.1.",
        logo_url="/broker-logos/coinbase_pro.svg",
        category="crypto",
        method="import",
        status="available",
    ),
    # ---- v1.1 OAuth queue (Notify me) ----
    BrokerCatalogEntry(
        slug="etrade",
        name="E*TRADE",
        description="OAuth integration ships in v1.1. Get notified when it's live.",
        logo_url="/broker-logos/etrade.svg",
        category="stocks",
        method="oauth",
        status="coming_v1_1",
    ),
    BrokerCatalogEntry(
        slug="tradier",
        name="Tradier",
        description="OAuth integration ships in v1.1. Get notified when it's live.",
        logo_url="/broker-logos/tradier.svg",
        category="stocks",
        method="oauth",
        status="coming_v1_1",
    ),
    BrokerCatalogEntry(
        slug="coinbase",
        name="Coinbase",
        description="OAuth integration ships in v1.1. Get notified when it's live.",
        logo_url="/broker-logos/coinbase.svg",
        category="crypto",
        method="oauth",
        status="coming_v1_1",
    ),
    BrokerCatalogEntry(
        slug="kraken",
        name="Kraken",
        description="OAuth integration ships in v1.1. Get notified when it's live.",
        logo_url="/broker-logos/kraken.svg",
        category="crypto",
        method="oauth",
        status="coming_v1_1",
    ),
    # ---- v1.2 SnapTrade (Pro) ----
    BrokerCatalogEntry(
        slug="robinhood_snaptrade",
        name="Robinhood (one-click)",
        description="One-click via SnapTrade. Available on Pro in v1.2.",
        logo_url="/broker-logos/robinhood.svg",
        category="stocks",
        method="oauth",
        status="coming_v1_2_snaptrade",
    ),
    BrokerCatalogEntry(
        slug="webull_snaptrade",
        name="Webull (one-click)",
        description="One-click via SnapTrade. Available on Pro in v1.2.",
        logo_url="/broker-logos/webull.svg",
        category="stocks",
        method="oauth",
        status="coming_v1_2_snaptrade",
    ),
    BrokerCatalogEntry(
        slug="public_snaptrade",
        name="Public (one-click)",
        description="One-click via SnapTrade. Available on Pro in v1.2.",
        logo_url="/broker-logos/public.svg",
        category="stocks",
        method="oauth",
        status="coming_v1_2_snaptrade",
    ),
    BrokerCatalogEntry(
        slug="m1_snaptrade",
        name="M1 Finance (one-click)",
        description="One-click via SnapTrade. Available on Pro in v1.2.",
        logo_url="/broker-logos/m1_finance.svg",
        category="stocks",
        method="oauth",
        status="coming_v1_2_snaptrade",
    ),
    BrokerCatalogEntry(
        slug="sofi_snaptrade",
        name="SoFi Invest (one-click)",
        description="One-click via SnapTrade. Available on Pro in v1.2.",
        logo_url="/broker-logos/sofi.svg",
        category="stocks",
        method="oauth",
        status="coming_v1_2_snaptrade",
    ),
]


# Map BrokerCatalogEntry.slug -> BrokerType.value for the brokers we
# actually persist as ``BrokerAccount`` rows today. Used by the connection-
# options route to derive ``user_state.connected`` from existing rows.
SLUG_TO_BROKER_TYPE: Dict[str, str] = {
    "schwab": "schwab",
    "ibkr": "ibkr",
    "tastytrade": "tastytrade",
    "fidelity": "fidelity",
    "robinhood": "robinhood",
}


def get_catalog() -> List[BrokerCatalogEntry]:
    """Return a fresh copy of the broker catalog.

    Returns a new list each call so callers cannot mutate the module-level
    constant by accident (defensive copy; cheap because the entries are
    immutable pydantic models).
    """

    return list(_CATALOG)


def get_broker_by_slug(slug: str) -> Optional[BrokerCatalogEntry]:
    """Look up a single catalog entry by slug. ``None`` if not present."""

    for entry in _CATALOG:
        if entry.slug == slug:
            return entry
    return None
