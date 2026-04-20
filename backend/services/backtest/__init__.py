"""Advanced backtest analysis services (Monte Carlo, walk-forward, etc).

This package complements the existing rules-based ``BacktestEngine`` in
``backend/services/strategy/backtest_engine.py``. Modules here consume
the engine's output (lists of trade returns, equity curves) and produce
higher-order analysis: confidence intervals, hyperparameter studies,
regime-conditional reports.

Sub-modules import lazily so an environment that lacks an optional
dependency for one analysis type doesn't break the whole package.
"""
