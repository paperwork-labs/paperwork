"""Strategy CRUD, composable rule evaluation, backtest, and template routes."""

from __future__ import annotations
from datetime import date, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.strategy import Strategy, StrategyType, StrategyStatus, BacktestRun, RunStatus
from app.models.backtest import StrategyBacktest, BacktestStatus
from app.models.market_data import MarketSnapshot
from app.services.gold.strategy.rule_evaluator import (
    RuleEvaluator,
    ConditionGroup,
    Condition,
    ConditionOperator,
    LogicalOperator,
)
from app.services.gold.strategy.signal_generator import SignalGenerator
from app.services.gold.strategy.backtest_engine import BacktestEngine
from app.services.gold.strategy.templates import (
    get_template,
    list_templates as _list_templates,
    STRATEGY_TEMPLATES,
)
from app.services.gold.strategy.context_builder import snapshot_to_context

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _trigger_auto_backtest(strategy_id: int, change_type: str = "update") -> None:
    """Queue auto-backtest for strategy if rules are present.
    
    Fire-and-forget: logs errors but doesn't propagate them to the API caller.
    """
    try:
        from app.tasks.strategy.auto_backtest import trigger_auto_backtest_on_change
        trigger_auto_backtest_on_change.delay(strategy_id, change_type=change_type)
        logger.info("Queued auto-backtest for strategy %s (%s)", strategy_id, change_type)
    except Exception as e:
        logger.warning("Failed to queue auto-backtest for strategy %s: %s", strategy_id, e)

_evaluator = RuleEvaluator()
_signal_gen = SignalGenerator()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ConditionSchema(BaseModel):
    field: str
    operator: str
    value: Any
    value_high: Optional[Any] = None


class ConditionGroupSchema(BaseModel):
    logic: str = "and"
    conditions: List[ConditionSchema] = Field(default_factory=list)
    groups: List["ConditionGroupSchema"] = Field(default_factory=list)


ConditionGroupSchema.model_rebuild()


class StrategyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    strategy_type: str = Field(..., description="One of the StrategyType enum values")
    config: Dict[str, Any] = Field(default_factory=dict)


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    strategy_type: Optional[str] = None
    status: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class EvaluateRequest(BaseModel):
    rules: ConditionGroupSchema
    symbols: Optional[List[str]] = None


class BacktestRequest(BaseModel):
    start_date: date
    end_date: date
    initial_capital: float = Field(default=100_000, gt=0)
    position_size_pct: float = Field(default=5.0, gt=0, le=100)
    symbols: Optional[List[str]] = None


class CreateFromTemplateRequest(BaseModel):
    template_id: str
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    overrides: Dict[str, Any] = Field(default_factory=dict)


class StrategyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    strategy_type: str
    status: str
    parameters: Dict[str, Any]
    created_at: Optional[str]
    updated_at: Optional[str]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_latest_strategy_backtests(
    db: Session, strategy_ids: List[int]
) -> Dict[int, StrategyBacktest]:
    """Most recent StrategyBacktest row per strategy (auto-backtest / validation pipeline)."""
    if not strategy_ids:
        return {}
    rows = (
        db.query(StrategyBacktest)
        .filter(StrategyBacktest.strategy_id.in_(strategy_ids))
        .order_by(StrategyBacktest.created_at.desc(), StrategyBacktest.id.desc())
        .all()
    )
    out: Dict[int, StrategyBacktest] = {}
    for r in rows:
        if r.strategy_id not in out:
            out[r.strategy_id] = r
    return out


def _metrics_from_backtest_row(bt: StrategyBacktest) -> Dict[str, Any]:
    return {
        "sharpe_ratio": float(bt.sharpe_ratio) if bt.sharpe_ratio is not None else None,
        "max_drawdown_pct": float(bt.max_drawdown_pct) if bt.max_drawdown_pct is not None else None,
        "win_rate": float(bt.win_rate) if bt.win_rate is not None else None,
    }


def _backtest_validation_payload(bt: Optional[StrategyBacktest]) -> Dict[str, Any]:
    """
    UI validation status for the latest auto-backtest row.

    Maps DB BacktestStatus + veto flags to PENDING | RUNNING | PASSED | FAILED | VETOED.
    """
    if bt is None:
        return {"status": "PENDING", "sharpe_ratio": None, "max_drawdown_pct": None, "win_rate": None}

    if bt.status == BacktestStatus.PENDING:
        return {**_metrics_from_backtest_row(bt), "status": "PENDING"}
    if bt.status == BacktestStatus.RUNNING:
        return {**_metrics_from_backtest_row(bt), "status": "RUNNING"}
    if bt.status == BacktestStatus.FAILED:
        return {**_metrics_from_backtest_row(bt), "status": "FAILED"}
    if bt.status == BacktestStatus.CANCELLED:
        return {**_metrics_from_backtest_row(bt), "status": "PENDING"}

    # COMPLETED
    payload = {**_metrics_from_backtest_row(bt), "status": "PASSED"}
    if bt.passed_veto_gates is False:
        payload["status"] = "VETOED"
    return payload


def _strategy_to_dict(
    s: Strategy, latest_backtest: Optional[StrategyBacktest] = None
) -> Dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "strategy_type": s.strategy_type.value if s.strategy_type else None,
        "status": s.status.value if s.status else None,
        "parameters": s.parameters or {},
        "execution_mode": s.execution_mode.value if s.execution_mode else None,
        "max_positions": s.max_positions,
        "position_size_pct": float(s.position_size_pct) if s.position_size_pct else None,
        "stop_loss_pct": float(s.stop_loss_pct) if s.stop_loss_pct else None,
        "take_profit_pct": float(s.take_profit_pct) if s.take_profit_pct else None,
        "run_frequency": s.run_frequency,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "backtest_validation": _backtest_validation_payload(latest_backtest),
    }


def _parse_condition_group(schema: ConditionGroupSchema) -> ConditionGroup:
    """Convert Pydantic schema to dataclass tree."""
    conditions = [
        Condition(
            field=c.field,
            operator=ConditionOperator(c.operator),
            value=c.value,
            value_high=c.value_high,
        )
        for c in schema.conditions
    ]
    groups = [_parse_condition_group(g) for g in schema.groups]
    return ConditionGroup(
        logic=LogicalOperator(schema.logic),
        conditions=conditions,
        groups=groups,
    )




# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_strategies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    strategies = (
        db.query(Strategy)
        .filter(Strategy.user_id == user.id)
        .order_by(Strategy.created_at.desc())
        .all()
    )
    sids = [s.id for s in strategies]
    latest_bt = _fetch_latest_strategy_backtests(db, sids)
    return {"data": [_strategy_to_dict(s, latest_bt.get(s.id)) for s in strategies]}


# ---------------------------------------------------------------------------
# Template routes (MUST be before /{strategy_id} to avoid path conflicts)
# ---------------------------------------------------------------------------

@router.get("/templates")
def list_strategy_templates():
    """Return summaries of all pre-built strategy templates."""
    return {"data": _list_templates()}


@router.get("/templates/{template_id}")
def get_strategy_template(template_id: str):
    """Return full template including rules config."""
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return {"data": tpl}


@router.post("/from-template", status_code=201)
def create_strategy_from_template(
    req: CreateFromTemplateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new strategy pre-filled from a template."""
    tpl = get_template(req.template_id)
    if not tpl:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{req.template_id}' not found",
        )

    try:
        stype = StrategyType(tpl["strategy_type"])
    except ValueError:
        stype = StrategyType.CUSTOM

    existing = (
        db.query(Strategy)
        .filter(Strategy.user_id == user.id, Strategy.name == req.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Strategy with this name already exists")

    config = dict(tpl.get("default_config", {}))
    config.update(req.overrides)

    strategy = Strategy(
        user_id=user.id,
        name=req.name,
        description=req.description or tpl.get("description", ""),
        strategy_type=stype,
        status=StrategyStatus.DRAFT,
        parameters=config,
        position_size_pct=tpl.get("position_size_pct", 5.0),
        max_positions=tpl.get("max_positions", 10),
        stop_loss_pct=tpl.get("stop_loss_pct", 8.0),
        max_holding_days=tpl.get("max_holding_days"),
        universe_filter=tpl.get("universe_filter"),
        created_by_user_id=user.id,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)

    # Queue auto-backtest for new template-based strategy
    _trigger_auto_backtest(strategy.id, change_type="create_from_template")

    latest_bt = _fetch_latest_strategy_backtests(db, [strategy.id])
    return {"data": _strategy_to_dict(strategy, latest_bt.get(strategy.id))}


@router.post("", status_code=201)
def create_strategy(
    req: StrategyCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        stype = StrategyType(req.strategy_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid strategy_type '{req.strategy_type}'. "
                   f"Valid: {[t.value for t in StrategyType]}",
        )

    existing = (
        db.query(Strategy)
        .filter(Strategy.user_id == user.id, Strategy.name == req.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Strategy with this name already exists")

    strategy = Strategy(
        user_id=user.id,
        name=req.name,
        description=req.description,
        strategy_type=stype,
        status=StrategyStatus.DRAFT,
        parameters=req.config,
        created_by_user_id=user.id,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)

    # Queue auto-backtest for new strategy
    _trigger_auto_backtest(strategy.id, change_type="create")

    latest_bt = _fetch_latest_strategy_backtests(db, [strategy.id])
    return {"data": _strategy_to_dict(strategy, latest_bt.get(strategy.id))}


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    latest_bt = _fetch_latest_strategy_backtests(db, [strategy.id])
    return {"data": _strategy_to_dict(strategy, latest_bt.get(strategy.id))}


@router.put("/{strategy_id}")
def update_strategy(
    strategy_id: int,
    req: StrategyUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if req.name is not None:
        dup = (
            db.query(Strategy)
            .filter(
                Strategy.user_id == user.id,
                Strategy.name == req.name,
                Strategy.id != strategy_id,
            )
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="Strategy with this name already exists")
        strategy.name = req.name

    if req.description is not None:
        strategy.description = req.description

    if req.strategy_type is not None:
        try:
            strategy.strategy_type = StrategyType(req.strategy_type)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid strategy_type '{req.strategy_type}'",
            )

    if req.status is not None:
        try:
            strategy.status = StrategyStatus(req.status)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status '{req.status}'",
            )

    rules_changed = False
    if req.config is not None:
        strategy.parameters = req.config
        rules_changed = True

    strategy.modified_by_user_id = user.id
    db.commit()
    db.refresh(strategy)

    # Queue auto-backtest if rules/config changed
    if rules_changed:
        _trigger_auto_backtest(strategy.id, change_type="update")

    latest_bt = _fetch_latest_strategy_backtests(db, [strategy.id])
    return {"data": _strategy_to_dict(strategy, latest_bt.get(strategy.id))}


@router.delete("/{strategy_id}")
def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    db.delete(strategy)
    db.commit()
    return {"data": {"id": strategy_id, "deleted": True}}


@router.post("/{strategy_id}/evaluate")
def evaluate_strategy(
    strategy_id: int,
    req: EvaluateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run rule evaluation against current MarketSnapshot data.

    Returns signals without persisting them.
    """
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    group = _parse_condition_group(req.rules)

    latest_ids_sub = (
        db.query(func.max(MarketSnapshot.id).label("id"))
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.is_valid.is_(True),
        )
        .group_by(MarketSnapshot.symbol)
        .subquery()
    )
    query = db.query(MarketSnapshot).join(
        latest_ids_sub, MarketSnapshot.id == latest_ids_sub.c.id
    )
    if req.symbols:
        normalized_symbols = [s.upper() for s in req.symbols]
        query = query.filter(MarketSnapshot.symbol.in_(normalized_symbols))

    snapshots = query.all()
    matches: List[Dict[str, Any]] = []
    for snap in snapshots:
        # Use context builder with regime context for consistent evaluation
        ctx = snapshot_to_context(snap, include_regime=True, db=db)
        result = _evaluator.evaluate(group, ctx)
        if result.matched:
            matches.append({
                "symbol": snap.symbol,
                "action": "buy",
                "strength": 1.0,
                "context": result.details,
                "regime_state": ctx.get("regime_state"),
                "regime_multiplier": ctx.get("regime_multiplier"),
            })

    signals = _signal_gen.generate_signals(db, strategy, matches)
    return {
        "data": {
            "strategy_id": strategy.id,
            "universe_scanned": len(snapshots),
            "matches": len(matches),
            "signals": signals,
        }
    }


@router.post("/{strategy_id}/backtest")
def run_backtest(
    strategy_id: int,
    req: BacktestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a backtest for a strategy against historical market data."""
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    params = strategy.parameters or {}
    entry_rules_raw = params.get("entry_rules")
    exit_rules_raw = params.get("exit_rules")
    if not entry_rules_raw or not exit_rules_raw:
        raise HTTPException(
            status_code=422,
            detail="Strategy must have entry_rules and exit_rules in parameters",
        )

    entry_rules = _parse_condition_group(ConditionGroupSchema(**entry_rules_raw))
    exit_rules = _parse_condition_group(ConditionGroupSchema(**exit_rules_raw))

    symbols = req.symbols
    if not symbols:
        universe = params.get("universe_symbols", [])
        if universe:
            symbols = universe
        else:
            snaps = (
                db.query(MarketSnapshot.symbol)
                .filter(
                    MarketSnapshot.analysis_type == "technical_snapshot",
                    MarketSnapshot.is_valid.is_(True),
                )
                .distinct()
                .all()
            )
            symbols = [s[0] for s in snaps]

    import time
    from datetime import datetime

    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()

    engine = BacktestEngine()
    result = engine.run(
        db=db,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        symbols=symbols,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_capital=req.initial_capital,
        position_size_pct=req.position_size_pct / 100,
    )

    execution_time = time.perf_counter() - start_time

    backtest_run = BacktestRun(
        strategy_id=strategy.id,
        user_id=user.id,
        name=f"{strategy.name} - {req.start_date} to {req.end_date}",
        start_date=datetime.combine(req.start_date, datetime.min.time()),
        end_date=datetime.combine(req.end_date, datetime.min.time()),
        initial_capital=req.initial_capital,
        status=RunStatus.COMPLETED,
        final_portfolio_value=result.metrics.final_capital,
        total_return_pct=result.metrics.total_return_pct,
        max_drawdown_pct=result.metrics.max_drawdown_pct,
        sharpe_ratio=result.metrics.sharpe_ratio,
        total_trades=result.metrics.total_trades,
        win_rate_pct=result.metrics.win_rate * 100,
        trades_executed=result.metrics.total_trades,
        execution_time_seconds=round(execution_time, 2),
        daily_returns=result.daily_returns,
        portfolio_values=[e["equity"] for e in result.equity_curve],
        trade_history=[
            {
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "date": str(t.date),
                "pnl": t.pnl,
            }
            for t in result.trades
        ],
        performance_metrics={
            "sortino_ratio": result.metrics.sortino_ratio,
            "profit_factor": result.metrics.profit_factor,
            "avg_trade_pnl": result.metrics.avg_trade_pnl,
            "max_win": result.metrics.max_win,
            "max_loss": result.metrics.max_loss,
        },
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(backtest_run)
    db.commit()
    db.refresh(backtest_run)

    return {
        "data": {
            "backtest_run_id": backtest_run.id,
            "strategy_id": strategy.id,
            "metrics": {
                "initial_capital": result.metrics.initial_capital,
                "final_capital": result.metrics.final_capital,
                "total_return_pct": result.metrics.total_return_pct,
                "max_drawdown_pct": result.metrics.max_drawdown_pct,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "sortino_ratio": result.metrics.sortino_ratio,
                "total_trades": result.metrics.total_trades,
                "win_rate": result.metrics.win_rate,
                "profit_factor": result.metrics.profit_factor,
                "avg_trade_pnl": result.metrics.avg_trade_pnl,
                "max_win": result.metrics.max_win,
                "max_loss": result.metrics.max_loss,
            },
            "equity_curve": result.equity_curve,
            "trades": [
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "date": t.date,
                    "pnl": t.pnl,
                }
                for t in result.trades
            ],
        }
    }


@router.get("/{strategy_id}/backtests")
def list_strategy_backtests(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all backtest runs for a strategy."""
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == user.id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    runs = (
        db.query(BacktestRun)
        .filter(
            BacktestRun.strategy_id == strategy_id,
            BacktestRun.user_id == user.id,
        )
        .order_by(BacktestRun.created_at.desc())
        .all()
    )

    return {
        "data": [
            {
                "id": r.id,
                "name": r.name,
                "start_date": r.start_date.date().isoformat() if r.start_date else None,
                "end_date": r.end_date.date().isoformat() if r.end_date else None,
                "status": r.status.value if r.status else None,
                "total_return_pct": r.total_return_pct,
                "max_drawdown_pct": r.max_drawdown_pct,
                "total_trades": r.total_trades,
                "win_rate_pct": r.win_rate_pct,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ],
        "count": len(runs),
    }


@router.get("/backtests/{backtest_id}")
def get_backtest_run(
    backtest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get details of a specific backtest run."""
    run = (
        db.query(BacktestRun)
        .filter(BacktestRun.id == backtest_id, BacktestRun.user_id == user.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    return {
        "data": {
            "id": run.id,
            "strategy_id": run.strategy_id,
            "name": run.name,
            "start_date": run.start_date.date().isoformat() if run.start_date else None,
            "end_date": run.end_date.date().isoformat() if run.end_date else None,
            "initial_capital": run.initial_capital,
            "status": run.status.value if run.status else None,
            "final_portfolio_value": run.final_portfolio_value,
            "total_return_pct": run.total_return_pct,
            "max_drawdown_pct": run.max_drawdown_pct,
            "sharpe_ratio": run.sharpe_ratio,
            "total_trades": run.total_trades,
            "win_rate_pct": run.win_rate_pct,
            "execution_time_seconds": run.execution_time_seconds,
            "trade_history": run.trade_history,
            "portfolio_values": run.portfolio_values,
            "performance_metrics": run.performance_metrics,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
    }


# ---------------------------------------------------------------------------
# Paper Trading Validation
# ---------------------------------------------------------------------------


@router.post("/{strategy_id}/paper-validation/start")
def start_paper_validation(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start paper trading validation for a strategy.
    
    Strategy must pass paper validation before it can be promoted to live trading.
    Default validation requires:
    - 7+ days of paper trading
    - 5+ paper trades
    - Win rate >= 40%
    - Max drawdown <= 15%
    """
    from app.services.gold.strategy.paper_validator import PaperValidator
    
    validator = PaperValidator(db)
    result = validator.start_validation(strategy_id, user.id)
    
    if "error" in result:
        status_code = 404 if "not found" in result["error"].lower() else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    
    return result


@router.get("/{strategy_id}/paper-validation/status")
def get_paper_validation_status(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current paper validation status and metrics."""
    from app.services.gold.strategy.paper_validator import PaperValidator
    
    validator = PaperValidator(db)
    result = validator.check_validation(strategy_id, user.id)
    
    return {
        "status": result.status.value,
        "days_elapsed": result.days_elapsed,
        "trades_count": result.trades_count,
        "win_rate_pct": result.win_rate_pct,
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "profit_factor": result.profit_factor,
        "checks": result.checks,
        "can_go_live": result.can_go_live,
        "message": result.message,
    }


@router.post("/{strategy_id}/paper-validation/promote")
def promote_to_live(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Promote a validated strategy to live trading.
    
    Only succeeds if paper validation has passed all checks.
    """
    from app.services.gold.strategy.paper_validator import PaperValidator
    
    validator = PaperValidator(db)
    result = validator.promote_to_live(strategy_id, user.id)
    
    if "error" in result:
        status_code = 404 if "not found" in result["error"].lower() else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    
    return result


@router.post("/{strategy_id}/paper-validation/reset")
def reset_paper_validation(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reset paper validation to start over."""
    from app.services.gold.strategy.paper_validator import PaperValidator
    
    validator = PaperValidator(db)
    result = validator.reset_validation(strategy_id, user.id)
    
    if "error" in result:
        status_code = 404 if "not found" in result["error"].lower() else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    
    return result
