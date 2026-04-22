"""Peak-signal engine: classify "winner is topping" risk from a pre-computed
``MarketSnapshot``.

The engine reads indicator values already present on ``MarketSnapshot`` and
does NOT recompute indicators. Four orthogonal sub-scores are combined into a
composite severity so the Winner Exit Advisor can reason about whether an
up-trending position is showing late-stage topping behavior:

* ``parabolic_score`` (0..1): how far price is extended above its trend MAs.
* ``climax_volume_score`` (0..1): one-bar volume/price climax into a range top.
* ``distribution_score`` (0..1): Stage 2 -> 3 / 3 -> 4 transitions + weakening RS.
* ``td_exhaustion_flag``: TD Sequential sell-setup exhausted (>= 9 or completed).

The engine is deterministic, pure, and safe to call on every dashboard tick.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, List, Optional

from backend.models.market_data import MarketSnapshot

logger = logging.getLogger(__name__)


# Thresholds. Kept module-level so they are visible, reviewable, and testable.
# These are deliberately conservative; tightening is cheap once we have the
# replay corpus to measure false-positive rate (G15 acceptance work).
PARABOLIC_EXT_PCT_WARN = Decimal("12")       # close more than 12% above SMA150
PARABOLIC_EXT_PCT_DANGER = Decimal("20")     # more than 20% -> full parabolic
PARABOLIC_ATR_DIST_WARN = Decimal("4")       # 4 ATRs above EMA21
PARABOLIC_ATR_DIST_DANGER = Decimal("7")     # 7+ ATRs above EMA21 (blow-off)
PARABOLIC_RANGE_POS_WARN = Decimal("90")     # top decile of 52w range
CLIMAX_VOL_RATIO_WARN = Decimal("1.5")       # 1.5x average
CLIMAX_VOL_RATIO_DANGER = Decimal("2.5")     # 2.5x average
DISTRIBUTION_STAGES = {"3A", "3B", "4A", "4B", "4C"}
WEAK_RS_THRESHOLD = Decimal("0")             # Mansfield < 0 => underperforming SPY
TD_EXHAUSTION_SETUP = 9


@dataclass(frozen=True)
class PeakSignal:
    """Structured peak-risk readout for a single position."""

    symbol: str
    parabolic_score: Decimal
    climax_volume_score: Decimal
    distribution_score: Decimal
    td_exhaustion_flag: bool
    composite_severity: str  # low | med | high
    reasons: List[str] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "symbol": self.symbol,
            "parabolic_score": float(self.parabolic_score),
            "climax_volume_score": float(self.climax_volume_score),
            "distribution_score": float(self.distribution_score),
            "td_exhaustion_flag": self.td_exhaustion_flag,
            "composite_severity": self.composite_severity,
            "reasons": list(self.reasons),
        }


def _d(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (ArithmeticError, TypeError, ValueError):
        return None


def _clip01(x: Decimal) -> Decimal:
    if x < Decimal("0"):
        return Decimal("0")
    if x > Decimal("1"):
        return Decimal("1")
    return x.quantize(Decimal("0.01"))


def _score_parabolic(
    row: MarketSnapshot, reasons: List[str]
) -> Decimal:
    """Sub-score for how stretched price is versus trend-following MAs."""
    ext = _d(row.ext_pct)
    atrx_sma150 = _d(row.atrx_sma_150)
    atr_dist_ema21 = _d(row.atr_dist_ema21)
    range_pos_52w = _d(row.range_pos_52w)

    contributions: List[Decimal] = []

    if ext is not None:
        if ext >= PARABOLIC_EXT_PCT_DANGER:
            contributions.append(Decimal("1.0"))
            reasons.append(
                f"Close {ext}% above SMA150 (>={PARABOLIC_EXT_PCT_DANGER}% "
                "is blow-off territory)"
            )
        elif ext >= PARABOLIC_EXT_PCT_WARN:
            span = PARABOLIC_EXT_PCT_DANGER - PARABOLIC_EXT_PCT_WARN
            frac = (ext - PARABOLIC_EXT_PCT_WARN) / span
            contributions.append(Decimal("0.4") + frac * Decimal("0.5"))
            reasons.append(
                f"Close {ext}% above SMA150 (stretched; >"
                f"{PARABOLIC_EXT_PCT_WARN}% warns)"
            )

    if atr_dist_ema21 is not None:
        if atr_dist_ema21 >= PARABOLIC_ATR_DIST_DANGER:
            contributions.append(Decimal("1.0"))
            reasons.append(
                f"{atr_dist_ema21} ATRs above EMA21 (climax extension)"
            )
        elif atr_dist_ema21 >= PARABOLIC_ATR_DIST_WARN:
            span = PARABOLIC_ATR_DIST_DANGER - PARABOLIC_ATR_DIST_WARN
            frac = (atr_dist_ema21 - PARABOLIC_ATR_DIST_WARN) / span
            contributions.append(Decimal("0.4") + frac * Decimal("0.5"))
            reasons.append(
                f"{atr_dist_ema21} ATRs above EMA21 (extended)"
            )

    if atrx_sma150 is not None and atrx_sma150 >= Decimal("5"):
        contributions.append(Decimal("0.6"))
        reasons.append(
            f"{atrx_sma150} ATRs above SMA150 (long-trend extension)"
        )

    if range_pos_52w is not None and range_pos_52w >= PARABOLIC_RANGE_POS_WARN:
        contributions.append(Decimal("0.4"))
        reasons.append(
            f"Top {Decimal('100') - range_pos_52w}% of 52w range "
            "(approaching highs)"
        )

    if not contributions:
        return Decimal("0")

    # Use the max individual contribution so a single severe signal dominates,
    # but blend in a small average term so multiple mid-level signals still
    # nudge the score up.
    hi = max(contributions)
    avg = sum(contributions) / Decimal(len(contributions))
    return _clip01(hi * Decimal("0.7") + avg * Decimal("0.3"))


def _score_climax_volume(
    row: MarketSnapshot, reasons: List[str]
) -> Decimal:
    """Sub-score for a climactic volume bar near the range highs."""
    vol_ratio = _d(row.vol_ratio)
    perf_1d = _d(row.perf_1d)
    range_pos_52w = _d(row.range_pos_52w)

    if vol_ratio is None:
        return Decimal("0")

    base: Decimal
    if vol_ratio >= CLIMAX_VOL_RATIO_DANGER:
        base = Decimal("0.85")
        reasons.append(f"Volume {vol_ratio}x 20d avg (climactic)")
    elif vol_ratio >= CLIMAX_VOL_RATIO_WARN:
        span = CLIMAX_VOL_RATIO_DANGER - CLIMAX_VOL_RATIO_WARN
        frac = (vol_ratio - CLIMAX_VOL_RATIO_WARN) / span
        base = Decimal("0.35") + frac * Decimal("0.4")
        reasons.append(f"Volume {vol_ratio}x 20d avg (elevated)")
    else:
        return Decimal("0")

    # Only counts as a topping signal if price is also near the top of its
    # range. A climax bar at the bottom of a range is accumulation, not
    # distribution.
    boost = Decimal("0")
    if range_pos_52w is not None and range_pos_52w >= Decimal("85"):
        boost += Decimal("0.10")
        reasons.append(
            "Climax bar printed in top-15% of 52w range"
        )
    if perf_1d is not None and perf_1d >= Decimal("5"):
        boost += Decimal("0.10")
        reasons.append(f"1-day move +{perf_1d}% on climactic volume")
    elif perf_1d is not None and perf_1d <= Decimal("-3"):
        # Outside-reversal / climax-reversal bar.
        boost += Decimal("0.15")
        reasons.append(
            f"1-day move {perf_1d}% on climactic volume (reversal risk)"
        )

    return _clip01(base + boost)


def _score_distribution(
    row: MarketSnapshot, reasons: List[str]
) -> Decimal:
    """Sub-score for stage transitions + weakening relative strength."""
    stage = (row.stage_label or "").strip().upper()
    prev_stage = (row.previous_stage_label or "").strip().upper()
    rs = _d(row.rs_mansfield_pct)
    action_label = (row.action_label or "").strip().upper()

    score = Decimal("0")

    if stage.startswith("4"):
        score = max(score, Decimal("0.95"))
        reasons.append(f"Stage {stage} (decline)")
    elif stage.startswith("3"):
        score = max(score, Decimal("0.55"))
        reasons.append(f"Stage {stage} (topping)")

    if prev_stage and stage and prev_stage != stage:
        if prev_stage.startswith("2") and stage.startswith("3"):
            score = max(score, Decimal("0.75"))
            reasons.append(
                f"Stage transition {prev_stage} -> {stage} (topping)"
            )
        elif prev_stage.startswith("3") and stage.startswith("4"):
            score = max(score, Decimal("0.95"))
            reasons.append(
                f"Stage transition {prev_stage} -> {stage} (breakdown)"
            )

    if rs is not None and rs < WEAK_RS_THRESHOLD and stage in DISTRIBUTION_STAGES:
        score = max(score, score + Decimal("0.15"))
        reasons.append(
            f"Relative strength {rs} (underperforming benchmark during top)"
        )

    if action_label in {"REDUCE", "SHORT", "AVOID"}:
        score = max(score, Decimal("0.6"))
        reasons.append(f"Action label: {action_label}")

    return _clip01(score)


def _td_exhaustion(
    row: MarketSnapshot, reasons: List[str]
) -> bool:
    sell_setup = row.td_sell_setup or 0
    sell_complete = bool(row.td_sell_complete)
    perfect_sell = bool(row.td_perfect_sell)

    if perfect_sell:
        reasons.append("TD Sequential perfect sell (exhaustion)")
        return True
    if sell_complete:
        reasons.append("TD Sequential sell setup completed (exhaustion)")
        return True
    if sell_setup >= TD_EXHAUSTION_SETUP:
        reasons.append(
            f"TD Sequential sell setup {sell_setup}/9 (exhaustion)"
        )
        return True
    if sell_setup >= 7:
        reasons.append(
            f"TD Sequential sell setup {sell_setup}/9 (near exhaustion)"
        )
    return False


def _composite_severity(
    parabolic: Decimal,
    climax: Decimal,
    distribution: Decimal,
    td_flag: bool,
) -> str:
    # weighted: distribution > parabolic > climax; td_flag bumps a tier.
    blended = (
        distribution * Decimal("0.45")
        + parabolic * Decimal("0.35")
        + climax * Decimal("0.20")
    )
    if td_flag:
        blended = min(Decimal("1"), blended + Decimal("0.20"))
    if blended >= Decimal("0.60"):
        return "high"
    if blended >= Decimal("0.30"):
        return "med"
    return "low"


class PeakSignalEngine:
    """Pure function wrapper. Stateless; accepts a snapshot, returns a signal."""

    def evaluate(
        self, symbol: str, snapshot: Optional[MarketSnapshot]
    ) -> PeakSignal:
        sym = (symbol or "").upper().strip()
        if snapshot is None:
            logger.info(
                "peak signal: snapshot unavailable for %s; returning neutral",
                sym,
            )
            return PeakSignal(
                symbol=sym,
                parabolic_score=Decimal("0"),
                climax_volume_score=Decimal("0"),
                distribution_score=Decimal("0"),
                td_exhaustion_flag=False,
                composite_severity="low",
                reasons=["snapshot data not available"],
            )

        reasons: List[str] = []
        parabolic = _score_parabolic(snapshot, reasons)
        climax = _score_climax_volume(snapshot, reasons)
        distribution = _score_distribution(snapshot, reasons)
        td_flag = _td_exhaustion(snapshot, reasons)
        severity = _composite_severity(parabolic, climax, distribution, td_flag)

        return PeakSignal(
            symbol=sym,
            parabolic_score=parabolic,
            climax_volume_score=climax,
            distribution_score=distribution,
            td_exhaustion_flag=td_flag,
            composite_severity=severity,
            reasons=reasons,
        )


__all__ = ["PeakSignal", "PeakSignalEngine"]
