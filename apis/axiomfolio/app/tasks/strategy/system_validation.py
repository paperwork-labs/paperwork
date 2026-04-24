"""
System-level backtest validation: Stage Analysis across historical regime periods.

Proves (or disproves) the trading system mathematically by running standardized
entry/exit rules against different market environments.
"""

import logging
from dataclasses import asdict
from datetime import date
from typing import Any, Dict, List, Optional

from celery import shared_task

from app.database import SessionLocal
from app.services.strategy.backtest_engine import BacktestEngine
from app.services.strategy.rule_evaluator import (
    Condition,
    ConditionGroup,
    ConditionOperator,
    LogicalOperator,
)
from app.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)

REGIME_PERIODS: List[Dict[str, Any]] = [
    {"name": "Dot-Com Bubble", "start": "1999-01-01", "end": "2001-12-31", "type": "bubble_burst"},
    {"name": "Post Dot-Com Recovery", "start": "2003-01-01", "end": "2007-06-30", "type": "bull"},
    {"name": "GFC", "start": "2007-07-01", "end": "2009-06-30", "type": "bear"},
    {"name": "Post-GFC Bull", "start": "2010-01-01", "end": "2015-12-31", "type": "bull"},
    {"name": "2016-2019 Bull", "start": "2016-01-01", "end": "2019-12-31", "type": "bull"},
    {"name": "COVID Crash", "start": "2020-01-01", "end": "2020-06-30", "type": "crash_recovery"},
    {"name": "Post-COVID Bull", "start": "2020-07-01", "end": "2021-12-31", "type": "bull"},
    {"name": "Rate Hike Bear", "start": "2022-01-01", "end": "2022-12-31", "type": "bear"},
    {"name": "2023-2024 Recovery", "start": "2023-01-01", "end": "2024-12-31", "type": "recovery"},
    {"name": "Full Period", "start": "1999-01-01", "end": "2026-03-31", "type": "all"},
]

ENTRY_RULES = ConditionGroup(
    logic=LogicalOperator.AND,
    conditions=[
        Condition(field="stage_label", operator=ConditionOperator.IN, value=["2A", "2B"]),
        Condition(field="rs_mansfield_pct", operator=ConditionOperator.GT, value=0),
        Condition(field="vol_ratio", operator=ConditionOperator.GT, value=1.0),
    ],
)

EXIT_RULES = ConditionGroup(
    logic=LogicalOperator.OR,
    conditions=[
        Condition(field="stage_label", operator=ConditionOperator.IN, value=["3B", "4A", "4B", "4C"]),
        Condition(field="rs_mansfield_pct", operator=ConditionOperator.LT, value=-5),
    ],
)

TOP_SYMBOLS = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM",
    "JNJ", "V", "PG", "UNH", "HD", "MA", "DIS", "NFLX", "ADBE",
    "CRM", "COST", "PEP", "ABBV", "TMO", "ACN", "MRK", "LLY",
    "AVGO", "TXN", "QCOM", "ORCL", "INTC", "CSCO", "IBM",
]


@shared_task(
    soft_time_limit=600,
    time_limit=660,
)
@task_run("system_backtest_validation")
def validate_stage_analysis(
    symbols: Optional[List[str]] = None,
    initial_capital: float = 100_000,
) -> dict:
    """Run Stage Analysis backtest across all regime periods and report metrics."""
    session = SessionLocal()
    try:
        use_symbols = symbols or TOP_SYMBOLS
        engine = BacktestEngine(slippage_bps=10.0, commission_per_trade=1.0)
        results: List[Dict[str, Any]] = []

        for period in REGIME_PERIODS:
            try:
                start = date.fromisoformat(period["start"])
                end = date.fromisoformat(period["end"])
                result = engine.run(
                    db=session,
                    entry_rules=ENTRY_RULES,
                    exit_rules=EXIT_RULES,
                    symbols=use_symbols,
                    start_date=start,
                    end_date=end,
                    initial_capital=initial_capital,
                    position_size_pct=0.05,
                )
                results.append({
                    "period": period["name"],
                    "type": period["type"],
                    "start": period["start"],
                    "end": period["end"],
                    "metrics": asdict(result.metrics),
                    "trade_count": len(result.trades),
                })
            except Exception as exc:
                logger.warning("Backtest failed for %s: %s", period["name"], exc)
                results.append({
                    "period": period["name"],
                    "type": period["type"],
                    "start": period["start"],
                    "end": period["end"],
                    "error": str(exc),
                })

        passing = sum(
            1
            for r in results
            if "metrics" in r
            and r["metrics"].get("sharpe_ratio") is not None
            and r["metrics"]["sharpe_ratio"] > 0.5
            and r["metrics"]["max_drawdown_pct"] < 30
        )

        return {
            "status": "ok",
            "symbols_tested": len(use_symbols),
            "periods_tested": len(results),
            "periods_passing": passing,
            "results": results,
        }
    finally:
        session.close()
