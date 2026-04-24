"""
Walk-Forward Analysis with Purged Cross-Validation.

Implements proper out-of-sample validation:
- Purged gaps to prevent lookahead bias
- Multiple train/test splits
- Degradation detection
- Veto gates for production deployment

medallion: gold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.services.strategy.backtest_engine import BacktestEngine, BacktestResult
from app.services.strategy.rule_evaluator import ConditionGroup

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardFold:
    """A single train/test split in walk-forward analysis."""

    fold_number: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    train_result: BacktestResult | None
    test_result: BacktestResult | None

    @property
    def train_sharpe(self) -> float | None:
        if self.train_result and self.train_result.metrics:
            return self.train_result.metrics.sharpe_ratio
        return None

    @property
    def test_sharpe(self) -> float | None:
        if self.test_result and self.test_result.metrics:
            return self.test_result.metrics.sharpe_ratio
        return None

    @property
    def degradation(self) -> float | None:
        """Calculate performance degradation from train to test."""
        if self.train_sharpe and self.test_sharpe:
            if self.train_sharpe != 0:
                return (self.train_sharpe - self.test_sharpe) / abs(self.train_sharpe)
        return None

    def to_dict(self) -> dict:
        return {
            "fold_number": self.fold_number,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "train_sharpe": self.train_sharpe,
            "test_sharpe": self.test_sharpe,
            "degradation": self.degradation,
        }


@dataclass
class VetoGateResult:
    """Result of a veto gate check."""

    name: str
    passed: bool
    value: float | None
    threshold: float
    message: str


@dataclass
class WalkForwardResult:
    """Complete walk-forward analysis result."""

    strategy_id: int | None
    n_folds: int
    purge_days: int
    folds: list[WalkForwardFold]
    veto_results: list[VetoGateResult]
    summary: dict[str, Any]
    passed_all_gates: bool
    recommendation: str  # "deploy", "paper_trade", "reject"

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "n_folds": self.n_folds,
            "purge_days": self.purge_days,
            "folds": [f.to_dict() for f in self.folds],
            "veto_results": [
                {
                    "name": v.name,
                    "passed": v.passed,
                    "value": v.value,
                    "threshold": v.threshold,
                    "message": v.message,
                }
                for v in self.veto_results
            ],
            "summary": self.summary,
            "passed_all_gates": self.passed_all_gates,
            "recommendation": self.recommendation,
        }


class WalkForwardAnalyzer:
    """
    Walk-forward analysis with proper purged cross-validation.

    Key features:
    - Purged gaps between train and test to prevent lookahead bias
    - Multiple overlapping folds for robustness
    - Degradation tracking (train vs test performance)
    - Veto gates for production deployment
    """

    # Default veto gate thresholds
    VETO_MIN_AVG_TEST_SHARPE = 0.3
    VETO_MAX_AVG_DEGRADATION = 0.5  # 50% max degradation
    VETO_MIN_POSITIVE_FOLDS = 0.6  # 60% of folds must be profitable
    VETO_MIN_TEST_WIN_RATE = 0.4
    VETO_MAX_TEST_DRAWDOWN = 25.0  # %

    def __init__(
        self,
        db: Session,
        n_folds: int = 5,
        purge_days: int = 5,
        test_size_days: int = 60,
    ):
        self.db = db
        self.n_folds = n_folds
        self.purge_days = purge_days
        self.test_size_days = test_size_days
        self.engine = BacktestEngine()

    def analyze(
        self,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        symbols: list[str],
        start_date: date,
        end_date: date,
        strategy_id: int | None = None,
    ) -> WalkForwardResult:
        """
        Run walk-forward analysis on a strategy.

        Args:
            entry_rules: Entry conditions
            exit_rules: Exit conditions
            symbols: Universe of symbols
            start_date: Start of analysis period
            end_date: End of analysis period
            strategy_id: Optional strategy ID for logging

        Returns:
            WalkForwardResult with folds, veto gates, and recommendation
        """
        logger.info(
            "Starting walk-forward analysis: %d folds, %d purge days, %s to %s",
            self.n_folds,
            self.purge_days,
            start_date,
            end_date,
        )

        # Generate fold splits
        folds = self._generate_folds(start_date, end_date)

        # Run backtests for each fold
        for fold in folds:
            logger.info(
                "Running fold %d: train %s-%s, test %s-%s",
                fold.fold_number,
                fold.train_start,
                fold.train_end,
                fold.test_start,
                fold.test_end,
            )

            # Train period backtest
            fold.train_result = self.engine.run(
                db=self.db,
                entry_rules=entry_rules,
                exit_rules=exit_rules,
                symbols=symbols,
                start_date=fold.train_start,
                end_date=fold.train_end,
            )

            # Test period backtest
            fold.test_result = self.engine.run(
                db=self.db,
                entry_rules=entry_rules,
                exit_rules=exit_rules,
                symbols=symbols,
                start_date=fold.test_start,
                end_date=fold.test_end,
            )

        # Calculate summary statistics
        summary = self._calculate_summary(folds)

        # Apply veto gates
        veto_results = self._apply_veto_gates(folds, summary)

        # Determine final recommendation
        passed_all = all(v.passed for v in veto_results)
        recommendation = self._determine_recommendation(veto_results, summary)

        return WalkForwardResult(
            strategy_id=strategy_id,
            n_folds=self.n_folds,
            purge_days=self.purge_days,
            folds=folds,
            veto_results=veto_results,
            summary=summary,
            passed_all_gates=passed_all,
            recommendation=recommendation,
        )

    def _generate_folds(self, start_date: date, end_date: date) -> list[WalkForwardFold]:
        """
        Generate train/test splits with purged gaps.

        Uses expanding window: each fold has more training data.
        Purge gap between train_end and test_start prevents lookahead.
        """
        folds = []
        total_days = (end_date - start_date).days

        # Minimum training period
        min_train_days = 120

        # Calculate fold boundaries
        available_test_days = total_days - min_train_days - self.purge_days
        if available_test_days < self.test_size_days:
            logger.warning("Not enough data for requested folds")
            return []

        fold_step = (available_test_days - self.test_size_days) // max(self.n_folds - 1, 1)

        for i in range(self.n_folds):
            # Test period moves forward with each fold
            test_start_offset = min_train_days + self.purge_days + (i * fold_step)
            test_start = start_date + timedelta(days=test_start_offset)
            test_end = min(test_start + timedelta(days=self.test_size_days), end_date)

            # Train period is everything before the purge
            train_start = start_date
            train_end = test_start - timedelta(days=self.purge_days + 1)

            folds.append(
                WalkForwardFold(
                    fold_number=i + 1,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_result=None,
                    test_result=None,
                )
            )

        return folds

    def _calculate_summary(self, folds: list[WalkForwardFold]) -> dict[str, Any]:
        """Calculate summary statistics across all folds."""
        train_sharpes = [f.train_sharpe for f in folds if f.train_sharpe is not None]
        test_sharpes = [f.test_sharpe for f in folds if f.test_sharpe is not None]
        degradations = [f.degradation for f in folds if f.degradation is not None]

        # Test metrics
        test_returns = []
        test_drawdowns = []
        test_win_rates = []

        for fold in folds:
            if fold.test_result and fold.test_result.metrics:
                metrics = fold.test_result.metrics
                test_returns.append(metrics.total_return_pct)
                test_drawdowns.append(metrics.max_drawdown_pct)
                if metrics.win_rate is not None:
                    test_win_rates.append(metrics.win_rate)

        return {
            "avg_train_sharpe": np.mean(train_sharpes) if train_sharpes else None,
            "avg_test_sharpe": np.mean(test_sharpes) if test_sharpes else None,
            "avg_degradation": np.mean(degradations) if degradations else None,
            "positive_folds": sum(1 for s in test_sharpes if s and s > 0),
            "total_folds": len(folds),
            "positive_fold_ratio": (
                sum(1 for s in test_sharpes if s and s > 0) / len(folds) if folds else 0
            ),
            "avg_test_return": np.mean(test_returns) if test_returns else None,
            "avg_test_drawdown": np.mean(test_drawdowns) if test_drawdowns else None,
            "avg_test_win_rate": np.mean(test_win_rates) if test_win_rates else None,
            "train_sharpe_std": np.std(train_sharpes) if len(train_sharpes) > 1 else None,
            "test_sharpe_std": np.std(test_sharpes) if len(test_sharpes) > 1 else None,
        }

    def _apply_veto_gates(
        self, folds: list[WalkForwardFold], summary: dict[str, Any]
    ) -> list[VetoGateResult]:
        """Apply veto gates to determine if strategy is production-ready."""
        results = []

        # Gate 1: Minimum test Sharpe
        avg_test_sharpe = summary.get("avg_test_sharpe")
        if avg_test_sharpe and avg_test_sharpe >= self.VETO_MIN_AVG_TEST_SHARPE:
            min_sharpe_msg = (
                f"Avg test Sharpe {avg_test_sharpe:.2f} >= {self.VETO_MIN_AVG_TEST_SHARPE}"
            )
        else:
            sharpe_display = f"{avg_test_sharpe:.2f}" if avg_test_sharpe else "N/A"
            min_sharpe_msg = f"Avg test Sharpe {sharpe_display} < {self.VETO_MIN_AVG_TEST_SHARPE}"
        results.append(
            VetoGateResult(
                name="min_test_sharpe",
                passed=(
                    avg_test_sharpe is not None and avg_test_sharpe >= self.VETO_MIN_AVG_TEST_SHARPE
                ),
                value=avg_test_sharpe,
                threshold=self.VETO_MIN_AVG_TEST_SHARPE,
                message=min_sharpe_msg,
            )
        )

        # Gate 2: Maximum degradation
        avg_degradation = summary.get("avg_degradation")
        if avg_degradation and abs(avg_degradation) <= self.VETO_MAX_AVG_DEGRADATION:
            max_deg_msg = (
                f"Avg degradation {abs(avg_degradation) * 100:.1f}% <= "
                f"{self.VETO_MAX_AVG_DEGRADATION * 100}%"
            )
        else:
            deg_pct = abs(avg_degradation) * 100 if avg_degradation else 0.0
            max_deg_msg = f"Avg degradation {deg_pct:.1f}% > {self.VETO_MAX_AVG_DEGRADATION * 100}%"
        results.append(
            VetoGateResult(
                name="max_degradation",
                passed=(
                    avg_degradation is not None
                    and abs(avg_degradation) <= self.VETO_MAX_AVG_DEGRADATION
                ),
                value=avg_degradation,
                threshold=self.VETO_MAX_AVG_DEGRADATION,
                message=max_deg_msg,
            )
        )

        # Gate 3: Minimum positive folds
        positive_ratio = summary.get("positive_fold_ratio", 0)
        results.append(
            VetoGateResult(
                name="min_positive_folds",
                passed=positive_ratio >= self.VETO_MIN_POSITIVE_FOLDS,
                value=positive_ratio,
                threshold=self.VETO_MIN_POSITIVE_FOLDS,
                message=(
                    f"{positive_ratio * 100:.0f}% positive folds >= {self.VETO_MIN_POSITIVE_FOLDS * 100}%"
                    if positive_ratio >= self.VETO_MIN_POSITIVE_FOLDS
                    else f"{positive_ratio * 100:.0f}% positive folds < {self.VETO_MIN_POSITIVE_FOLDS * 100}%"
                ),
            )
        )

        # Gate 4: Minimum test win rate
        avg_win_rate = summary.get("avg_test_win_rate")
        if avg_win_rate and avg_win_rate >= self.VETO_MIN_TEST_WIN_RATE:
            win_rate_msg = (
                f"Avg test win rate {avg_win_rate * 100:.1f}% >= "
                f"{self.VETO_MIN_TEST_WIN_RATE * 100}%"
            )
        else:
            win_pct = avg_win_rate * 100 if avg_win_rate else 0.0
            win_rate_msg = (
                f"Avg test win rate {win_pct:.1f}% < {self.VETO_MIN_TEST_WIN_RATE * 100}%"
            )
        results.append(
            VetoGateResult(
                name="min_test_win_rate",
                passed=(avg_win_rate is not None and avg_win_rate >= self.VETO_MIN_TEST_WIN_RATE),
                value=avg_win_rate,
                threshold=self.VETO_MIN_TEST_WIN_RATE,
                message=win_rate_msg,
            )
        )

        # Gate 5: Maximum test drawdown
        avg_drawdown = summary.get("avg_test_drawdown")
        if avg_drawdown and avg_drawdown <= self.VETO_MAX_TEST_DRAWDOWN:
            drawdown_msg = (
                f"Avg test drawdown {avg_drawdown:.1f}% <= {self.VETO_MAX_TEST_DRAWDOWN}%"
            )
        else:
            dd_display = avg_drawdown if avg_drawdown else 0.0
            drawdown_msg = f"Avg test drawdown {dd_display:.1f}% > {self.VETO_MAX_TEST_DRAWDOWN}%"
        results.append(
            VetoGateResult(
                name="max_test_drawdown",
                passed=(avg_drawdown is not None and avg_drawdown <= self.VETO_MAX_TEST_DRAWDOWN),
                value=avg_drawdown,
                threshold=self.VETO_MAX_TEST_DRAWDOWN,
                message=drawdown_msg,
            )
        )

        return results

    def _determine_recommendation(
        self, veto_results: list[VetoGateResult], summary: dict[str, Any]
    ) -> str:
        """Determine deployment recommendation based on veto gates."""
        failed_gates = [v for v in veto_results if not v.passed]

        if len(failed_gates) == 0:
            return "deploy"
        elif len(failed_gates) <= 2:
            # Allow paper trading if only minor gates failed
            critical_gates = {"min_test_sharpe", "max_degradation"}
            if any(v.name in critical_gates for v in failed_gates):
                return "paper_trade"
            return "deploy"
        else:
            return "reject"
