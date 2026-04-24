"""Market data services - indicators, universe, multi-timeframe.

medallion: silver
"""

from .stage_classifier import (
    classify_stage_for_timeframe,
    classify_stage_scalar,
    classify_stage_series,
    compute_weinstein_stage_from_daily,
    compute_weinstein_stage_series_from_daily,
    weekly_from_daily,
)

from .multi_timeframe import MultiTimeframeEngine, MultiTimeframeResult, TimeframeStage

__all__ = [
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
