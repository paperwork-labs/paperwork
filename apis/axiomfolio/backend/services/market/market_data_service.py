"""Service graph factory — creates and exports market data sub-service singletons.

Callers import the specific sub-service they need:

    from backend.services.market.market_data_service import snapshot_builder
    snap = await snapshot_builder.get_snapshot(symbol)

Construction order is linear and acyclic:
    MarketInfra -> PriceBarWriter -> ProviderRouter -> FundamentalsService
    -> QuoteService -> IndexUniverseService -> SnapshotBuilder -> CoverageAnalytics

medallion: silver
"""
from __future__ import annotations

import logging

from backend.services.market.market_infra import MarketInfra
from backend.services.market.price_bar_writer import PriceBarWriter
from backend.services.market.provider_router import (
    ProviderRouter,
    APIProvider,
    _last_n_trading_sessions,
    _is_l2_fresh,
    L2_FRESHNESS_MAX_DAYS,
    _cb_failures,
    _cb_open_until,
    _cb_lock,
)
from backend.services.market.fundamentals_service import FundamentalsService, needs_fundamentals
from backend.services.market.quote_service import QuoteService
from backend.services.market.index_universe_service import IndexUniverseService
from backend.services.market.snapshot_builder import SnapshotBuilder
from backend.services.market.coverage_analytics import CoverageAnalytics
from backend.services.market.stage_quality_service import (
    StageQualityService,
    normalize_stage_label,
    VALID_STAGE_LABELS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service graph — constructed once at import time, acyclic
# ---------------------------------------------------------------------------

infra = MarketInfra()
price_bars = PriceBarWriter()
provider_router = ProviderRouter(infra, price_bars)
fundamentals = FundamentalsService(infra, provider_router)
quote = QuoteService(infra, provider_router, fundamentals)
index_universe = IndexUniverseService(infra)
snapshot_builder = SnapshotBuilder(provider_router, quote, fundamentals)
coverage_analytics = CoverageAnalytics(infra)
stage_quality = StageQualityService()
