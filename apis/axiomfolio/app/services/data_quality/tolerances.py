"""
Per-Field Tolerance Configuration
=================================

Pure data module -- no logic, just the answer to "how close do two
provider values have to be before we say they agree?".

We separate this from ``QuorumService`` so that:

* changing a tolerance is a one-line, easily-reviewed edit;
* tests can import the same constants the service uses (no drift);
* ops can read the file to understand "why was X flagged?".

Tolerances are fractional (e.g., 0.005 = 0.5%). For exact-match fields
(symbol, name, sector) we use ``Decimal("0")`` -- any difference is a
disagreement.

If you need to add a new field, add it here AND add a corresponding
test in ``backend/tests/data_quality/test_quorum_service.py``.

medallion: silver
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict


# Quorum threshold = "fraction of responding providers that must
# agree". 2 of 3 = 2/3 exactly (not 0.667, which is slightly above 2/3
# and breaks ``ratio >= threshold`` for two agreeing providers).
# Used as the default by ``QuorumService``; callers can override
# per-call (e.g., for low-stakes fields).
DEFAULT_QUORUM_THRESHOLD = Decimal("2") / Decimal("3")


# Sentinel for "must match exactly" (symbols, names, sectors).
EXACT_TOLERANCE = Decimal("0")


# Live last-trade price. Bid/ask spreads + clock skew between providers
# can produce sub-percent differences even when both are correct.
PRICE_TOLERANCE_PCT = Decimal("0.005")  # 0.5%

# Daily close: providers reconcile to the same official print, so
# tolerance is much tighter than live prices.
CLOSE_PRICE_TOLERANCE_PCT = Decimal("0.001")  # 0.1%

# Daily/cumulative volume. Wider than price because dark-pool prints
# trickle in over the consolidated tape and providers report at
# different cadences.
VOLUME_TOLERANCE_PCT = Decimal("0.02")  # 2%

# Fundamentals (EPS, revenue, market cap). Providers source from
# different filings and may apply different adjustments.
FUNDAMENTALS_TOLERANCE_PCT = Decimal("0.01")  # 1%


# Per-field map. Lookup-only: ``tolerance_for_field`` is the public
# entry point so callers don't reach into the dict and miss a default.
_FIELD_TOLERANCES: Dict[str, Decimal] = {
    # Live / intraday price-like fields.
    "LAST_PRICE": PRICE_TOLERANCE_PCT,
    "OPEN_PRICE": PRICE_TOLERANCE_PCT,
    "HIGH_PRICE": PRICE_TOLERANCE_PCT,
    "LOW_PRICE": PRICE_TOLERANCE_PCT,
    # Daily close uses the tighter band -- this is what powers
    # MarketSnapshotHistory and indicator computation.
    "CLOSE_PRICE": CLOSE_PRICE_TOLERANCE_PCT,
    # Volume.
    "VOLUME": VOLUME_TOLERANCE_PCT,
    # Fundamentals.
    "MARKET_CAP": PRICE_TOLERANCE_PCT,
    "EPS": FUNDAMENTALS_TOLERANCE_PCT,
    "REVENUE": FUNDAMENTALS_TOLERANCE_PCT,
    "PE_RATIO": FUNDAMENTALS_TOLERANCE_PCT,
    # Exact-match string-ish fields. (Stored as numeric placeholders
    # in the quorum service via hashing -- see test for
    # ``_validate_exact``.)
    "TICKER": EXACT_TOLERANCE,
    "NAME": EXACT_TOLERANCE,
    "SECTOR": EXACT_TOLERANCE,
    "INDUSTRY": EXACT_TOLERANCE,
}


# Fallback for fields we haven't catalogued yet. Conservative: use the
# fundamentals (1%) tolerance. We log on use (see QuorumService).
DEFAULT_NUMERIC_TOLERANCE_PCT = FUNDAMENTALS_TOLERANCE_PCT


def tolerance_for_field(field_name: str) -> Decimal:
    """Return the configured tolerance for ``field_name``.

    Falls back to ``DEFAULT_NUMERIC_TOLERANCE_PCT`` for unknown
    fields. Callers that need to distinguish "configured" from
    "fallback" should look up ``_FIELD_TOLERANCES`` directly -- but
    most production code paths just want a number.
    """
    return _FIELD_TOLERANCES.get(field_name, DEFAULT_NUMERIC_TOLERANCE_PCT)
