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
from backend.services.gold.winner_exit_advisor import (
    WinnerExitAdvice,
    WinnerExitAdvisor,
)

__all__ = [
    "ComponentScore",
    "ExitLot",
    "PeakSignal",
    "PeakSignalEngine",
    "PickQualityScore",
    "PickQualityScorer",
    "TaxAwareExitCalculator",
    "TaxAwareExitResult",
    "TaxProfile",
    "WinnerExitAdvice",
    "WinnerExitAdvisor",
]
