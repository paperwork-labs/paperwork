"""Real-time regime monitoring service.

Monitors VIX for intraday spikes and generates regime shift alerts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models.market_data import MarketRegime


class RegimeAlert:
    """Represents a regime alert condition."""

    def __init__(
        self,
        alert_type: str,  # "vix_spike", "regime_shift"
        severity: str,  # "warning", "critical"
        current_value: float,
        threshold: float,
        message: str,
        detected_at: datetime,
    ) -> None:
        self.alert_type = alert_type
        self.severity = severity
        self.current_value = current_value
        self.threshold = threshold
        self.message = message
        self.detected_at = detected_at


class RegimeMonitor:
    """Monitor market regime in real-time."""

    VIX_SPIKE_WARNING = 15.0  # 15% intraday spike triggers warning
    VIX_SPIKE_CRITICAL = 25.0  # 25% spike triggers critical
    VIX_ABSOLUTE_WARNING = 25.0  # VIX above 25 is warning
    VIX_ABSOLUTE_CRITICAL = 35.0  # VIX above 35 is critical

    def __init__(self, db: Session) -> None:
        self.db = db
        self._last_vix: Optional[float] = None
        self._vix_open: Optional[float] = None
        self._alerts_sent: set[str] = set()

    def restore_day_state(self, vix_open: Optional[float], alerts_sent: set[str]) -> None:
        """Restore VIX open and dedupe keys from Redis across Celery runs."""
        self._vix_open = vix_open
        self._alerts_sent = set(alerts_sent)

    def snapshot_day_state(self) -> tuple[Optional[float], set[str]]:
        """State to persist after a run (VIX open + alert dedupe keys)."""
        return self._vix_open, set(self._alerts_sent)

    def check_vix(self, current_vix: float) -> List[RegimeAlert]:
        """Check VIX for alert conditions.

        Returns list of alerts triggered (may be empty).
        """
        alerts: List[RegimeAlert] = []
        now = datetime.now(timezone.utc)

        # Check absolute level
        if current_vix >= self.VIX_ABSOLUTE_CRITICAL:
            alert_key = f"vix_absolute_critical_{now.date()}"
            if alert_key not in self._alerts_sent:
                alerts.append(
                    RegimeAlert(
                        alert_type="vix_absolute",
                        severity="critical",
                        current_value=current_vix,
                        threshold=self.VIX_ABSOLUTE_CRITICAL,
                        message=f"VIX at {current_vix:.1f} - extreme fear level",
                        detected_at=now,
                    )
                )
                self._alerts_sent.add(alert_key)
        elif current_vix >= self.VIX_ABSOLUTE_WARNING:
            alert_key = f"vix_absolute_warning_{now.date()}"
            if alert_key not in self._alerts_sent:
                alerts.append(
                    RegimeAlert(
                        alert_type="vix_absolute",
                        severity="warning",
                        current_value=current_vix,
                        threshold=self.VIX_ABSOLUTE_WARNING,
                        message=f"VIX elevated at {current_vix:.1f}",
                        detected_at=now,
                    )
                )
                self._alerts_sent.add(alert_key)

        # Check intraday spike (if we have open price)
        if self._vix_open and self._vix_open > 0:
            pct_change = (current_vix - self._vix_open) / self._vix_open * 100

            if pct_change >= self.VIX_SPIKE_CRITICAL:
                alert_key = f"vix_spike_critical_{now.date()}"
                if alert_key not in self._alerts_sent:
                    alerts.append(
                        RegimeAlert(
                            alert_type="vix_spike",
                            severity="critical",
                            current_value=pct_change,
                            threshold=self.VIX_SPIKE_CRITICAL,
                            message=f"VIX spiked {pct_change:.1f}% intraday",
                            detected_at=now,
                        )
                    )
                    self._alerts_sent.add(alert_key)
            elif pct_change >= self.VIX_SPIKE_WARNING:
                alert_key = f"vix_spike_warning_{now.date()}"
                if alert_key not in self._alerts_sent:
                    alerts.append(
                        RegimeAlert(
                            alert_type="vix_spike",
                            severity="warning",
                            current_value=pct_change,
                            threshold=self.VIX_SPIKE_WARNING,
                            message=f"VIX up {pct_change:.1f}% today",
                            detected_at=now,
                        )
                    )
                    self._alerts_sent.add(alert_key)

        self._last_vix = current_vix
        return alerts

    def set_vix_open(self, open_price: float) -> None:
        """Set today's VIX open price for spike calculation."""
        self._vix_open = open_price

    def check_regime_shift(self) -> Optional[RegimeAlert]:
        """Check if market regime shifted from previous day."""
        # Get last two regime records
        regimes = (
            self.db.query(MarketRegime)
            .order_by(MarketRegime.as_of_date.desc())
            .limit(2)
            .all()
        )

        if len(regimes) < 2:
            return None

        current, previous = regimes[0], regimes[1]

        if current.regime_state != previous.regime_state:
            now = datetime.now(timezone.utc)
            severity = "warning"

            # Critical if shift is 2+ levels or to R5
            current_num = int(current.regime_state[1]) if current.regime_state else 3
            previous_num = int(previous.regime_state[1]) if previous.regime_state else 3

            if abs(current_num - previous_num) >= 2 or current.regime_state == "R5":
                severity = "critical"

            return RegimeAlert(
                alert_type="regime_shift",
                severity=severity,
                current_value=float(current_num),
                threshold=float(previous_num),
                message=f"Market regime shifted from {previous.regime_state} to {current.regime_state}",
                detected_at=now,
            )

        return None

    def reset_daily(self) -> None:
        """Reset daily tracking (call at market open)."""
        self._vix_open = None
        self._alerts_sent.clear()
