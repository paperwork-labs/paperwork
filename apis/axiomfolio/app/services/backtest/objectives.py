"""Pluggable objective functions for walk-forward optimization.

Every objective takes a list of ``TradeResult`` (one per closed trade in
the test window) and returns a ``Decimal`` score. Optuna maximizes the
score, so loss-style metrics (e.g. ulcer index) should be returned as
negative numbers.

All scores are computed in :class:`Decimal` to honor the iron law that
financial statistics must not silently round-trip through ``float`` when
they are persisted. Internal arithmetic that requires ``math.sqrt`` falls
back to ``float`` only for the square root step and is converted back to
``Decimal`` immediately so the persisted column is exact.

medallion: gold
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal, getcontext
from typing import TYPE_CHECKING, Callable, Dict, Sequence

if TYPE_CHECKING:
    from app.services.backtest.walk_forward import TradeResult

logger = logging.getLogger(__name__)

# Generous precision — these are fed straight into Numeric(18,8) columns
# but interim divisions need headroom to avoid quantization surprises.
getcontext().prec = 28

# 252 trading days per year, used to annualize daily-return-like sums.
TRADING_DAYS = Decimal("252")


ObjectiveFn = Callable[[Sequence["TradeResult"]], Decimal]


def _to_decimal(value: float) -> Decimal:
    if math.isnan(value) or math.isinf(value):
        return Decimal("0")
    return Decimal(str(value))


def _trade_returns(trades: Sequence["TradeResult"]) -> list[Decimal]:
    return [t.return_pct for t in trades if t.return_pct is not None]


def _mean(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def _stdev(values: Sequence[Decimal]) -> Decimal:
    """Sample stdev. Returns 0 for n < 2 — caller must treat as undefined
    (i.e. the metric is not computable, not "perfectly stable")."""
    n = len(values)
    if n < 2:
        return Decimal("0")
    mu = _mean(values)
    var = sum((v - mu) * (v - mu) for v in values) / Decimal(n - 1)
    return _to_decimal(math.sqrt(float(var)))


def sharpe_ratio(trades: Sequence["TradeResult"]) -> Decimal:
    """Annualized Sharpe of per-trade returns.

    We use trade-by-trade returns rather than daily returns because the
    walk-forward runner aggregates by trade and the per-day series may
    have flat windows that distort std. Higher = better.
    """
    rets = _trade_returns(trades)
    if len(rets) < 2:
        return Decimal("0")
    mu = _mean(rets)
    sigma = _stdev(rets)
    if sigma == 0:
        return Decimal("0")
    return mu / sigma * _to_decimal(math.sqrt(float(TRADING_DAYS)))


def sortino_ratio(trades: Sequence["TradeResult"]) -> Decimal:
    """Like Sharpe but only penalizes downside volatility."""
    rets = _trade_returns(trades)
    if len(rets) < 2:
        return Decimal("0")
    mu = _mean(rets)
    downside = [r for r in rets if r < 0]
    if not downside:
        return Decimal("0") if mu <= 0 else Decimal("999")  # unbounded upside cap
    downside_var = sum(r * r for r in downside) / Decimal(len(downside))
    downside_std = _to_decimal(math.sqrt(float(downside_var)))
    if downside_std == 0:
        return Decimal("0")
    return mu / downside_std * _to_decimal(math.sqrt(float(TRADING_DAYS)))


def calmar_ratio(trades: Sequence["TradeResult"]) -> Decimal:
    """Total return divided by max equity drawdown across the trade sequence.

    Returns 0 when there were no losing periods (drawdown == 0); the trial
    is then judged purely by other metrics in tie-breaks if Optuna maps
    multiple objectives.
    """
    rets = _trade_returns(trades)
    if not rets:
        return Decimal("0")
    equity = Decimal("1")
    peak = equity
    max_dd = Decimal("0")
    for r in rets:
        equity = equity * (Decimal("1") + r)
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
    total_ret = equity - Decimal("1")
    if max_dd == 0:
        # No drawdown observed — return raw total return (positive or zero).
        return max(total_ret, Decimal("0"))
    return total_ret / max_dd


def expectancy(trades: Sequence["TradeResult"]) -> Decimal:
    """Average return per trade. Direct, easy to interpret."""
    rets = _trade_returns(trades)
    if not rets:
        return Decimal("0")
    return _mean(rets)


def win_rate_x_avg_win(trades: Sequence["TradeResult"]) -> Decimal:
    """Win rate * average winning return. Useful when avoiding drawdowns
    matters more than raw expectancy (penalizes a few big losses that
    expectancy alone might mask)."""
    rets = _trade_returns(trades)
    if not rets:
        return Decimal("0")
    wins = [r for r in rets if r > 0]
    if not wins:
        return Decimal("0")
    win_rate = Decimal(len(wins)) / Decimal(len(rets))
    avg_win = _mean(wins)
    return win_rate * avg_win


OBJECTIVES: Dict[str, ObjectiveFn] = {
    "sharpe_ratio": sharpe_ratio,
    "sortino_ratio": sortino_ratio,
    "calmar_ratio": calmar_ratio,
    "expectancy": expectancy,
    "win_rate_x_avg_win": win_rate_x_avg_win,
}


def get_objective(name: str) -> ObjectiveFn:
    """Look up an objective by name. Raises ``ValueError`` on unknown name
    so a typo'd config fails loudly rather than silently scoring zero."""
    if name not in OBJECTIVES:
        raise ValueError(
            f"Unknown objective '{name}'. "
            f"Available: {sorted(OBJECTIVES.keys())}"
        )
    return OBJECTIVES[name]


def list_objectives() -> list[str]:
    return sorted(OBJECTIVES.keys())
