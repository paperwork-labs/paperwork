"""
Monte Carlo backtest endpoint
=============================

POST ``/api/v1/backtest/monte-carlo`` runs a single bootstrap or all
three preset scenarios on a list of trade returns and returns the
confidence-interval result synchronously.

Tier-gated to ``research.monte_carlo`` (Pro+ in the catalog). The work
is CPU-bound numpy and stays well under the 5s request budget at the
default 10,000 simulations x a few hundred trades, so we don't push
this onto Celery yet -- that becomes a future move when we expose
n_simulations > 100k or operate on cohort-level fan charts.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import require_feature
from app.models.user import User
from app.services.gold.backtest.monte_carlo import (
    MAX_ITERATIONS,
    MIN_SAMPLES,
    MonteCarloSimulator,
)
from app.services.gold.backtest.scenarios import (
    SCENARIO_DESCRIPTIONS,
    run_all_scenarios,
    run_scenario,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class MonteCarloRequest(BaseModel):
    """Request body for /backtest/monte-carlo.

    ``trade_returns`` is a list of per-trade decimal returns (e.g.
    ``0.025`` for +2.5%). Pydantic v2 will accept JSON numbers and
    coerce them to ``Decimal`` so the simulator never sees float; if
    the caller wants to preserve precision they can send strings.

    Extra fields are rejected so clients cannot pass an unscoped
    ``strategy_id`` (or similar) until the server implements an
    explicit ``user_id`` ownership check for that path.
    """

    model_config = ConfigDict(extra="forbid")

    trade_returns: List[Decimal] = Field(
        ...,
        min_length=MIN_SAMPLES,
        description=(
            "Per-trade returns as decimal fractions (e.g. 0.025 for +2.5%). "
            f"At least {MIN_SAMPLES} trades required."
        ),
    )
    n_simulations: int = Field(
        default=10_000,
        ge=100,
        le=MAX_ITERATIONS,
        description="Number of bootstrap iterations (capped for synchronous API).",
    )
    initial_capital: Decimal = Field(
        default=Decimal("100000"),
        gt=Decimal("0"),
        description="Starting equity in account currency.",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Optional RNG seed for reproducibility.",
    )
    risk_free_rate: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="Annualized risk-free rate used in Sharpe numerator.",
    )
    scenario: Optional[str] = Field(
        default=None,
        description=(
            "If set, runs only the named preset scenario "
            "('iid_baseline' | 'optimistic_skew' | 'pessimistic_skew'). "
            "If omitted and run_all_scenarios=False, the iid baseline is used."
        ),
    )
    run_all_scenarios: bool = Field(
        default=False,
        description="When true, runs all three preset scenarios and returns each.",
    )


@router.post("/monte-carlo")
def post_monte_carlo(
    payload: MonteCarloRequest,
    user: User = Depends(require_feature("research.monte_carlo")),
) -> Dict[str, Any]:
    """Run Monte Carlo simulation(s) on the supplied trade returns.

    Multi-tenancy: scoped to ``user.id`` via ``require_feature`` (which
    calls ``get_current_user``). Trade returns are supplied inline only;
    there is no server-side load of another user's saved backtest unless
    a future field (e.g. ``strategy_id``) is added with an explicit
    ``strategy.user_id == current_user.id`` guard.
    """
    try:
        if payload.run_all_scenarios:
            results = run_all_scenarios(
                payload.trade_returns,
                n_simulations=payload.n_simulations,
                initial_capital=payload.initial_capital,
                seed=payload.seed,
                risk_free_rate=payload.risk_free_rate,
            )
            return {
                "mode": "all_scenarios",
                "scenarios": {name: r.to_dict() for name, r in results.items()},
                "available_scenarios": list(SCENARIO_DESCRIPTIONS),
            }

        if payload.scenario:
            scenario_result = run_scenario(
                payload.scenario,
                payload.trade_returns,
                n_simulations=payload.n_simulations,
                initial_capital=payload.initial_capital,
                seed=payload.seed,
                risk_free_rate=payload.risk_free_rate,
            )
            return {
                "mode": "scenario",
                "scenario": scenario_result.to_dict(),
                "available_scenarios": list(SCENARIO_DESCRIPTIONS),
            }

        sim = MonteCarloSimulator(risk_free_rate=payload.risk_free_rate)
        result = sim.run(
            payload.trade_returns,
            n_simulations=payload.n_simulations,
            initial_capital=payload.initial_capital,
            seed=payload.seed,
        )
        return {
            "mode": "single",
            "result": result.to_dict(),
            "available_scenarios": list(SCENARIO_DESCRIPTIONS),
        }

    except ValueError as e:
        logger.info("monte_carlo: invalid request from user %s: %s", user.id, e)
        raise HTTPException(status_code=400, detail=str(e)) from e
