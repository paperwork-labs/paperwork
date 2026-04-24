"""Optuna-driven walk-forward hyperparameter optimization.

This is a *new* optimizer that complements (does not replace) the existing
:class:`app.services.strategy.walk_forward.WalkForwardAnalyzer`. The
older analyzer runs a single parameter set across multiple folds and
applies veto gates; this module *searches* a parameter space with Optuna,
scores each trial on out-of-sample windows, and reports per-regime
attribution.

Architecture
------------

1. The caller supplies a ``StrategyBuilder`` callable that turns a
   ``params`` dict into ``(entry_rules, exit_rules)`` for the existing
   :class:`app.services.strategy.backtest_engine.BacktestEngine`. We
   never modify the engine — the optimizer is a thin shell that asks the
   engine to run on each train/test window.
2. The dataset is described by a list of symbols + date range. Splits are
   contiguous, non-overlapping rolling windows; the test window
   immediately follows the train window with no purge gap (we leave
   purged-CV to the older analyzer).
3. Each Optuna trial = N splits. The *trial score* is the mean test-window
   objective across all splits. We persist per-split scores so the UI can
   render a bar chart of stability.
4. A ``StudyResult`` carries best params, best score, all per-split
   results for the best trial, and per-regime attribution. The persistence
   layer (``WalkForwardStudy`` model) stores it; the API serves it.

Read-only safety
----------------
The optimizer never places orders or mutates broker / position state. It
operates entirely on historical data via ``MarketSnapshotHistory`` (the
backtest engine's only data source).

medallion: gold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

import optuna
from optuna.samplers import TPESampler
from sqlalchemy.orm import Session

from app.services.gold.backtest.objectives import (
    OBJECTIVES,
    ObjectiveFn,
    get_objective,
    list_objectives,
)
from app.services.gold.backtest.regime_attribution import (
    REGIME_LABELS,
    RegimeLookup,
    attribute_trades_by_regime,
    filter_trades_by_regime,
)
from app.services.gold.strategy.backtest_engine import BacktestEngine, BacktestTrade
from app.services.gold.strategy.rule_evaluator import ConditionGroup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class TradeResult:
    """A single closed round-trip in a test window.

    ``return_pct`` is the realized fractional return (e.g. ``Decimal("0.12")``
    means +12%). It is *not* annualized; objectives that need annualization
    handle it themselves.
    """

    entry_date: date
    exit_date: date
    pnl: Decimal
    return_pct: Decimal
    symbol: str = ""
    regime: Optional[str] = None  # R1-R5 or None when lookup unavailable


@dataclass
class SplitResult:
    """Per-split summary for one trial."""

    split_index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    train_score: Decimal
    test_score: Decimal
    trade_count: int

    def to_dict(self) -> dict:
        return {
            "split_index": self.split_index,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "train_score": float(self.train_score),
            "test_score": float(self.test_score),
            "trade_count": self.trade_count,
        }


@dataclass
class StudyResult:
    """Top-level result emitted by :meth:`WalkForwardOptimizer.optimize`."""

    best_params: Dict[str, Any]
    best_score: Decimal
    objective: str
    total_trials: int
    per_split_results: List[SplitResult]
    regime_attribution: Dict[str, Dict[str, float]]
    failed_trials: int = 0

    def to_dict(self) -> dict:
        return {
            "best_params": self.best_params,
            "best_score": float(self.best_score),
            "objective": self.objective,
            "total_trials": self.total_trials,
            "failed_trials": self.failed_trials,
            "per_split_results": [s.to_dict() for s in self.per_split_results],
            "regime_attribution": self.regime_attribution,
        }


# ---------------------------------------------------------------------------
# Strategy + runner protocols
# ---------------------------------------------------------------------------


StrategyBuilder = Callable[[Dict[str, Any]], Tuple[ConditionGroup, ConditionGroup]]
"""Build entry + exit rule trees from a candidate parameter set."""


class WindowRunner(Protocol):
    """Run the strategy on one (start, end) window and return its trades.

    The default implementation in :func:`build_default_runner` calls
    :class:`BacktestEngine`. Tests inject a synthetic runner so they can
    exercise the optimizer's search loop without staging
    ``MarketSnapshotHistory`` rows.
    """

    def __call__(
        self,
        params: Dict[str, Any],
        symbols: Sequence[str],
        window_start: date,
        window_end: date,
    ) -> List[TradeResult]: ...


# ---------------------------------------------------------------------------
# Default runner (real engine)
# ---------------------------------------------------------------------------


def _bt_trade_to_result(
    entry: BacktestTrade,
    exit_: BacktestTrade,
    regime_lookup: Optional[RegimeLookup],
) -> TradeResult:
    """Pair a buy + sell from the engine into a TradeResult.

    The engine emits ``BacktestTrade`` per side; the optimizer needs
    closed round-trips. ``return_pct`` uses the buy price as denominator
    and the realized PnL as numerator; commissions/slippage are already
    baked into the prices and the PnL by the engine.
    """
    entry_dt = date.fromisoformat(str(entry.date))
    exit_dt = date.fromisoformat(str(exit_.date))
    cost = Decimal(str(entry.price)) * Decimal(str(entry.quantity))
    pnl = Decimal(str(exit_.pnl))
    ret = pnl / cost if cost > 0 else Decimal("0")
    regime = regime_lookup(entry_dt) if regime_lookup else None
    return TradeResult(
        entry_date=entry_dt,
        exit_date=exit_dt,
        pnl=pnl,
        return_pct=ret,
        symbol=entry.symbol,
        regime=regime,
    )


def _engine_trades_to_results(
    engine_trades: Sequence[BacktestTrade],
    regime_lookup: Optional[RegimeLookup],
) -> List[TradeResult]:
    """Pair each closing 'sell' to its most recent 'buy' for the same symbol."""
    open_buys: Dict[str, BacktestTrade] = {}
    out: List[TradeResult] = []
    for t in engine_trades:
        if t.side == "buy":
            # If a stale buy is still open we replace it to keep the runner
            # idempotent across edge cases (engine should not emit two buys
            # for the same symbol but defensive coding pays here).
            open_buys[t.symbol] = t
        elif t.side == "sell":
            buy = open_buys.pop(t.symbol, None)
            if buy is None:
                logger.debug(
                    "sell without matching buy for %s on %s — skipping pairing",
                    t.symbol,
                    t.date,
                )
                continue
            out.append(_bt_trade_to_result(buy, t, regime_lookup))
    return out


def build_default_runner(
    db: Session,
    strategy_builder: StrategyBuilder,
    *,
    initial_capital: float = 100_000.0,
    position_size_pct: float = 0.05,
    slippage_bps: float = 5.0,
    commission_per_trade: float = 1.0,
    regime_lookup: Optional[RegimeLookup] = None,
) -> WindowRunner:
    """Wire the production :class:`BacktestEngine` into a ``WindowRunner``.

    The engine is created once and reused across windows since it is
    stateless. The DB session is captured by closure — the caller
    controls its lifetime (per the iron law that services must not own
    sessions).
    """
    engine = BacktestEngine(
        slippage_bps=slippage_bps, commission_per_trade=commission_per_trade
    )

    def runner(
        params: Dict[str, Any],
        symbols: Sequence[str],
        window_start: date,
        window_end: date,
    ) -> List[TradeResult]:
        entry_rules, exit_rules = strategy_builder(params)
        result = engine.run(
            db=db,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            symbols=list(symbols),
            start_date=window_start,
            end_date=window_end,
            initial_capital=initial_capital,
            position_size_pct=position_size_pct,
        )
        return _engine_trades_to_results(result.trades, regime_lookup)

    return runner


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------


def _generate_splits(
    dataset_start: date,
    dataset_end: date,
    train_window_days: int,
    test_window_days: int,
    n_splits: int,
) -> List[Tuple[date, date, date, date]]:
    """Build rolling, non-overlapping (train_start, train_end, test_start,
    test_end) tuples.

    Layout:
        ┌──train──┐┌──test──┐
                  ┌──train──┐┌──test──┐
                            ┌──train──┐┌──test──┐
        |←—————————— available days ——————————→|

    The window slides forward by ``test_window_days`` per split (so trials
    cover non-overlapping out-of-sample periods). Raises ``ValueError`` if
    the dataset cannot fit even one split — silently returning [] would
    make a study look like it ran successfully on no data.
    """
    if train_window_days <= 0 or test_window_days <= 0:
        raise ValueError(
            "train_window_days and test_window_days must be positive integers"
        )
    if n_splits <= 0:
        raise ValueError("n_splits must be a positive integer")

    total_days = (dataset_end - dataset_start).days
    needed = train_window_days + test_window_days * n_splits
    if total_days < needed:
        raise ValueError(
            f"Dataset spans {total_days} days but {n_splits} splits require "
            f"at least {needed} days (train={train_window_days} + "
            f"{n_splits}*test={test_window_days})."
        )

    splits: List[Tuple[date, date, date, date]] = []
    for i in range(n_splits):
        train_start = dataset_start + timedelta(days=i * test_window_days)
        train_end = train_start + timedelta(days=train_window_days - 1)
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=test_window_days - 1)
        if test_end > dataset_end:
            break
        splits.append((train_start, train_end, test_start, test_end))
    if not splits:
        raise ValueError(
            "No splits could be generated; check dataset / window sizing."
        )
    return splits


# ---------------------------------------------------------------------------
# Optuna param-space adapter
# ---------------------------------------------------------------------------


def _suggest(trial: optuna.Trial, name: str, spec: Dict[str, Any]) -> Any:
    """Translate a JSON param spec into an Optuna ``trial.suggest_*`` call.

    Spec shapes::

        {"type": "int", "low": 5, "high": 40, "step": 5}
        {"type": "float", "low": 0.01, "high": 0.5, "log": false}
        {"type": "categorical", "choices": ["sma", "ema"]}
    """
    kind = spec.get("type")
    if kind == "int":
        low = int(spec["low"])
        high = int(spec["high"])
        step = int(spec.get("step", 1))
        return trial.suggest_int(name, low, high, step=step)
    if kind == "float":
        low = float(spec["low"])
        high = float(spec["high"])
        log = bool(spec.get("log", False))
        return trial.suggest_float(name, low, high, log=log)
    if kind == "categorical":
        choices = spec["choices"]
        if not isinstance(choices, list) or not choices:
            raise ValueError(f"categorical param '{name}' needs non-empty 'choices'")
        return trial.suggest_categorical(name, choices)
    raise ValueError(f"Unknown param type '{kind}' for '{name}'")


def validate_param_space(param_space: Dict[str, Dict[str, Any]]) -> None:
    """Cheap upfront check so a bad config rejects at API time instead of
    inside a Celery task that has already taken the heavy lock."""
    if not isinstance(param_space, dict) or not param_space:
        raise ValueError("param_space must be a non-empty mapping")
    for name, spec in param_space.items():
        if not isinstance(spec, dict):
            raise ValueError(f"param '{name}' spec must be a dict")
        kind = spec.get("type")
        if kind not in ("int", "float", "categorical"):
            raise ValueError(
                f"param '{name}' has unsupported type '{kind}'; "
                f"expected one of int/float/categorical"
            )
        if kind in ("int", "float"):
            if "low" not in spec or "high" not in spec:
                raise ValueError(f"param '{name}' requires 'low' and 'high'")
            if float(spec["high"]) <= float(spec["low"]):
                raise ValueError(f"param '{name}' high must be > low")
        if kind == "categorical":
            if not spec.get("choices"):
                raise ValueError(f"param '{name}' requires non-empty 'choices'")


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardOptimizer:
    """Run a walk-forward Optuna study against a pluggable runner.

    Attributes:
        runner: Callable that backtests one window and returns trades.
        objective_name: Key into :data:`OBJECTIVES`.
        n_trials: Optuna trial budget.
        timeout_s: Optional hard wall clock for the whole study; the
            Celery wrapper enforces its own ``time_limit`` separately.
        seed: Sampler seed for deterministic reproducibility in tests.
        progress_callback: Optional ``(completed, total) -> None`` hook
            that the Celery task wires into a DB update so the frontend
            polling endpoint shows live progress.
    """

    runner: WindowRunner
    objective_name: str = "sharpe_ratio"
    n_trials: int = 50
    timeout_s: Optional[int] = None
    seed: Optional[int] = 42
    progress_callback: Optional[Callable[[int, int], None]] = None

    def __post_init__(self) -> None:
        if self.objective_name not in OBJECTIVES:
            raise ValueError(
                f"Unknown objective '{self.objective_name}'. "
                f"Available: {list_objectives()}"
            )

    def optimize(
        self,
        param_space: Dict[str, Dict[str, Any]],
        symbols: Sequence[str],
        dataset_start: date,
        dataset_end: date,
        train_window_days: int,
        test_window_days: int,
        n_splits: int,
        regime_filter: Optional[str] = None,
    ) -> StudyResult:
        """Run the study and return a :class:`StudyResult`.

        ``regime_filter`` (optional R1-R5) restricts scoring to trades
        whose entry date matches that regime — useful for "what params
        win in chop?" studies.
        """
        validate_param_space(param_space)
        if regime_filter is not None and regime_filter not in REGIME_LABELS:
            raise ValueError(
                f"regime_filter must be one of {REGIME_LABELS} or None"
            )

        splits = _generate_splits(
            dataset_start, dataset_end, train_window_days, test_window_days, n_splits
        )
        objective_fn: ObjectiveFn = get_objective(self.objective_name)

        # Cache per-trial trade lists so we can replay regime attribution
        # for the winning trial without re-running every backtest.
        trial_state: Dict[int, Dict[str, Any]] = {}
        completed_trials = 0
        failed_trials = 0

        def trial_objective(trial: optuna.Trial) -> float:
            nonlocal completed_trials, failed_trials
            params = {name: _suggest(trial, name, spec) for name, spec in param_space.items()}
            split_results: List[SplitResult] = []
            all_trades: List[TradeResult] = []
            try:
                for idx, (tr_s, tr_e, te_s, te_e) in enumerate(splits):
                    train_trades = self.runner(params, symbols, tr_s, tr_e)
                    test_trades = self.runner(params, symbols, te_s, te_e)
                    if regime_filter:
                        test_trades_for_score = filter_trades_by_regime(
                            test_trades, regime_filter
                        )
                    else:
                        test_trades_for_score = test_trades
                    train_score = objective_fn(train_trades)
                    test_score = objective_fn(test_trades_for_score)
                    split_results.append(
                        SplitResult(
                            split_index=idx,
                            train_start=tr_s,
                            train_end=tr_e,
                            test_start=te_s,
                            test_end=te_e,
                            train_score=train_score,
                            test_score=test_score,
                            trade_count=len(test_trades),
                        )
                    )
                    all_trades.extend(test_trades)
            except Exception as e:
                # We never silently zero out a failed trial — Optuna's
                # behavior on a raise is to mark it FAILED and keep
                # searching. We log + count for the run summary.
                failed_trials += 1
                logger.warning(
                    "trial %s failed for params=%s: %s", trial.number, params, e
                )
                raise

            mean_test_score = sum(
                (s.test_score for s in split_results), Decimal("0")
            ) / Decimal(len(split_results))

            trial_state[trial.number] = {
                "splits": split_results,
                "trades": all_trades,
            }
            completed_trials += 1
            if self.progress_callback:
                try:
                    self.progress_callback(completed_trials, self.n_trials)
                except Exception as cb_err:
                    # Progress reporting must never sink the study.
                    logger.warning("progress callback raised: %s", cb_err)
            return float(mean_test_score)

        sampler = TPESampler(seed=self.seed)
        # Suppress Optuna's INFO chatter — we have our own logging cadence
        # and the Celery worker logs are already noisy.
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(
            trial_objective,
            n_trials=self.n_trials,
            timeout=self.timeout_s,
            catch=(Exception,),
            show_progress_bar=False,
        )

        if study.best_trial is None:
            raise RuntimeError("Optuna did not produce any successful trial")

        best_state = trial_state.get(study.best_trial.number)
        if not best_state:
            raise RuntimeError(
                "Best trial state missing — this indicates an internal "
                "accounting bug; refusing to silently return zeros."
            )

        best_trades: List[TradeResult] = best_state["trades"]
        regime_attr = attribute_trades_by_regime(best_trades, objective_fn)

        return StudyResult(
            best_params=dict(study.best_params),
            best_score=Decimal(str(study.best_value)),
            objective=self.objective_name,
            total_trials=len(study.trials),
            per_split_results=best_state["splits"],
            regime_attribution=regime_attr,
            failed_trials=failed_trials,
        )
