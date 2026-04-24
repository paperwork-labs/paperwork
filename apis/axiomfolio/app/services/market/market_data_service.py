"""Service graph factory — creates and exports market data sub-service singletons.

Callers import the specific sub-service they need:

    from app.services.market.market_data_service import snapshot_builder
    snap = await snapshot_builder.get_snapshot(symbol)

Construction order is linear and acyclic:
    MarketInfra -> PriceBarWriter -> ProviderRouter -> FundamentalsService
    -> QuoteService -> IndexUniverseService -> SnapshotBuilder -> CoverageAnalytics

medallion: silver
"""

from __future__ import annotations

import logging

from app.services.market.coverage_analytics import CoverageAnalytics
from app.services.market.fundamentals_service import FundamentalsService
from app.services.market.index_universe_service import IndexUniverseService
from app.services.market.market_infra import MarketInfra
from app.services.market.price_bar_writer import PriceBarWriter
from app.services.market.provider_router import (
    ProviderRouter,
)
from app.services.market.quote_service import QuoteService
from app.services.market.snapshot_builder import SnapshotBuilder
from app.services.market.stage_quality_service import (
    StageQualityService,
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
