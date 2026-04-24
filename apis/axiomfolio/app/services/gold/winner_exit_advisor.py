"""Winner Exit Advisor.

For an open position showing strength, combine:

* ``PeakSignal`` from :mod:`peak_signal_engine` (is the winner topping?)
* ``TaxAwareExitResult`` from :mod:`tax_aware_exit_calculator` (what does an
  exit cost after tax?)
* stop-distance (how close is the trailing stop to current price?)
* market regime (R1..R5 from ``MarketSnapshot.regime_state`` when available)

and return a structured, advisory-only "should you close?" recommendation.

This service **never** places orders and is not wired into any execution
path. It feeds a UI surface and the daily narrative.

medallion: gold
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.services.gold.peak_signal_engine import PeakSignal
from app.services.gold.tax_aware_exit_calculator import TaxAwareExitResult

# Recommendation taxonomy. Kept small on purpose; the UI summary carries the
# nuance.
ACTION_HOLD = "hold"
ACTION_TRIM = "trim"  # scale a fractional position (20-33%)
ACTION_SCALE = "scale"  # scale a larger slice (50%+)
ACTION_EXIT = "exit"  # full exit advised

VALID_ACTIONS = {ACTION_HOLD, ACTION_TRIM, ACTION_SCALE, ACTION_EXIT}

# Confidence bands. Deliberately conservative: recommendations land as "med"
# unless signals line up across peak risk, stop proximity, and regime.
CONFIDENCE_HIGH = "high"
CONFIDENCE_MED = "med"
CONFIDENCE_LOW = "low"


RISK_OFF_REGIMES = {"R4", "R5"}
RISK_ON_REGIMES = {"R1", "R2"}


TWO_PLACES = Decimal("0.01")


def _q(v: Decimal) -> Decimal:
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class WinnerExitAdvice:
    """Structured recommendation. Advisory only; never auto-executes."""

    symbol: str
    action: str
    suggested_scale_pct: int  # 0..100
    confidence: str  # low | med | high
    summary: str  # plain-English one-liner
    reasons: list[str] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "suggested_scale_pct": self.suggested_scale_pct,
            "confidence": self.confidence,
            "summary": self.summary,
            "reasons": list(self.reasons),
        }


class WinnerExitAdvisor:
    """Pure composer: no DB I/O; caller assembles inputs."""

    def advise(
        self,
        *,
        symbol: str,
        peak: PeakSignal,
        tax: TaxAwareExitResult,
        current_price: Decimal,
        stop_price: Decimal | None = None,
        atr_value: Decimal | None = None,
        regime_state: str | None = None,
    ) -> WinnerExitAdvice:
        sym = (symbol or "").upper().strip()
        reasons: list[str] = []

        # Re-surface the reason stacks so UI consumers see every piece of
        # evidence in one place. We deliberately copy (not reference) so
        # callers cannot mutate the source dataclasses.
        reasons.extend(f"peak: {r}" for r in peak.reasons)

        # Stop proximity: translate "how close is the trailing stop to the
        # price" into ATR multiples where possible, otherwise percent.
        stop_proximity_signal = _stop_proximity_signal(
            current_price=current_price,
            stop_price=stop_price,
            atr_value=atr_value,
            reasons=reasons,
        )

        # Regime shapes both direction and confidence.
        regime = (regime_state or "").strip().upper() or None
        _regime_tier(regime, reasons)

        # Net gain/loss drives whether the tax friction even matters (a
        # losing scale is mostly about the stop and the peak, not the tax).
        is_winner = tax.realized_gain_loss > Decimal("0")

        if is_winner and not tax.tax_advantaged and tax.total_tax > Decimal("0"):
            drag_pct = (
                _q((tax.total_tax / tax.gross_proceeds) * Decimal("100"))
                if tax.gross_proceeds > Decimal("0")
                else Decimal("0")
            )
            reasons.append(
                f"tax: total tax ${_q(tax.total_tax)} on "
                f"${_q(tax.gross_proceeds)} gross ({drag_pct}% drag)"
            )
        elif tax.tax_advantaged:
            reasons.append("tax: account is tax-advantaged; no exit drag")
        else:
            reasons.append("tax: negligible or no realized gain on exit slice")

        # Score the peak side 0..3.
        peak_points = _peak_points(peak)

        # Score the stop side 0..2.
        stop_points = stop_proximity_signal

        # Regime side: risk-off adds 1, risk-on subtracts 1.
        regime_points = 0
        if regime in RISK_OFF_REGIMES:
            regime_points = 1
        elif regime in RISK_ON_REGIMES:
            regime_points = -1

        # Tax friction: a high tax drag on a large ST gain dampens urgency
        # of a partial exit unless peak/stop evidence overwhelms it. A
        # negligible drag (tax-advantaged or long-term-only) slightly raises
        # urgency since there is no cost to waiting.
        tax_friction = _tax_friction_penalty(tax)
        reasons.append(f"tax friction penalty: {tax_friction}")

        total = peak_points + stop_points + regime_points - tax_friction

        action, scale_pct, confidence = _pick_action(total, peak, stop_points)

        summary = _plain_english_summary(
            symbol=sym,
            action=action,
            scale_pct=scale_pct,
            peak=peak,
            tax=tax,
            regime=regime,
            stop_points=stop_points,
            is_winner=is_winner,
        )

        return WinnerExitAdvice(
            symbol=sym,
            action=action,
            suggested_scale_pct=scale_pct,
            confidence=confidence,
            summary=summary,
            reasons=reasons,
        )


def _peak_points(peak: PeakSignal) -> int:
    severity = (peak.composite_severity or "low").lower()
    base = {"low": 0, "med": 1, "high": 2}.get(severity, 0)
    if peak.td_exhaustion_flag:
        base += 1
    return base


def _stop_proximity_signal(
    *,
    current_price: Decimal,
    stop_price: Decimal | None,
    atr_value: Decimal | None,
    reasons: list[str],
) -> int:
    """Return 0..2; 2 = stop is very close (within 1 ATR or 3%)."""
    if stop_price is None or current_price <= Decimal("0"):
        reasons.append("stop: no stop reference available")
        return 0
    if stop_price >= current_price:
        reasons.append(
            f"stop: stop ${stop_price} >= price ${current_price} (invert or already triggered)"
        )
        return 2
    distance = current_price - stop_price
    pct = (distance / current_price) * Decimal("100")
    if atr_value is not None and atr_value > Decimal("0"):
        atr_mult = distance / atr_value
        reasons.append(f"stop: ${stop_price} is {_q(pct)}% / {_q(atr_mult)} ATR below price")
        if atr_mult <= Decimal("1"):
            return 2
        if atr_mult <= Decimal("2"):
            return 1
        return 0
    reasons.append(f"stop: ${stop_price} is {_q(pct)}% below price")
    if pct <= Decimal("3"):
        return 2
    if pct <= Decimal("6"):
        return 1
    return 0


def _regime_tier(regime: str | None, reasons: list[str]) -> str:
    if regime is None:
        reasons.append("regime: not available")
        return "neutral"
    if regime in RISK_OFF_REGIMES:
        reasons.append(f"regime: {regime} (risk-off)")
        return "risk_off"
    if regime in RISK_ON_REGIMES:
        reasons.append(f"regime: {regime} (risk-on)")
        return "risk_on"
    reasons.append(f"regime: {regime} (neutral)")
    return "neutral"


def _tax_friction_penalty(tax: TaxAwareExitResult) -> int:
    if tax.tax_advantaged:
        return 0
    if tax.realized_gain_loss <= Decimal("0"):
        return 0
    if tax.gross_proceeds <= Decimal("0"):
        return 0
    drag_ratio = tax.total_tax / tax.gross_proceeds
    # If waiting converts most of the drag, prefer trim over big scale.
    # Thresholds are intentionally coarse; this nudges, not vetoes.
    if drag_ratio >= Decimal("0.25") and tax.days_to_long_term is not None:
        return 1
    return 0


def _pick_action(total: int, peak: PeakSignal, stop_points: int) -> tuple[str, int, str]:
    """Map aggregate score to (action, scale_pct, confidence)."""
    if total >= 4:
        return ACTION_EXIT, 100, CONFIDENCE_HIGH
    if total == 3:
        return ACTION_SCALE, 50, CONFIDENCE_HIGH
    if total == 2:
        return ACTION_SCALE, 33, CONFIDENCE_MED
    if total == 1:
        return ACTION_TRIM, 25, CONFIDENCE_MED
    if total == 0:
        # If we have ANY peak evidence at all, suggest a small trim.
        if peak.composite_severity == "med" or peak.td_exhaustion_flag:
            return ACTION_TRIM, 20, CONFIDENCE_LOW
        return ACTION_HOLD, 0, CONFIDENCE_MED
    # Negative: signals say hold.
    return ACTION_HOLD, 0, CONFIDENCE_MED if stop_points == 0 else CONFIDENCE_LOW


def _plain_english_summary(
    *,
    symbol: str,
    action: str,
    scale_pct: int,
    peak: PeakSignal,
    tax: TaxAwareExitResult,
    regime: str | None,
    stop_points: int,
    is_winner: bool,
) -> str:
    parts: list[str] = []

    if action == ACTION_HOLD:
        parts.append(f"Hold {symbol} for now.")
    elif action == ACTION_TRIM:
        parts.append(f"Trim ~{scale_pct}% of {symbol} to lock partial gains.")
    elif action == ACTION_SCALE:
        parts.append(f"Scale ~{scale_pct}% of {symbol}.")
    elif action == ACTION_EXIT:
        parts.append(f"Full exit of {symbol} advised.")

    sev = (peak.composite_severity or "low").lower()
    if sev == "high":
        parts.append("Peak-risk readout is high.")
    elif sev == "med":
        parts.append("Peak-risk readout is medium.")
    if peak.td_exhaustion_flag:
        parts.append("TD Sequential sell setup is exhausted.")

    if stop_points >= 2:
        parts.append("Stop is within one ATR / 3% of price.")
    elif stop_points == 1:
        parts.append("Stop is within two ATR / 6% of price.")

    if regime:
        if regime in RISK_OFF_REGIMES:
            parts.append(f"Regime {regime} is risk-off.")
        elif regime in RISK_ON_REGIMES:
            parts.append(f"Regime {regime} is risk-on (tailwind).")
        else:
            parts.append(f"Regime {regime}.")

    if is_winner and not tax.tax_advantaged and tax.total_tax > Decimal("0"):
        parts.append(
            f"Exit tax est. ${_q(tax.total_tax)} (after-tax ${_q(tax.after_tax_proceeds)})."
        )
        if tax.days_to_long_term is not None and tax.breakeven_price_for_long_term_wait is not None:
            parts.append(
                f"Waiting {tax.days_to_long_term} day(s) for long-term "
                f"breaks even above ${_q(tax.breakeven_price_for_long_term_wait)}."
            )
    elif tax.tax_advantaged:
        parts.append("Tax-advantaged account: no exit drag.")

    parts.append("Advisory only -- system will not auto-execute.")
    return " ".join(parts)


__all__ = [
    "ACTION_EXIT",
    "ACTION_HOLD",
    "ACTION_SCALE",
    "ACTION_TRIM",
    "CONFIDENCE_HIGH",
    "CONFIDENCE_LOW",
    "CONFIDENCE_MED",
    "VALID_ACTIONS",
    "WinnerExitAdvice",
    "WinnerExitAdvisor",
]
