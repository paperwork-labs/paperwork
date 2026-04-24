"""Walk-forward hyperparameter optimization and advanced backtest analysis.

This package complements the existing rules-based ``BacktestEngine`` in
``app/services/strategy/backtest_engine.py``. Walk-forward tooling wraps
the engine: trades are rolled into train/test splits, scored by a pluggable
objective, and explored with Optuna.

Monte Carlo and related modules consume the engine's output (trade returns,
equity curves) and produce higher-order analysis: confidence intervals,
bootstrap distributions, regime-conditional reports.

Sub-modules import lazily where needed so an optional dependency for one
analysis type does not break the whole package.

medallion: gold
"""

from app.services.backtest.walk_forward import (
    SplitResult,
    StrategyBuilder,
    StudyResult,
    TradeResult,
    WalkForwardOptimizer,
    build_default_runner,
)

__all__ = [
    "SplitResult",
    "StrategyBuilder",
    "StudyResult",
    "TradeResult",
    "WalkForwardOptimizer",
    "build_default_runner",
]
