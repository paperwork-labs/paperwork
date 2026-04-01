"""Exit Cascade Engine (v4 Section 8)

9-tier independently-firing exit system for long positions:
  Tiers 1–5: Base exits (always active)
  Tiers 6–9: Regime-conditional exits (fire when regime worsens)

4-tier short exit system:
  S1–S4: Cover signals for short positions

Each tier fires independently; most aggressive (closest to exit) wins.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from backend.services.market.regime_engine import (
    REGIME_R1,
    REGIME_R2,
    REGIME_R3,
    REGIME_R4,
    REGIME_R5,
)

logger = logging.getLogger(__name__)


class ExitAction(str, Enum):
    HOLD = "HOLD"
    REDUCE_25 = "REDUCE_25"
    REDUCE_50 = "REDUCE_50"
    EXIT = "EXIT"


@dataclass
class ExitSignal:
    """A single exit tier's recommendation."""
    tier: str
    action: ExitAction
    reason: str
    urgency: int  # 1 (lowest) to 10 (most urgent)


@dataclass
class PositionContext:
    """Snapshot of a position's current state for exit evaluation."""
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    current_price: float
    atr_14: float
    atrp_14: float
    stage_label: str
    previous_stage_label: Optional[str]
    current_stage_days: int
    ext_pct: float
    sma150_slope: float
    ema10_dist_n: float
    rs_mansfield: float
    regime_state: str
    previous_regime_state: Optional[str]
    days_held: int
    pnl_pct: float  # unrealized P&L %
    # Peak trade price since entry (longs: highest close/high). None = use entry_price fallback in T2/T7.
    high_water_price: Optional[float] = None


@dataclass
class CascadeResult:
    """Full cascade evaluation output."""
    symbol: str
    signals: list[ExitSignal] = field(default_factory=list)
    final_action: ExitAction = ExitAction.HOLD
    final_reason: str = ""
    final_tier: str = ""

    def add(self, signal: ExitSignal) -> None:
        self.signals.append(signal)
        if signal.urgency > self._max_urgency():
            self.final_action = signal.action
            self.final_reason = signal.reason
            self.final_tier = signal.tier

    def _max_urgency(self) -> int:
        if not self.signals:
            return 0
        return max(s.urgency for s in self.signals if s.action != ExitAction.HOLD)


# ── Long Exit Tiers 1–5 (Base) ──

def _tier1_stop_loss(ctx: PositionContext) -> ExitSignal:
    """T1: Hard stop loss — 2× ATR below entry."""
    stop = ctx.entry_price - (2.0 * ctx.atr_14)
    if ctx.current_price <= stop:
        return ExitSignal("T1", ExitAction.EXIT, f"Stop loss hit (price {ctx.current_price:.2f} <= stop {stop:.2f})", 10)
    return ExitSignal("T1", ExitAction.HOLD, "Above stop", 0)


def _tier2_trailing_stop(ctx: PositionContext) -> ExitSignal:
    """T2: Adaptive trailing stop based on stage, regime, and volatility.

    Base multipliers by stage:
      2A/2B: 1.5× ATR
      2C: 2.0× ATR (wider for extended moves)
      3A+: 1.0× ATR (tighter as momentum fades)

    Regime adjustment:
      R1/R2: no change (favorable)
      R3: -0.25× (slightly tighter)
      R4/R5: -0.5× (much tighter, protect gains)

    Volatility adjustment (atrp_14):
      Low vol (<2%): -0.25× (tighter, less room needed)
      High vol (>4%): +0.25× (wider, avoid whipsaws)
    """
    # Base multiplier by stage
    base_mult = 1.5
    if ctx.stage_label == "2C":
        base_mult = 2.0
    elif ctx.stage_label.startswith("3"):
        base_mult = 1.0

    # Regime adjustment
    regime_adj = 0.0
    if ctx.regime_state == REGIME_R3:
        regime_adj = -0.25
    elif ctx.regime_state in (REGIME_R4, REGIME_R5):
        regime_adj = -0.5

    # Volatility adjustment
    vol_adj = 0.0
    if ctx.atrp_14 < 2.0:
        vol_adj = -0.25
    elif ctx.atrp_14 > 4.0:
        vol_adj = 0.25

    # Final multiplier (minimum 0.5 to avoid unreasonably tight stops)
    multiplier = max(0.5, base_mult + regime_adj + vol_adj)

    trail_distance = multiplier * ctx.atr_14
    if ctx.pnl_pct <= 0:
        return ExitSignal("T2", ExitAction.HOLD, "Trail not hit", 0)
    # Trail from high water mark, not a tautology on current_price.
    # TODO: Populate high_water_price from position peak tracking; entry-only fallback ignores give-back from higher peaks.
    hwm = ctx.high_water_price if ctx.high_water_price is not None else ctx.entry_price
    if ctx.current_price < (hwm - trail_distance):
        return ExitSignal(
            "T2", ExitAction.EXIT,
            f"Trailing stop ({multiplier:.2f}× ATR, stage={ctx.stage_label}, regime={ctx.regime_state}, hwm={hwm:.2f})",
            9
        )
    return ExitSignal("T2", ExitAction.HOLD, "Trail not hit", 0)


def _tier3_stage_deterioration(ctx: PositionContext) -> ExitSignal:
    """T3: Stage downgrade exit.

    2B→3A: reduce 50%
    2C→3A: reduce 50%
    Any→4x: full exit
    """
    prev = ctx.previous_stage_label or ""
    curr = ctx.stage_label

    if curr.startswith("4"):
        return ExitSignal("T3", ExitAction.EXIT, f"Stage dropped to {curr} (decline phase)", 9)
    if prev in ("2B", "2C") and curr == "3A":
        return ExitSignal("T3", ExitAction.REDUCE_50, f"Stage deteriorated {prev}→{curr}", 7)
    if curr == "3B":
        return ExitSignal("T3", ExitAction.EXIT, f"Stage reached {curr} (late distribution)", 8)
    return ExitSignal("T3", ExitAction.HOLD, "Stage stable", 0)


def _tier4_time_based(ctx: PositionContext) -> ExitSignal:
    """T4: Time-based exit for positions that aren't working.

    45+ days in same stage with < 5% gain → reduce
    90+ days with < 0% → exit
    """
    if ctx.days_held >= 90 and ctx.pnl_pct < 0:
        return ExitSignal("T4", ExitAction.EXIT, f"90+ days held, P&L {ctx.pnl_pct:.1f}%", 6)
    if ctx.days_held >= 45 and ctx.pnl_pct < 5:
        return ExitSignal("T4", ExitAction.REDUCE_25, f"45+ days held, P&L {ctx.pnl_pct:.1f}%", 4)
    return ExitSignal("T4", ExitAction.HOLD, "Time ok", 0)


def _tier5_profit_target(ctx: PositionContext) -> ExitSignal:
    """T5: Profit target — take partial at extension.

    ext_pct > 25%: reduce 25%
    ext_pct > 40%: reduce 50%
    """
    if ctx.ext_pct > 40:
        return ExitSignal("T5", ExitAction.REDUCE_50, f"Extended {ctx.ext_pct:.1f}% from SMA150", 6)
    if ctx.ext_pct > 25:
        return ExitSignal("T5", ExitAction.REDUCE_25, f"Extended {ctx.ext_pct:.1f}% from SMA150", 4)
    return ExitSignal("T5", ExitAction.HOLD, "Not extended", 0)


# ── Long Exit Tiers 6–9 (Regime-Conditional) ──

def _tier6_regime_transition(ctx: PositionContext) -> Optional[ExitSignal]:
    """T6: Regime worsening exits.

    R1/R2 → R4/R5: exit all longs
    R1/R2 → R3: reduce 25%
    """
    if ctx.previous_regime_state is None:
        logger.warning(
            "T6 regime transition skipped for %s: previous_regime_state is unknown",
            ctx.symbol,
        )
        return None
    prev = ctx.previous_regime_state
    curr = ctx.regime_state

    if prev in (REGIME_R1, REGIME_R2) and curr in (REGIME_R4, REGIME_R5):
        return ExitSignal("T6", ExitAction.EXIT, f"Regime crashed {prev}→{curr}", 10)
    if prev in (REGIME_R1, REGIME_R2) and curr == REGIME_R3:
        return ExitSignal("T6", ExitAction.REDUCE_25, f"Regime weakened {prev}→{curr}", 5)
    return ExitSignal("T6", ExitAction.HOLD, "Regime stable", 0)


def _tier7_regime_trail(ctx: PositionContext) -> ExitSignal:
    """T7: Tighter trailing stops in worse regimes.

    R3: 1.0× ATR trail
    R4: 0.75× ATR trail
    R5: exit everything
    """
    if ctx.regime_state == REGIME_R5:
        return ExitSignal("T7", ExitAction.EXIT, "R5 — exit all longs", 10)

    multiplier = None
    if ctx.regime_state == REGIME_R4:
        multiplier = 0.75
    elif ctx.regime_state == REGIME_R3:
        multiplier = 1.0

    if multiplier is not None and ctx.pnl_pct > 0:
        trail = multiplier * ctx.atr_14
        # Same high-water trailing pattern as T2 (not entry+pnl expressed as a function of current only).
        hwm = ctx.high_water_price if ctx.high_water_price is not None else ctx.entry_price
        if ctx.current_price < (hwm - trail):
            return ExitSignal(
                "T7",
                ExitAction.EXIT,
                f"Regime trail hit ({multiplier}× ATR in {ctx.regime_state}, hwm={hwm:.2f})",
                8,
            )
    return ExitSignal("T7", ExitAction.HOLD, "Regime trail ok", 0)


def _tier8_regime_profit_taking(ctx: PositionContext) -> ExitSignal:
    """T8: Accelerated profit-taking in deteriorating regimes.

    R3 + ext_pct > 15: reduce 25%
    R4 + ext_pct > 10: reduce 50%
    """
    if ctx.regime_state == REGIME_R4 and ctx.ext_pct > 10:
        return ExitSignal("T8", ExitAction.REDUCE_50, f"R4 + extended {ctx.ext_pct:.1f}%", 7)
    if ctx.regime_state == REGIME_R3 and ctx.ext_pct > 15:
        return ExitSignal("T8", ExitAction.REDUCE_25, f"R3 + extended {ctx.ext_pct:.1f}%", 5)
    return ExitSignal("T8", ExitAction.HOLD, "Not regime-extended", 0)


def _tier9_r5_full_exit(ctx: PositionContext) -> ExitSignal:
    """T9: R5 forces full exit of all longs regardless of stage/profit."""
    if ctx.regime_state == REGIME_R5:
        return ExitSignal("T9", ExitAction.EXIT, "R5 bear regime — mandatory long exit", 10)
    return ExitSignal("T9", ExitAction.HOLD, "Not R5", 0)


# ── Short Exit Tiers S1–S4 ──

def _short_s1_stage_improvement(ctx: PositionContext) -> ExitSignal:
    """S1: Stage improvement cover — cover shorts when stage improves."""
    if ctx.stage_label in ("1A", "1B", "2A", "2B"):
        return ExitSignal("S1", ExitAction.EXIT, f"Stage improved to {ctx.stage_label} — cover short", 9)
    return ExitSignal("S1", ExitAction.HOLD, "Stage still bearish", 0)


def _short_s2_regime_improvement(ctx: PositionContext) -> ExitSignal:
    """S2: Regime improvement cover — cover when regime improves to R1/R2."""
    if ctx.regime_state in (REGIME_R1, REGIME_R2):
        return ExitSignal("S2", ExitAction.EXIT, f"Regime improved to {ctx.regime_state} — cover short", 9)
    return ExitSignal("S2", ExitAction.HOLD, "Regime still bearish", 0)


def _short_s3_vol_spike(ctx: PositionContext) -> ExitSignal:
    """S3: Volatility spike cover — extreme downside often reverses."""
    if ctx.ext_pct < -25:
        return ExitSignal("S3", ExitAction.REDUCE_50, f"Extreme extension {ctx.ext_pct:.1f}% — partial cover", 6)
    return ExitSignal("S3", ExitAction.HOLD, "Extension normal", 0)


def _short_s4_target(ctx: PositionContext) -> ExitSignal:
    """S4: Profit target for shorts — cover at predefined gain."""
    if ctx.pnl_pct > 35:
        return ExitSignal("S4", ExitAction.EXIT, f"Short P&L {ctx.pnl_pct:.1f}% — full cover", 7)
    if ctx.pnl_pct > 20:
        return ExitSignal("S4", ExitAction.REDUCE_50, f"Short P&L {ctx.pnl_pct:.1f}% — take partial", 5)
    return ExitSignal("S4", ExitAction.HOLD, "Target not reached", 0)


# ── Cascade evaluation ──

ExitTierFn = Callable[[PositionContext], Optional[ExitSignal]]

LONG_TIERS: list[ExitTierFn] = [
    _tier1_stop_loss,
    _tier2_trailing_stop,
    _tier3_stage_deterioration,
    _tier4_time_based,
    _tier5_profit_target,
    _tier6_regime_transition,
    _tier7_regime_trail,
    _tier8_regime_profit_taking,
    _tier9_r5_full_exit,
]

SHORT_TIERS: list[ExitTierFn] = [
    _short_s1_stage_improvement,
    _short_s2_regime_improvement,
    _short_s3_vol_spike,
    _short_s4_target,
]


def evaluate_exit_cascade(ctx: PositionContext) -> CascadeResult:
    """Evaluate all applicable exit tiers for a position.

    Each tier fires independently. Most aggressive (highest urgency) wins.
    """
    result = CascadeResult(symbol=ctx.symbol)

    tiers = LONG_TIERS if ctx.side == "LONG" else SHORT_TIERS
    for tier_fn in tiers:
        signal = tier_fn(ctx)
        if signal is None:
            continue
        if signal.action != ExitAction.HOLD:
            result.add(signal)

    if not result.signals or all(s.action == ExitAction.HOLD for s in result.signals):
        result.final_action = ExitAction.HOLD
        result.final_reason = "All tiers clear"
        result.final_tier = ""

    logger.debug(
        "Exit cascade for %s (%s): %s via %s — %d tiers fired",
        ctx.symbol,
        ctx.side,
        result.final_action.value,
        result.final_tier,
        len([s for s in result.signals if s.action != ExitAction.HOLD]),
    )
    return result
