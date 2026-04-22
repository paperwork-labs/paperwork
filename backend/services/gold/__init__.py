"""Medallion layer: gold. See docs/ARCHITECTURE.md and D127."""

from backend.services.gold.pick_quality_scorer import (
    ComponentScore,
    PickQualityScore,
    PickQualityScorer,
)

__all__ = [
    "ComponentScore",
    "PickQualityScore",
    "PickQualityScorer",
]
