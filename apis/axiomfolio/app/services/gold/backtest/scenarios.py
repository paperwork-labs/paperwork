"""
Monte Carlo Preset Scenarios
============================

Wraps :class:`MonteCarloSimulator` with three opinionated sampling
strategies the UI exposes as presets:

* ``iid_baseline`` -- uniform-with-replacement; the textbook bootstrap.
* ``optimistic_skew`` -- biases the sampler toward the user's winning
  trades. Answers "if my edge is real and persists, what does the next
  N trades look like?".
* ``pessimistic_skew`` -- biases toward losing trades. Stress test --
  "if conditions get worse, how bad can the equity curve get?".

The skew weights are intentionally simple (2x on the skewed side, 1x
on the other) to keep the result interpretable. More elaborate weight
schemes belong in a future "regime-conditional Monte Carlo" sub-phase.

medallion: gold
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Sequence

from app.services.gold.backtest.monte_carlo import (
    MonteCarloResult,
    MonteCarloSimulator,
)


_SKEW_FACTOR: float = 2.0


@dataclass(frozen=True)
class ScenarioResult:
    """One scenario's Monte Carlo result + the scenario metadata."""

    name: str
    description: str
    result: MonteCarloResult

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "result": self.result.to_dict(),
        }


SCENARIO_DESCRIPTIONS: Dict[str, str] = {
    "iid_baseline": (
        "Uniform-with-replacement bootstrap. Each historical trade is "
        "equally likely to be sampled -- the standard Monte Carlo baseline."
    ),
    "optimistic_skew": (
        "Winners are weighted ~2x more likely to be drawn. Use to "
        "estimate upside if your edge persists or strengthens."
    ),
    "pessimistic_skew": (
        "Losers are weighted ~2x more likely to be drawn. Use as a "
        "stress test for adverse drift in conditions."
    ),
}


def _winner_weights(returns: Sequence[Decimal]) -> List[float]:
    """Return per-trade sampling weights that bias toward winning trades.

    A trade is a "winner" if its return is strictly positive. Flat trades
    get a baseline weight of 1.0 so they're neither boosted nor suppressed.
    """
    return [_SKEW_FACTOR if float(r) > 0 else 1.0 for r in returns]


def _loser_weights(returns: Sequence[Decimal]) -> List[float]:
    """Return per-trade sampling weights that bias toward losing trades."""
    return [_SKEW_FACTOR if float(r) < 0 else 1.0 for r in returns]


def run_scenario(
    name: str,
    trade_returns: Sequence[Decimal],
    *,
    n_simulations: int = 10_000,
    initial_capital: Decimal = Decimal("100000"),
    seed: Optional[int] = None,
    risk_free_rate: Decimal = Decimal("0"),
) -> ScenarioResult:
    """Run a single named scenario and return its result.

    Raises
    ------
    ValueError
        if ``name`` is not one of the known scenarios. We raise rather
        than fall back to ``iid_baseline`` so a typo on the API surfaces
        as a 4xx instead of silently producing the wrong picture.
    """
    if name not in SCENARIO_DESCRIPTIONS:
        raise ValueError(
            f"Unknown scenario '{name}'. Valid: {sorted(SCENARIO_DESCRIPTIONS)}"
        )

    sim = MonteCarloSimulator(risk_free_rate=risk_free_rate)

    if name == "iid_baseline":
        weights: Optional[List[float]] = None
    elif name == "optimistic_skew":
        weights = _winner_weights(trade_returns)
    elif name == "pessimistic_skew":
        weights = _loser_weights(trade_returns)
    else:
        raise AssertionError(f"unreachable scenario {name}")

    result = sim.run(
        trade_returns,
        n_simulations=n_simulations,
        initial_capital=initial_capital,
        seed=seed,
        weights=weights,
    )
    return ScenarioResult(
        name=name,
        description=SCENARIO_DESCRIPTIONS[name],
        result=result,
    )


def run_all_scenarios(
    trade_returns: Sequence[Decimal],
    *,
    n_simulations: int = 10_000,
    initial_capital: Decimal = Decimal("100000"),
    seed: Optional[int] = None,
    risk_free_rate: Decimal = Decimal("0"),
) -> Dict[str, ScenarioResult]:
    """Run all three preset scenarios and return them keyed by name.

    Each scenario gets the *same* base seed; numpy's PRNG state is
    fresh per ``run_scenario`` call so the seed-vs-weights interaction
    is deterministic.
    """
    return {
        name: run_scenario(
            name,
            trade_returns,
            n_simulations=n_simulations,
            initial_capital=initial_capital,
            seed=seed,
            risk_free_rate=risk_free_rate,
        )
        for name in SCENARIO_DESCRIPTIONS
    }
