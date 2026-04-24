"""Tests for ``DriftDetector``.

Synthetic-history tests for per-provider drift detection. We build a
30-day Gaussian sample for a known mean / sigma, inject an outlier,
and assert the detector flags it (and only it).

Iron-law guards:

* float values are rejected loudly,
* insufficient history returns ``is_drift=False`` rather than guessing,
* zero-sigma history (a stuck-cache provider) flags ANY change.
"""

from __future__ import annotations

import random
from decimal import Decimal
from typing import List

import pytest

from backend.services.data_quality import DriftDetector


@pytest.fixture
def detector() -> DriftDetector:
    return DriftDetector()


def _synthetic_history(
    mean: float, sigma: float, n: int = 30, seed: int = 1234
) -> List[Decimal]:
    """Reproducible Gaussian-ish sample as Decimals.

    Uses ``random.Random`` rather than NumPy to keep tests dependency-
    light. Decimal preservation: each sample is rounded to 4 decimal
    places so the sample's empirical sigma is close to the analytical
    sigma.
    """
    rng = random.Random(seed)
    return [
        Decimal(f"{rng.gauss(mean, sigma):.4f}")
        for _ in range(n)
    ]


# ---------------------------------------------------------------------------
# In-band / outlier flagging
# ---------------------------------------------------------------------------


def test_in_band_value_is_not_flagged(detector: DriftDetector) -> None:
    history = _synthetic_history(mean=100.0, sigma=1.0, n=30)
    # Within ~1 sigma of the mean -- well inside the 3-sigma band.
    result = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=Decimal("100.5"),
        history=history,
    )
    assert result.is_drift is False
    assert result.reason == "within_sigma_band"
    assert result.mean is not None and result.stddev is not None
    assert result.lower_bound is not None and result.upper_bound is not None


def test_five_sigma_outlier_is_flagged(detector: DriftDetector) -> None:
    history = _synthetic_history(mean=100.0, sigma=1.0, n=30)
    result = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=Decimal("106"),  # ~6 sigma above mean
        history=history,
    )
    assert result.is_drift is True
    assert result.reason == "outside_sigma_band"
    assert result.deviation_pct is not None
    assert result.deviation_pct > 0  # signed: positive = above band


def test_negative_outlier_is_flagged(detector: DriftDetector) -> None:
    history = _synthetic_history(mean=100.0, sigma=1.0, n=30)
    result = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=Decimal("90"),  # ~10 sigma below mean
        history=history,
    )
    assert result.is_drift is True
    assert result.deviation_pct < 0


# ---------------------------------------------------------------------------
# Insufficient history
# ---------------------------------------------------------------------------


def test_insufficient_history_does_not_flag(detector: DriftDetector) -> None:
    # Default min_samples = 5. Pass 3 historical points.
    history = [Decimal("100"), Decimal("100.5"), Decimal("101")]
    result = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=Decimal("500"),  # would obviously drift if we had history
        history=history,
    )
    assert result.is_drift is False
    assert result.reason == "insufficient_history"
    # We don't compute mean/stddev with too-few samples.
    assert result.mean is None
    assert result.stddev is None


# ---------------------------------------------------------------------------
# Zero-sigma history (stuck cache)
# ---------------------------------------------------------------------------


def test_zero_sigma_history_treats_any_change_as_drift(
    detector: DriftDetector,
) -> None:
    # Provider has been returning the exact same number for 10 days
    # (e.g., a stale cache). A different value, however small, should
    # flag.
    history = [Decimal("100.00")] * 10
    drift_result = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=Decimal("100.01"),
        history=history,
    )
    assert drift_result.is_drift is True
    assert drift_result.reason == "zero_sigma_history"

    # Same value as the flat history -> not drift.
    same_result = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=Decimal("100.00"),
        history=history,
    )
    assert same_result.is_drift is False
    assert same_result.reason == "matches_flat_history"


# ---------------------------------------------------------------------------
# Threshold + envelope math
# ---------------------------------------------------------------------------


def test_three_sigma_threshold_boundary(detector: DriftDetector) -> None:
    """A value just outside 3 sigma flags; just inside does not."""
    history = _synthetic_history(mean=100.0, sigma=1.0, n=200, seed=42)
    mean, stddev = detector.compute_envelope(history)
    assert mean is not None and stddev is not None

    # Construct a value 4 sigma above the empirical mean -- safely
    # outside even with sample-mean noise.
    above = mean + (stddev * Decimal(4))
    drift = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=above,
        history=history,
    )
    assert drift.is_drift is True

    # And a value 1 sigma above -- safely inside.
    inside = mean + stddev
    no_drift = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=inside,
        history=history,
    )
    assert no_drift.is_drift is False


def test_compute_envelope_matches_manual_calculation() -> None:
    detector = DriftDetector(min_samples=2)
    # Hand-pickable: mean = 4, sample-stddev = sqrt(((-3)^2 + (-1)^2 +
    # 1^2 + 3^2) / 3) = sqrt(20/3) ~= 2.5820
    mean, stddev = detector.compute_envelope(
        [Decimal("1"), Decimal("3"), Decimal("5"), Decimal("7")]
    )
    assert mean == Decimal("4")
    assert abs(stddev - Decimal("2.5820")) < Decimal("0.001")


# ---------------------------------------------------------------------------
# Constructor + input hygiene
# ---------------------------------------------------------------------------


def test_constructor_validates_inputs() -> None:
    with pytest.raises(ValueError):
        DriftDetector(history_window_days=0)
    with pytest.raises(ValueError):
        DriftDetector(sigma_threshold=Decimal("0"))
    with pytest.raises(ValueError):
        DriftDetector(min_samples=1)


def test_check_rejects_float_value(detector: DriftDetector) -> None:
    history = _synthetic_history(mean=100.0, sigma=1.0)
    with pytest.raises(TypeError, match="Decimal"):
        detector.check(
            symbol="AAPL",
            field_name="LAST_PRICE",
            provider="fmp",
            value=100.0,  # float -- forbidden
            history=history,
        )


def test_window_days_helper_returns_cutoff_in_past(detector: DriftDetector) -> None:
    cutoff = detector.cutoff_for_now()
    from datetime import datetime, timezone

    delta = datetime.now(timezone.utc) - cutoff
    assert detector.window_days >= 1
    # Cutoff should be within ~1 second of (now - window_days).
    assert abs(delta.days - detector.window_days) <= 1


def test_expected_range_dict_round_trips_decimals(detector: DriftDetector) -> None:
    history = _synthetic_history(mean=100.0, sigma=1.0, n=30)
    result = detector.check(
        symbol="AAPL",
        field_name="LAST_PRICE",
        provider="fmp",
        value=Decimal("110"),
        history=history,
    )
    payload = result.expected_range_dict()
    assert payload["mean"] is not None
    assert payload["stddev"] is not None
    assert payload["lower"] is not None
    assert payload["upper"] is not None
    assert payload["n_samples"] == 30
    assert payload["window_days"] == detector.window_days
