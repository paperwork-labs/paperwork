"""Backtest engine -- replays strategy rules against historical market data.

medallion: gold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.market_data import MarketSnapshotHistory
from app.services.strategy.context_builder import add_prev_fields, history_to_context
from app.services.strategy.rule_evaluator import (
    ConditionGroup,
    RuleEvaluator,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    symbol: str
    side: str
    quantity: float
    price: float
    date: str
    pnl: float = 0.0


@dataclass
class BacktestMetrics:
    initial_capital: float
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    total_trades: int
    win_rate: float
    profit_factor: float | None
    avg_trade_pnl: float
    max_win: float
    max_loss: float


@dataclass
class BacktestResult:
    metrics: BacktestMetrics
    equity_curve: list[dict[str, Any]]
    trades: list[BacktestTrade]
    daily_returns: list[float]


class PositionTracker:
    """Tracks open positions during a backtest."""

    def __init__(self):
        self.positions: dict[str, dict[str, float]] = {}

    def open(self, symbol: str, quantity: float, price: float) -> None:
        if symbol in self.positions:
            existing = self.positions[symbol]
            total_qty = existing["quantity"] + quantity
            existing["avg_price"] = (
                existing["avg_price"] * existing["quantity"] + price * quantity
            ) / total_qty
            existing["quantity"] = total_qty
        else:
            self.positions[symbol] = {"quantity": quantity, "avg_price": price}

    def close(self, symbol: str, quantity: float, price: float) -> float:
        if symbol not in self.positions:
            return 0.0
        pos = self.positions[symbol]
        qty_to_close = min(quantity, pos["quantity"])
        pnl = qty_to_close * (price - pos["avg_price"])
        pos["quantity"] -= qty_to_close
        if pos["quantity"] <= 0.001:
            del self.positions[symbol]
        return pnl

    def unrealized_pnl(self, prices: dict[str, float]) -> float:
        total = 0.0
        for symbol, pos in self.positions.items():
            current = prices.get(symbol, pos["avg_price"])
            total += pos["quantity"] * (current - pos["avg_price"])
        return total


class BacktestEngine:
    """Replay strategy rules against MarketSnapshotHistory."""

    def __init__(self, slippage_bps: float = 5.0, commission_per_trade: float = 1.0):
        self.slippage_bps = slippage_bps
        self.commission = commission_per_trade
        self.evaluator = RuleEvaluator()

    def run(
        self,
        db: Session,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        symbols: list[str],
        start_date: date,
        end_date: date,
        initial_capital: float = 100_000.0,
        position_size_pct: float = 0.05,
    ) -> BacktestResult:
        snapshots = self._load_history(db, symbols, start_date, end_date)
        if not snapshots:
            return self._empty_result(initial_capital)

        tracker = PositionTracker()
        trades: list[BacktestTrade] = []
        equity_curve: list[dict[str, Any]] = []
        daily_returns: list[float] = []

        cash = initial_capital
        prev_equity = initial_capital

        dates = sorted(snapshots.keys())
        for day in dates:
            day_data = snapshots[day]
            prices = {s["symbol"]: s.get("current_price", 0) for s in day_data}

            for snap in day_data:
                symbol = snap["symbol"]
                price = snap.get("current_price", 0)
                if not price or price <= 0:
                    continue

                context = {**snap}

                if symbol in tracker.positions:
                    result = self.evaluator.evaluate(exit_rules, context)
                    if result.matched:
                        qty = tracker.positions[symbol]["quantity"]
                        sell_price = price * (1 - self.slippage_bps / 10000)
                        pnl = tracker.close(symbol, qty, sell_price) - self.commission
                        cash += qty * sell_price - self.commission
                        trades.append(
                            BacktestTrade(
                                symbol=symbol,
                                side="sell",
                                quantity=qty,
                                price=sell_price,
                                date=day,
                                pnl=pnl,
                            )
                        )
                else:
                    result = self.evaluator.evaluate(entry_rules, context)
                    if result.matched:
                        alloc = initial_capital * position_size_pct
                        qty = max(1, int(alloc / price))
                        cost = qty * price * (1 + self.slippage_bps / 10000) + self.commission
                        if cost <= cash:
                            buy_price = price * (1 + self.slippage_bps / 10000)
                            tracker.open(symbol, qty, buy_price)
                            cash -= cost
                            trades.append(
                                BacktestTrade(
                                    symbol=symbol,
                                    side="buy",
                                    quantity=qty,
                                    price=buy_price,
                                    date=day,
                                )
                            )

            equity = cash + sum(
                tracker.positions.get(s, {}).get("quantity", 0) * prices.get(s, 0) for s in prices
            )
            daily_return = (equity - prev_equity) / prev_equity if prev_equity else 0
            daily_returns.append(daily_return)
            equity_curve.append({"date": day, "equity": round(equity, 2)})
            prev_equity = equity

        final_equity = equity_curve[-1]["equity"] if equity_curve else initial_capital
        metrics = self._compute_metrics(initial_capital, final_equity, trades, daily_returns)
        return BacktestResult(
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades,
            daily_returns=daily_returns,
        )

    def _load_history(
        self, db: Session, symbols: list[str], start: date, end: date
    ) -> dict[str, list[dict[str, Any]]]:
        rows = (
            db.query(MarketSnapshotHistory)
            .filter(
                MarketSnapshotHistory.symbol.in_([s.upper() for s in symbols]),
                MarketSnapshotHistory.as_of_date >= start,
                MarketSnapshotHistory.as_of_date <= end,
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshotHistory.as_of_date)
            .all()
        )
        # First pass: group rows by symbol to track previous day's data
        by_symbol: dict[str, list[MarketSnapshotHistory]] = {}
        for r in rows:
            if r.symbol not in by_symbol:
                by_symbol[r.symbol] = []
            by_symbol[r.symbol].append(r)

        # Second pass: build context with _prev fields for crossover detection
        by_date: dict[str, list[dict[str, Any]]] = {}
        symbol_prev: dict[str, MarketSnapshotHistory | None] = {}

        for r in rows:
            d = str(r.as_of_date)
            if d not in by_date:
                by_date[d] = []
            # Use context builder with aliases; regime_state comes from history row
            ctx = history_to_context(r, include_regime=False, db=None)
            # Add _prev fields for crossover detection
            prev_row = symbol_prev.get(r.symbol)
            ctx = add_prev_fields(ctx, prev_row)
            by_date[d].append(ctx)
            # Track this row as previous for next iteration
            symbol_prev[r.symbol] = r

        return by_date

    def _compute_metrics(
        self,
        initial: float,
        final: float,
        trades: list[BacktestTrade],
        daily_returns: list[float],
    ) -> BacktestMetrics:
        total_return = ((final - initial) / initial) * 100 if initial else 0

        equity_peak = initial
        max_dd = 0.0
        running = initial
        for r in daily_returns:
            running *= 1 + r
            equity_peak = max(equity_peak, running)
            dd = (equity_peak - running) / equity_peak if equity_peak else 0
            max_dd = max(max_dd, dd)

        sell_trades = [t for t in trades if t.side == "sell"]
        wins = [t for t in sell_trades if t.pnl > 0]
        losses = [t for t in sell_trades if t.pnl <= 0]

        win_rate = len(wins) / len(sell_trades) if sell_trades else 0
        avg_pnl = sum(t.pnl for t in sell_trades) / len(sell_trades) if sell_trades else 0
        max_win = max((t.pnl for t in sell_trades), default=0)
        max_loss = min((t.pnl for t in sell_trades), default=0)

        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

        sharpe = None
        sortino = None
        if len(daily_returns) > 1:
            mean_r = sum(daily_returns) / len(daily_returns)
            std_r = (
                sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            ) ** 0.5
            if std_r > 0:
                sharpe = (mean_r / std_r) * (252**0.5)
            neg_returns = [r for r in daily_returns if r < 0]
            if neg_returns:
                downside_std = (sum(r**2 for r in neg_returns) / len(neg_returns)) ** 0.5
                if downside_std > 0:
                    sortino = (mean_r / downside_std) * (252**0.5)

        return BacktestMetrics(
            initial_capital=initial,
            final_capital=final,
            total_return_pct=round(total_return, 2),
            max_drawdown_pct=round(max_dd * 100, 2),
            sharpe_ratio=round(sharpe, 3) if sharpe else None,
            sortino_ratio=round(sortino, 3) if sortino else None,
            total_trades=len(trades),
            win_rate=round(win_rate, 3),
            profit_factor=round(profit_factor, 3) if profit_factor else None,
            avg_trade_pnl=round(avg_pnl, 2),
            max_win=round(max_win, 2),
            max_loss=round(max_loss, 2),
        )

    def _empty_result(self, capital: float) -> BacktestResult:
        return BacktestResult(
            metrics=BacktestMetrics(
                initial_capital=capital,
                final_capital=capital,
                total_return_pct=0,
                max_drawdown_pct=0,
                sharpe_ratio=None,
                sortino_ratio=None,
                total_trades=0,
                win_rate=0,
                profit_factor=None,
                avg_trade_pnl=0,
                max_win=0,
                max_loss=0,
            ),
            equity_curve=[],
            trades=[],
            daily_returns=[],
        )
