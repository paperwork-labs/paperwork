"""Strategy CRUD, composable rule evaluation, backtest, and template routes."""

from __future__ import annotations
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.models.strategy import Strategy, StrategyType, StrategyStatus
from backend.models.market_data import MarketSnapshot
from backend.services.strategy.rule_evaluator import (
    RuleEvaluator,
    ConditionGroup,
    Condition,
    ConditionOperator,
    LogicalOperator,
)
from backend.services.strategy.signal_generator import SignalGenerator
from backend.services.strategy.backtest_engine import BacktestEngine
from backend.services.strategy.templates import (
    get_template,
    list_templates as _list_templates,
    STRATEGY_TEMPLATES,
)
from backend.services.strategy.context_builder import snapshot_to_context

router = APIRouter()

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

def _strategy_to_dict(s: Strategy) -> Dict[str, Any]:
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
    return {"data": [_strategy_to_dict(s) for s in strategies]}


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
    return {"data": _strategy_to_dict(strategy)}


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
    return {"data": _strategy_to_dict(strategy)}


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
    return {"data": _strategy_to_dict(strategy)}


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

    if req.config is not None:
        strategy.parameters = req.config

    strategy.modified_by_user_id = user.id
    db.commit()
    db.refresh(strategy)
    return {"data": _strategy_to_dict(strategy)}


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

    return {
        "data": {
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
