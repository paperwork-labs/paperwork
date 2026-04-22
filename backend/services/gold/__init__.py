"""
Medallion layer: gold. See docs/ARCHITECTURE.md and D127.
"""

from backend.services.gold.peak_signal_engine import (
    PeakSignal,
    PeakSignalEngine,
)
from backend.services.gold.pick_quality_scorer import (
    ComponentScore,
    PickQualityScore,
    PickQualityScorer,
)
from backend.services.gold.tax_aware_exit_calculator import (
    ExitLot,
    TaxAwareExitCalculator,
    TaxAwareExitResult,
    TaxProfile,
)
from backend.services.gold.trade_card_composer import (
    AlertItem,
    AlertLevel,
    ContractRecommendation,
    ContractStatus,
    ContractType,
    LimitPriceTier,
    LimitTier,
    OptionsChainSurface,
    SizingStatus,
    SizingTier,
    TradeCard,
    TradeCardComposer,
    trade_card_to_payload,
)
from backend.services.gold.winner_exit_advisor import (
    WinnerExitAdvice,
    WinnerExitAdvisor,
)

__all__ = [
    "AlertItem",
    "AlertLevel",
    "ComponentScore",
    "ContractRecommendation",
    "ContractStatus",
    "ContractType",
    "ExitLot",
    "LimitPriceTier",
    "LimitTier",
    "OptionsChainSurface",
    "PeakSignal",
    "PeakSignalEngine",
    "PickQualityScore",
    "PickQualityScorer",
    "SizingStatus",
    "SizingTier",
    "TaxAwareExitCalculator",
    "TaxAwareExitResult",
    "TaxProfile",
    "TradeCard",
    "TradeCardComposer",
    "WinnerExitAdvice",
    "WinnerExitAdvisor",
    "trade_card_to_payload",
]
