"""
Tests for app.services.backtest.monte_carlo

Acceptance criteria:

* Reproducibility: same ``seed`` ⇒ identical result.
* Known-distribution test: when fed a sample with known mean, the
  recovered mean terminal value matches theoretical within ±2%.
* P5/P95 of the equity-curve fan bracket the empirical no-resample
  terminal value (a deterministic sanity check that the bootstrap
  centers on the input).
* Output shape & validation: probabilities ∈ [0,1], drawdown ∈ [0,100],
  equity curves match trade count, Decimal everywhere.
* Scenario presets: optimistic/pessimistic/iid behave as advertised.

HTTP / DB integration tests live in ``test_monte_carlo_api.py``.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

pytestmark = pytest.mark.no_db

from app.services.backtest.monte_carlo import (
    MAX_ITERATIONS,
    MIN_SAMPLES,
    MonteCarloResult,
    MonteCarloSimulator,
)
from app.services.backtest.scenarios import (
    SCENARIO_DESCRIPTIONS,
    run_all_scenarios,
    run_scenario,
)


# A fixed return distribution we use across many tests. Mix of winners
# and losers, mean ~+0.5%, stdev ~3.5% — close to a real swing strategy.
# Padded to ``MIN_SAMPLES`` for bootstrap validity gates.
_BASE_TRADE_RETURNS: list[Decimal] = [
    Decimal("0.020"),
    Decimal("-0.010"),
    Decimal("0.035"),
    Decimal("-0.025"),
    Decimal("0.045"),
    Decimal("-0.015"),
    Decimal("0.025"),
    Decimal("-0.020"),
    Decimal("0.030"),
    Decimal("-0.005"),
    Decimal("0.015"),
    Decimal("-0.030"),
    Decimal("0.040"),
    Decimal("-0.020"),
    Decimal("0.010"),
]
_TRADE_RETURNS: list[Decimal] = (_BASE_TRADE_RETURNS * 2)[:MIN_SAMPLES]
assert len(_TRADE_RETURNS) == MIN_SAMPLES


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """Same seed + same inputs ⇒ bit-identical results."""

    def test_reproducible_with_seed(self):
        sim = MonteCarloSimulator()
        a = sim.run(_TRADE_RETURNS, n_simulations=500, seed=42)
        b = sim.run(_TRADE_RETURNS, n_simulations=500, seed=42)
        assert a.to_dict() == b.to_dict(), (
            "Identical inputs + seed must yield identical Decimal output. "
            "If this fails, the RNG is leaking state between runs."
        )

    def test_different_seeds_differ(self):
        sim = MonteCarloSimulator()
        a = sim.run(_TRADE_RETURNS, n_simulations=500, seed=1)
        b = sim.run(_TRADE_RETURNS, n_simulations=500, seed=2)
        assert a.terminal_value.median != b.terminal_value.median, (
            "Different seeds should produce different distributions; "
            "if they collide here the seed isn't actually being used."
        )

    def test_seed_matches_across_scenario_calls(self):
        a = run_scenario("iid_baseline", _TRADE_RETURNS, n_simulations=500, seed=7)
        b = run_scenario("iid_baseline", _TRADE_RETURNS, n_simulations=500, seed=7)
        assert a.result.to_dict() == b.result.to_dict()


# ---------------------------------------------------------------------------
# Known-distribution accuracy
# ---------------------------------------------------------------------------


class TestKnownDistribution:
    """Recover the input distribution within tolerance.

    For an iid bootstrap, the *expected* mean terminal equity equals
    ``initial * (1 + sample_mean) ** n_trades`` where ``sample_mean`` is
    the empirical mean of the *input* returns (not the population mean
    they were drawn from).     At 5,000 simulations × N=30 trades this
    estimate is tight enough to test within ±2%.
    """

    def test_mean_terminal_within_2pct_tolerance(self):
        rng = np.random.default_rng(2024)
        # 30 trades drawn from a known normal distribution.
        sample = rng.normal(loc=0.005, scale=0.03, size=30)
        trade_returns = [Decimal(str(round(r, 6))) for r in sample]
        sample_mean = float(np.mean([float(r) for r in trade_returns]))

        sim = MonteCarloSimulator()
        result = sim.run(
            trade_returns,
            n_simulations=5_000,
            initial_capital=Decimal("100000"),
            seed=2024,
        )
        # The expected mean of cumprod(1+R) ≠ (1+E[R])^n in general
        # because of Jensen's; but for the per-simulation *median* of
        # equity * the *mean across simulations* should land near the
        # geometric expectation. We use the bootstrap empirical mean
        # rather than the population mean to keep the assertion exact.
        expected = 100000.0 * (1.0 + sample_mean) ** 30
        recovered = float(result.terminal_value.mean)
        rel_err = abs(recovered - expected) / expected
        assert rel_err < 0.02, (
            f"Expected ~{expected:.2f}, got {recovered:.2f} "
            f"(rel_err={rel_err:.4f}). Bootstrap mean drifted >2% from "
            "the geometric mean of the resampled returns."
        )

    def test_p5_p95_bracket_sample_terminal(self):
        """Deterministic sample terminal should fall inside [P5, P95]."""
        sim = MonteCarloSimulator()
        result = sim.run(
            _TRADE_RETURNS,
            n_simulations=5_000,
            initial_capital=Decimal("100000"),
            seed=11,
        )
        # Compute the in-order, no-resample terminal value.
        capital = Decimal("100000")
        for r in _TRADE_RETURNS:
            capital = capital * (Decimal("1") + r)
        deterministic_terminal = float(capital)
        p5 = float(result.terminal_value.p5)
        p95 = float(result.terminal_value.p95)
        assert p5 <= deterministic_terminal <= p95, (
            f"Deterministic terminal {deterministic_terminal:.2f} fell "
            f"outside the [{p5:.2f}, {p95:.2f}] 90% CI — the bootstrap "
            "should bracket the input order at this sample size."
        )

    def test_p5_p95_equity_curve_monotone_at_sample_size(self):
        """For each step, P5 ≤ P50 ≤ P95 (a basic percentile sanity check)."""
        sim = MonteCarloSimulator()
        result = sim.run(_TRADE_RETURNS, n_simulations=2_000, seed=3)
        for i, (lo, mid, hi) in enumerate(
            zip(
                result.equity_curve.p5,
                result.equity_curve.p50,
                result.equity_curve.p95,
            )
        ):
            assert lo <= mid <= hi, (
                f"Percentile order broken at step {i}: "
                f"p5={lo}, p50={mid}, p95={hi}"
            )


# ---------------------------------------------------------------------------
# Output shape and types
# ---------------------------------------------------------------------------


class TestOutputShape:
    def test_equity_curve_length_matches_trades(self):
        sim = MonteCarloSimulator()
        result = sim.run(_TRADE_RETURNS, n_simulations=200, seed=0)
        assert len(result.equity_curve.p5) == len(_TRADE_RETURNS)
        assert len(result.equity_curve.p50) == len(_TRADE_RETURNS)
        assert len(result.equity_curve.p95) == len(_TRADE_RETURNS)

    def test_probabilities_in_unit_interval(self):
        sim = MonteCarloSimulator()
        result = sim.run(_TRADE_RETURNS, n_simulations=500, seed=0)
        assert Decimal("0") <= result.probability_of_loss <= Decimal("1")
        assert Decimal("0") <= result.probability_of_2x <= Decimal("1")

    def test_drawdown_in_zero_hundred_pct(self):
        sim = MonteCarloSimulator()
        result = sim.run(_TRADE_RETURNS, n_simulations=500, seed=0)
        assert Decimal("0") <= result.max_drawdown_pct.median <= Decimal("100")
        assert Decimal("0") <= result.max_drawdown_pct.p95 <= Decimal("100")

    def test_to_dict_is_string_decimals(self):
        """API response must serialize Decimals as strings to preserve precision."""
        sim = MonteCarloSimulator()
        d = sim.run(_TRADE_RETURNS, n_simulations=100, seed=0).to_dict()
        assert isinstance(d["probability_of_loss"], str)
        assert isinstance(d["probability_of_2x"], str)
        for v in d["equity_curve"]["p50"]:
            assert isinstance(v, str)
        for v in d["max_drawdown_pct"].values():
            assert isinstance(v, str)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_empty_returns_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            MonteCarloSimulator().run([], n_simulations=100)

    def test_validates_min_samples(self):
        few = _TRADE_RETURNS[: MIN_SAMPLES - 1]
        with pytest.raises(ValueError, match="at least"):
            MonteCarloSimulator().run(few, n_simulations=100)

    def test_zero_simulations_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            MonteCarloSimulator().run(_TRADE_RETURNS, n_simulations=0)

    def test_validates_iterations_cap(self):
        with pytest.raises(ValueError, match="capped"):
            MonteCarloSimulator().run(
                _TRADE_RETURNS, n_simulations=MAX_ITERATIONS + 1
            )

    def test_negative_capital_raises(self):
        with pytest.raises(ValueError, match="> 0"):
            MonteCarloSimulator().run(
                _TRADE_RETURNS,
                n_simulations=100,
                initial_capital=Decimal("-1"),
            )

    def test_weights_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="weights length"):
            MonteCarloSimulator().run(
                _TRADE_RETURNS,
                n_simulations=100,
                weights=[1.0, 2.0],
            )

    def test_negative_weights_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            MonteCarloSimulator().run(
                _TRADE_RETURNS,
                n_simulations=100,
                weights=[-1.0] * len(_TRADE_RETURNS),
            )

    def test_zero_weights_raises(self):
        with pytest.raises(ValueError, match="sum to > 0"):
            MonteCarloSimulator().run(
                _TRADE_RETURNS,
                n_simulations=100,
                weights=[0.0] * len(_TRADE_RETURNS),
            )

    def test_non_finite_trade_return_raises(self):
        bad = list(_TRADE_RETURNS)
        bad[0] = Decimal("NaN")
        with pytest.raises(ValueError, match="finite"):
            MonteCarloSimulator().run(bad, n_simulations=100, seed=1)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


class TestScenarios:
    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError, match="Unknown scenario"):
            run_scenario("not_a_scenario", _TRADE_RETURNS)

    def test_run_all_scenarios_returns_three(self):
        results = run_all_scenarios(_TRADE_RETURNS, n_simulations=300, seed=0)
        assert set(results) == set(SCENARIO_DESCRIPTIONS)
        assert all(isinstance(r.result, MonteCarloResult) for r in results.values())

    def test_optimistic_beats_pessimistic_on_median_terminal(self):
        results = run_all_scenarios(_TRADE_RETURNS, n_simulations=2_000, seed=99)
        opt = float(results["optimistic_skew"].result.terminal_value.median)
        pes = float(results["pessimistic_skew"].result.terminal_value.median)
        assert opt > pes, (
            f"Optimistic median ({opt:.2f}) should exceed pessimistic "
            f"median ({pes:.2f}). If not, weight bias isn't being applied."
        )

    def test_iid_lies_between_skews(self):
        results = run_all_scenarios(_TRADE_RETURNS, n_simulations=2_000, seed=99)
        opt = float(results["optimistic_skew"].result.terminal_value.median)
        iid = float(results["iid_baseline"].result.terminal_value.median)
        pes = float(results["pessimistic_skew"].result.terminal_value.median)
        assert pes <= iid <= opt, (
            f"Expected pessimistic <= iid <= optimistic; got "
            f"pes={pes:.2f}, iid={iid:.2f}, opt={opt:.2f}."
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSingleTrade:
    """Identical per-trade returns collapse the terminal distribution."""

    def test_identical_returns_collapses_distribution(self):
        sim = MonteCarloSimulator()
        identical = [Decimal("0.05")] * MIN_SAMPLES
        result = sim.run(
            identical,
            n_simulations=200,
            initial_capital=Decimal("100"),
            seed=0,
        )
        assert result.terminal_value.p5 == result.terminal_value.p95
        assert result.terminal_value.p5 == result.terminal_value.median
        expected_terminal = 100.0 * (1.05**MIN_SAMPLES)
        assert abs(float(result.terminal_value.median) - expected_terminal) < 1e-6


class TestDecimalBoundaries:
    def test_decimal_inputs_preserved(self):
        """String Decimals at ingress survive quantization at the boundary."""
        sim = MonteCarloSimulator()
        returns = [Decimal("0.01")] * MIN_SAMPLES
        result = sim.run(
            returns,
            n_simulations=300,
            initial_capital=Decimal("1000.00"),
            seed=99,
        )
        assert result.params["initial_capital"] == "1000.00"
        assert all(isinstance(x, Decimal) for x in result.equity_curve.p50)
