"""
Monte Carlo Simulator
=====================

Bootstrap-resamples a list of historical *trade returns* to produce
confidence intervals on the equity curve, max drawdown, Sharpe ratio,
terminal value, probability of loss, and probability of doubling.

Why this exists
---------------

A single backtest result is one realization of an underlying return
distribution. Monte Carlo resampling answers: "what would the equity
curve have looked like if the trades had occurred in a different
order, or if a slightly different sample of trades had been taken?"
That gives the user a calibrated sense of how much luck is hidden in
the headline Sharpe.

Design choices
--------------

* **Inputs are ``Decimal``** for monetary values per the iron law in
  ``AGENTS.md``. We accept trade-level returns as ``Decimal`` (e.g.
  ``Decimal("0.025")`` for a +2.5% trade) and convert to ``float64``
  internally because numpy bootstrap on N=10,000 simulations × 200
  trades needs to be fast (target sub-2s).
* **Aggregates back to ``Decimal``**. The simulation uses ``float64``
  internally for performance (bootstrap matrix, ``np.percentile``).
  Quantiles and monetary summaries are quantized to 8 decimal places
  and returned as ``Decimal`` at the API boundary so money never
  round-trips as bare IEEE floats in JSON.
* **Reproducible** when ``seed`` is set; same seed + inputs => identical
  output. This is required by the acceptance criteria.
* **Read-only**: never touches the DB. The caller is responsible for
  loading trade returns from a study or supplying them inline.

Public API
----------

``MonteCarloSimulator.run(trade_returns, n_simulations, initial_capital, seed) -> MonteCarloResult``

See ``app/api/routes/backtest/monte_carlo.py`` for the HTTP wrapper
and ``app/services/backtest/scenarios.py`` for preset weighted
resamplers (optimistic/pessimistic skew).

medallion: gold
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


TRADING_DAYS_PER_YEAR = 252

# Maximum bootstrap iterations per synchronous call (aligned with the
# FastAPI route's ``le=`` cap). Prevents accidental DoS via huge ``n``.
MAX_ITERATIONS = 100_000

# Minimum historical trades before we accept a bootstrap sample. Below
# this, percentile bands are not statistically meaningful for research UX.
MIN_SAMPLES = 30

_DECIMAL_QUANTUM = Decimal("0.00000001")

_FAN_PERCENTILES: tuple[int, ...] = (5, 25, 50, 75, 95)


@dataclass(frozen=True)
class EquityCurvePercentiles:
    """Per-step percentiles of the simulated equity curves.

    Each list has ``n_trades`` elements, where index ``i`` is the
    distribution of equity values *after* trade ``i`` has been applied
    across all simulations. Index ``0`` is the equity after the first
    bootstrap-sampled trade; index ``n_trades-1`` is the terminal value.
    """

    p5: list[Decimal]
    p25: list[Decimal]
    p50: list[Decimal]
    p75: list[Decimal]
    p95: list[Decimal]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "p5": [str(v) for v in self.p5],
            "p25": [str(v) for v in self.p25],
            "p50": [str(v) for v in self.p50],
            "p75": [str(v) for v in self.p75],
            "p95": [str(v) for v in self.p95],
        }


@dataclass(frozen=True)
class DistributionStats:
    """Summary of a one-dimensional distribution across simulations.

    Used for max-drawdown, Sharpe, and terminal value distributions.
    All percentiles use linear interpolation (numpy default) which is
    appropriate for the smooth distributions Monte Carlo produces.
    """

    mean: Decimal
    median: Decimal
    p5: Decimal
    p25: Decimal
    p75: Decimal
    p95: Decimal
    std: Decimal

    def to_dict(self) -> dict[str, str]:
        return {
            "mean": str(self.mean),
            "median": str(self.median),
            "p5": str(self.p5),
            "p25": str(self.p25),
            "p75": str(self.p75),
            "p95": str(self.p95),
            "std": str(self.std),
        }


@dataclass(frozen=True)
class MonteCarloResult:
    """Container returned by ``MonteCarloSimulator.run``.

    The ``params`` block echoes the key inputs back so a UI can render
    "you ran 10,000 sims on 142 trades starting at $100,000" without
    having to keep the request payload around.
    """

    equity_curve: EquityCurvePercentiles
    max_drawdown_pct: DistributionStats
    sharpe: DistributionStats
    terminal_value: DistributionStats
    probability_of_loss: Decimal
    probability_of_2x: Decimal
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "equity_curve": self.equity_curve.to_dict(),
            "max_drawdown_pct": self.max_drawdown_pct.to_dict(),
            "sharpe": self.sharpe.to_dict(),
            "terminal_value": self.terminal_value.to_dict(),
            "probability_of_loss": str(self.probability_of_loss),
            "probability_of_2x": str(self.probability_of_2x),
            "params": self.params,
        }


def _to_decimal(x: float, quantum: Decimal = _DECIMAL_QUANTUM) -> Decimal:
    """Convert a numpy/python float to a quantized Decimal.

    We round through ``str()`` to avoid the ``Decimal(0.1)`` precision
    surprise -- going through the string repr gives the user-expected
    base-10 value before the quantize.

    Non-finite values are never silently coerced (no-silent-fallback).
    """
    if not np.isfinite(x):
        logger.warning("monte_carlo: non-finite value %s rejected", x)
        raise ValueError(f"non-finite value cannot be converted to Decimal: {x}")
    return Decimal(str(float(x))).quantize(quantum)


def _validate_inputs(
    trade_returns: Sequence[Decimal],
    n_simulations: int,
    initial_capital: Decimal,
) -> None:
    if not trade_returns:
        raise ValueError("trade_returns must not be empty")
    if len(trade_returns) < MIN_SAMPLES:
        raise ValueError(
            f"trade_returns must contain at least {MIN_SAMPLES} trades "
            "for a statistically meaningful bootstrap"
        )
    if n_simulations < 1:
        raise ValueError("n_simulations must be >= 1")
    if n_simulations > MAX_ITERATIONS:
        raise ValueError(f"n_simulations capped at {MAX_ITERATIONS:,} for synchronous API")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be > 0")

    arr = np.asarray([float(r) for r in trade_returns], dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError("trade_returns must be finite decimal fractions (no NaN/Inf)")


@dataclass
class MonteCarloSimulator:
    """Bootstrap-resampling Monte Carlo over a fixed list of trade returns.

    Stateless -- instances exist only to keep the call site readable
    (``MonteCarloSimulator().run(...)``). No side-effects, no DB access.

    Parameters
    ----------
    risk_free_rate
        Annualized risk-free rate used in the Sharpe numerator. Defaults
        to 0 because most retail backtests are reported gross of cash
        return; if you wire this to a higher-fidelity engine, pass an
        annualized rate (e.g. ``Decimal("0.045")`` for 4.5%).
    """

    risk_free_rate: Decimal = Decimal("0")

    def run(
        self,
        trade_returns: Sequence[Decimal],
        n_simulations: int = 10_000,
        initial_capital: Decimal = Decimal("100000"),
        seed: int | None = None,
        weights: Sequence[float] | None = None,
    ) -> MonteCarloResult:
        """Run the simulation.

        Parameters
        ----------
        trade_returns
            Sequence of per-trade returns expressed as Decimal fractions.
            ``Decimal("0.025")`` means +2.5% on the trade. The resampler
            treats each entry as one independent trade outcome.
        n_simulations
            Number of bootstrap iterations. 10,000 is enough to stabilize
            P5/P95 within ~+/-1% on most realistic distributions.
        initial_capital
            Starting equity. Final equity = ``initial_capital * prod(1 + r_i)``.
        seed
            If provided, seeds a ``numpy.random.default_rng`` for full
            reproducibility (same seed + inputs => same output).
        weights
            Optional sampling weights aligned with ``trade_returns``.
            Used by the scenarios module to bias toward winners /
            losers; ``None`` means uniform-with-replacement (iid).
        """
        _validate_inputs(trade_returns, n_simulations, initial_capital)

        returns = np.asarray([float(r) for r in trade_returns], dtype=np.float64)
        n_trades = returns.shape[0]
        capital_f = float(initial_capital)

        rng = np.random.default_rng(seed) if seed is not None else np.random.default_rng()

        if weights is not None:
            w = np.asarray(weights, dtype=np.float64)
            if w.shape[0] != n_trades:
                raise ValueError("weights length must equal trade_returns length")
            if np.any(w < 0):
                raise ValueError("weights must be non-negative")
            total = w.sum()
            if total <= 0:
                raise ValueError("weights must sum to > 0")
            probs: np.ndarray | None = w / total
        else:
            probs = None

        sample_idx = rng.choice(n_trades, size=(n_simulations, n_trades), replace=True, p=probs)
        sampled_returns = returns[sample_idx]

        gross = 1.0 + sampled_returns
        equity = capital_f * np.cumprod(gross, axis=1)

        pct_curve = np.percentile(equity, _FAN_PERCENTILES, axis=0)
        equity_curve = EquityCurvePercentiles(
            p5=[_to_decimal(v) for v in pct_curve[0]],
            p25=[_to_decimal(v) for v in pct_curve[1]],
            p50=[_to_decimal(v) for v in pct_curve[2]],
            p75=[_to_decimal(v) for v in pct_curve[3]],
            p95=[_to_decimal(v) for v in pct_curve[4]],
        )

        running_max = np.maximum.accumulate(equity, axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            drawdown = np.where(running_max > 0, 1.0 - equity / running_max, 0.0)
        max_dd = drawdown.max(axis=1) * 100.0

        rf_per_period = float(self.risk_free_rate) / TRADING_DAYS_PER_YEAR
        excess = sampled_returns - rf_per_period
        mean_excess = excess.mean(axis=1)
        std_excess = excess.std(axis=1, ddof=1) if n_trades > 1 else np.zeros(n_simulations)
        with np.errstate(divide="ignore", invalid="ignore"):
            sharpe = np.where(
                std_excess > 0,
                (mean_excess / std_excess) * np.sqrt(TRADING_DAYS_PER_YEAR),
                0.0,
            )

        terminal = equity[:, -1]

        prob_loss = float((terminal < capital_f).mean())
        prob_2x = float((terminal >= 2.0 * capital_f).mean())

        return MonteCarloResult(
            equity_curve=equity_curve,
            max_drawdown_pct=_summarize(max_dd),
            sharpe=_summarize(sharpe),
            terminal_value=_summarize(terminal),
            probability_of_loss=_to_decimal(prob_loss),
            probability_of_2x=_to_decimal(prob_2x),
            params={
                "n_simulations": n_simulations,
                "n_trades": n_trades,
                "initial_capital": str(initial_capital),
                "seed": seed,
                "risk_free_rate": str(self.risk_free_rate),
                "weighted": weights is not None,
            },
        )


def _summarize(arr: np.ndarray) -> DistributionStats:
    """Compute the canonical six-number summary of a 1-D distribution."""
    pcts = np.percentile(arr, [5, 25, 50, 75, 95])
    return DistributionStats(
        mean=_to_decimal(float(arr.mean())),
        median=_to_decimal(float(pcts[2])),
        p5=_to_decimal(float(pcts[0])),
        p25=_to_decimal(float(pcts[1])),
        p75=_to_decimal(float(pcts[3])),
        p95=_to_decimal(float(pcts[4])),
        std=_to_decimal(float(arr.std(ddof=1) if arr.size > 1 else 0.0)),
    )
