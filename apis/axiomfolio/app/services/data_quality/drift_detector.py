"""
Per-Provider Drift Detector
===========================

Quorum (``quorum_service``) tells us providers disagree with each
other RIGHT NOW. This module asks the orthogonal question: "is one
provider drifting from its OWN history?" That catches a different
failure mode -- a provider quietly switching upstream feeds, swapping
adjusted-for-splits to unadjusted prices, or returning stale cache.

Algorithm: compute the rolling mean and standard deviation of a
provider's recent values for ``(symbol, field)`` over a configurable
window (default 30 days). If the new value is more than ``sigma``
standard deviations from the mean, raise an alert.

Why per-provider, not cross-provider? A single provider's mean cancels
out structural offsets between providers (e.g., FMP vs yfinance
adjustment conventions) and isolates the change-detection signal.

Decimal end to end (R32, R34, R38). We use ``math.sqrt`` only on a
``float`` cast at the very last step, then round-trip back through
``Decimal(str(...))`` so the persisted value is exact.

medallion: silver
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.models.provider_quorum import ProviderDriftAlert

logger = logging.getLogger(__name__)


DEFAULT_HISTORY_WINDOW_DAYS = 30

# 3 sigma is the classic "very unlikely from random noise" threshold.
# At 3 sigma, ~0.27% of in-distribution observations would trigger,
# so for a 30-day window of one-per-day samples we'd expect ~0.08
# false positives per provider per (symbol, field). Acceptable
# given an operator can dismiss with a note.
DEFAULT_SIGMA_THRESHOLD = Decimal("3")

# Below this many samples the std-dev estimate is too noisy to trust;
# we silently NOT alert (returning ``DriftDetectorResult(is_drift=False
# , reason='insufficient_history')``).
MIN_SAMPLES_FOR_ENVELOPE = 5


@dataclass(frozen=True)
class DriftDetectorResult:
    """Outcome of one drift check.

    Always returns a result (never ``None``) so the caller can log
    the "no drift" path too -- silent skips are how regressions go
    unnoticed (R32, R34, R38).

    ``is_drift=True`` means the value warrants writing a row to
    ``provider_drift_alerts``. ``is_drift=False`` rows can be logged
    and discarded.
    """

    symbol: str
    field_name: str
    provider: str
    actual_value: Decimal
    is_drift: bool
    reason: str
    mean: Optional[Decimal] = None
    stddev: Optional[Decimal] = None
    lower_bound: Optional[Decimal] = None
    upper_bound: Optional[Decimal] = None
    deviation_pct: Optional[Decimal] = None
    n_samples: int = 0
    window_days: int = DEFAULT_HISTORY_WINDOW_DAYS

    def expected_range_dict(self) -> dict:
        """JSONB shape persisted to ``ProviderDriftAlert.expected_range``."""
        return {
            "mean": str(self.mean) if self.mean is not None else None,
            "stddev": str(self.stddev) if self.stddev is not None else None,
            "lower": str(self.lower_bound) if self.lower_bound is not None else None,
            "upper": str(self.upper_bound) if self.upper_bound is not None else None,
            "n_samples": int(self.n_samples),
            "window_days": int(self.window_days),
        }


# Backwards-compatible alias requested in the spec ("DriftEvent").
DriftEvent = DriftDetectorResult


class DriftDetector:
    """Stateless drift evaluator. Safe to instantiate per-task."""

    def __init__(
        self,
        history_window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
        sigma_threshold: Decimal = DEFAULT_SIGMA_THRESHOLD,
        min_samples: int = MIN_SAMPLES_FOR_ENVELOPE,
    ):
        if history_window_days <= 0:
            raise ValueError(
                f"history_window_days must be positive, got {history_window_days}"
            )
        if sigma_threshold <= 0:
            raise ValueError(
                f"sigma_threshold must be positive, got {sigma_threshold}"
            )
        if min_samples < 2:
            raise ValueError(
                f"min_samples must be >= 2 (need variance), got {min_samples}"
            )
        self._history_window_days = int(history_window_days)
        self._sigma_threshold = Decimal(sigma_threshold)
        self._min_samples = int(min_samples)

    @property
    def window_days(self) -> int:
        return self._history_window_days

    @property
    def sigma_threshold(self) -> Decimal:
        return self._sigma_threshold

    def cutoff_for_now(self, now: Optional[datetime] = None) -> datetime:
        """UTC cutoff timestamp for "still in the lookback window"."""
        anchor = now or datetime.now(timezone.utc)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        return anchor - timedelta(days=self._history_window_days)

    def compute_envelope(
        self, history: Sequence[Decimal]
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Return ``(mean, stddev)`` from ``history``.

        Uses sample standard deviation (``n - 1`` denominator) so a
        2-sample envelope isn't artificially tight. Returns
        ``(None, None)`` if fewer than 2 samples; ``(mean, Decimal(0))``
        if all samples are identical.
        """
        if len(history) < 2:
            return (None, None)
        total = sum(history, Decimal(0))
        mean = total / Decimal(len(history))
        variance_num = sum(((x - mean) ** 2 for x in history), Decimal(0))
        variance = variance_num / Decimal(len(history) - 1)
        # Decimal has no native sqrt; round-trip through float then
        # back through ``Decimal(str(...))`` to preserve a deterministic
        # representation (no float repr surprises).
        stddev = Decimal(str(math.sqrt(float(variance))))
        return (mean, stddev)

    def check(
        self,
        symbol: str,
        field_name: str,
        provider: str,
        value: Decimal,
        history: Sequence[Decimal],
    ) -> DriftDetectorResult:
        """Decide whether ``value`` drifts from ``history``.

        ``history`` is the provider's own past values for ``(symbol,
        field_name)`` within the configured window, in any order. We
        deliberately don't fetch it ourselves -- the caller (a
        scheduled task or service) controls the DB session and can
        join MarketSnapshotHistory more efficiently than we can.
        """
        if not isinstance(value, Decimal):
            raise TypeError(
                f"DriftDetector.check requires Decimal value, got "
                f"{type(value).__name__}: {value!r}"
            )

        n = len(history)
        if n < self._min_samples:
            return DriftDetectorResult(
                symbol=symbol,
                field_name=field_name,
                provider=provider,
                actual_value=value,
                is_drift=False,
                reason="insufficient_history",
                n_samples=n,
                window_days=self._history_window_days,
            )

        mean, stddev = self.compute_envelope(history)
        if mean is None or stddev is None:
            return DriftDetectorResult(
                symbol=symbol,
                field_name=field_name,
                provider=provider,
                actual_value=value,
                is_drift=False,
                reason="insufficient_history",
                n_samples=n,
                window_days=self._history_window_days,
            )

        if stddev == 0:
            # Degenerate history (e.g., a flat-line cache). Any change
            # at all is "drift" by definition -- otherwise we'd
            # rubber-stamp a stuck provider.
            is_drift = value != mean
            deviation_pct = (
                ((value - mean) / mean).copy_abs() if mean != 0 else Decimal(0)
            )
            signed_deviation_pct = (
                ((value - mean) / mean) if mean != 0 else Decimal(0)
            )
            return DriftDetectorResult(
                symbol=symbol,
                field_name=field_name,
                provider=provider,
                actual_value=value,
                is_drift=is_drift,
                reason="zero_sigma_history" if is_drift else "matches_flat_history",
                mean=mean,
                stddev=stddev,
                lower_bound=mean,
                upper_bound=mean,
                deviation_pct=signed_deviation_pct if is_drift else deviation_pct,
                n_samples=n,
                window_days=self._history_window_days,
            )

        band = self._sigma_threshold * stddev
        lower = mean - band
        upper = mean + band

        # Signed: positive = above the band, negative = below. Stored
        # as ``actual_value / mean - 1`` which is the operator-friendly
        # form (e.g., +0.078 = "7.8% above the mean").
        if mean != 0:
            signed_dev_pct = (value - mean) / mean
        else:
            signed_dev_pct = Decimal(0)

        is_drift = value < lower or value > upper

        return DriftDetectorResult(
            symbol=symbol,
            field_name=field_name,
            provider=provider,
            actual_value=value,
            is_drift=is_drift,
            reason="outside_sigma_band" if is_drift else "within_sigma_band",
            mean=mean,
            stddev=stddev,
            lower_bound=lower,
            upper_bound=upper,
            deviation_pct=signed_dev_pct,
            n_samples=n,
            window_days=self._history_window_days,
        )

    def persist(
        self,
        db: Session,
        result: DriftDetectorResult,
        alert_at: Optional[datetime] = None,
    ) -> Optional[ProviderDriftAlert]:
        """Write a drift alert if ``result.is_drift``.

        Returns ``None`` when ``is_drift`` is False (so callers can do
        ``if detector.persist(db, r): bump_counter()``). Caller
        controls the transaction.
        """
        if not result.is_drift:
            return None

        if result.deviation_pct is None:
            # Defensive: ``check`` always sets deviation_pct when
            # is_drift=True. If we hit this, the contract has drifted.
            logger.error(
                "drift result is_drift=True but deviation_pct is None for %s/%s/%s",
                result.symbol,
                result.field_name,
                result.provider,
            )
            return None

        row = ProviderDriftAlert(
            symbol=result.symbol,
            field_name=result.field_name,
            provider=result.provider,
            expected_range=result.expected_range_dict(),
            actual_value=result.actual_value,
            deviation_pct=result.deviation_pct,
        )
        if alert_at is not None:
            row.alert_at = alert_at
        db.add(row)
        db.flush()
        logger.warning(
            "drift alert created id=%s symbol=%s field=%s provider=%s deviation=%s",
            row.id,
            row.symbol,
            row.field_name,
            row.provider,
            row.deviation_pct,
        )
        return row
