"""Market data services - price feed, indicators, universe, multi-timeframe."""

# Stage Analysis helpers: defined in stage_classifier, still re-exported from
# indicator_engine for backward compatibility. Prefer importing from
# backend.services.market.stage_classifier (or this package after migration).
# Do not remove indicator_engine re-exports until all call sites below are updated:
# - backend/tasks/market/history.py
# - backend/services/market/market_data_service.py
# - backend/tests/test_stage_classification.py, test_rs_mansfield.py,
#   test_pipeline_e2e.py, test_edge_cases.py, test_indicator_engine_stage_refinement.py
from .stage_classifier import (
    classify_stage_for_timeframe,
    classify_stage_scalar,
    classify_stage_series,
    compute_weinstein_stage_from_daily,
    compute_weinstein_stage_series_from_daily,
    weekly_from_daily,
)

from .price_feed import PriceFeedService, price_feed_service, BarData
from .multi_timeframe import MultiTimeframeEngine, MultiTimeframeResult, TimeframeStage

__all__ = [
    "PriceFeedService",
    "price_feed_service",
    "BarData",
    "MultiTimeframeEngine",
    "MultiTimeframeResult",
    "TimeframeStage",
    "weekly_from_daily",
    "classify_stage_for_timeframe",
    "classify_stage_scalar",
    "classify_stage_series",
    "compute_weinstein_stage_from_daily",
    "compute_weinstein_stage_series_from_daily",
]
