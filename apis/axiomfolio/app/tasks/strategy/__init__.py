"""
Strategy Tasks Package
======================

Celery tasks for strategy operations:
- Signal evaluation
- Entry/exit scanning
- Portfolio allocation
- Auto-backtesting
"""

from .auto_backtest import (
    run_auto_backtest,
    trigger_auto_backtest_on_change,
)
from .tasks import (
    evaluate_strategies_task,
)

__all__ = [
    "evaluate_strategies_task",
    "run_auto_backtest",
    "trigger_auto_backtest_on_change",
]
