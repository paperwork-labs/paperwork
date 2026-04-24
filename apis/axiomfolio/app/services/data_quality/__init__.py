"""
Data Quality Layer
==================

Read-side validation that sits between provider clients and our
canonical stores (``MarketSnapshot``, ``MarketSnapshotHistory``,
``PriceData``).

Two cooperating modules:

* :class:`QuorumService` -- "do N providers agree on (symbol, field)?"
* :class:`DriftDetector` -- "is this provider drifting from its own
  recent history?"

Tolerances are centralised in :mod:`tolerances` so changing them is a
one-line audit. Both services accept ``Decimal`` only -- floats are
rejected loudly so we never invent disagreements out of binary
floating-point noise (R32, R34, R38).

medallion: silver
"""

from .drift_detector import DriftDetector, DriftDetectorResult, DriftEvent
from .quorum_service import QuorumResult, QuorumService
from .tolerances import (
    DEFAULT_NUMERIC_TOLERANCE_PCT,
    DEFAULT_QUORUM_THRESHOLD,
    EXACT_TOLERANCE,
    FUNDAMENTALS_TOLERANCE_PCT,
    PRICE_TOLERANCE_PCT,
    VOLUME_TOLERANCE_PCT,
    tolerance_for_field,
)

__all__ = [
    "DriftDetector",
    "DriftDetectorResult",
    "DriftEvent",
    "QuorumResult",
    "QuorumService",
    "DEFAULT_NUMERIC_TOLERANCE_PCT",
    "DEFAULT_QUORUM_THRESHOLD",
    "EXACT_TOLERANCE",
    "FUNDAMENTALS_TOLERANCE_PCT",
    "PRICE_TOLERANCE_PCT",
    "VOLUME_TOLERANCE_PCT",
    "tolerance_for_field",
]
