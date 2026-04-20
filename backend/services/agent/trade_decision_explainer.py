"""
Trade Decision Explainer service.

For every executed order this service builds a structured "why was this
trade taken" explanation:

* trigger          -- pick / scan / rebalance / manual / strategy / unknown
* rationale        -- bullets grounded in the snapshot / lineage at order time
* risk_context     -- size, stop, regime alignment
* outcome_so_far   -- realized P&L if closed, current state if open
* narrative        -- 2-4 paragraph markdown for the drawer

It is **read-only**: it never mutates Order / Trade / Position rows. It
joins to the linked ValidatedPick / TradeSignal / Strategy when present,
and pulls the most recent ``MarketSnapshot`` for the symbol that was
already computed before the order timestamp (a strict "<= " filter
guarantees we don't peek at indicators that didn't exist yet).

Caching contract
----------------

Calling :meth:`TradeDecisionExplainer.explain` for an order that already
has a persisted explanation returns the cached row -- no LLM cost on the
second hit. To force a regenerate, call
:meth:`TradeDecisionExplainer.regenerate`, which writes a new row with
``version = previous_version + 1``.

LLM gateway integration
-----------------------

If a future ``backend/services/agent/llm_gateway.py`` lands with a
constitution-enforced budget cap, swap :func:`_build_provider` to route
through it. Today the explainer reuses the same
:class:`OpenAIChatProvider` and :class:`StubLLMProvider` machinery the
AnomalyExplainer uses, so the budget pattern is identical (per-call
``max_tokens`` cap, fail-closed when ``OPENAI_API_KEY`` is absent).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models import (
    MarketRegime,
    MarketSnapshot,
    Order,
    PickEngagement,
    Strategy,
    Trade,
    TradeDecisionExplanation,
    TradeSignal,
    ValidatedPick,
)
from backend.services.agent.anomaly_explainer.openai_provider import (
    OpenAIChatProvider,
)
from backend.services.agent.anomaly_explainer.provider import (
    LLMProvider,
    LLMProviderError,
    StubLLMProvider,
)
from backend.services.agent.explanation_prompts import (
    OUTPUT_JSON_SCHEMA,
    SCHEMA_VERSION,
    SYSTEM_PROMPT,
    TRIGGER_TYPES,
    build_user_prompt,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Errors
# -----------------------------------------------------------------------------


class TradeDecisionExplainerError(RuntimeError):
    """Raised for non-recoverable failures (missing order, cross-tenant access).

    LLM-side failures are caught internally and surface as a persisted
    fallback row -- the caller never sees a provider exception.
    """


class OrderNotFoundError(TradeDecisionExplainerError):
    """Raised when the requested order does not exist or is not owned by
    the requesting user."""


# -----------------------------------------------------------------------------
# Result wire shape
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ExplainerResult:
    """Returned by :meth:`TradeDecisionExplainer.explain`.

    ``reused`` is ``True`` when the cached row was returned and ``False``
    when a fresh LLM call (or fallback) produced a new row.
    """

    row_id: int
    order_id: int
    user_id: int
    version: int
    trigger_type: str
    schema_version: str
    model_used: str
    is_fallback: bool
    cost_usd: Decimal
    prompt_token_count: int
    completion_token_count: int
    payload: Dict[str, Any]
    narrative: str
    generated_at: datetime
    reused: bool


# -----------------------------------------------------------------------------
# Internal: lineage + snapshot context builders (no LLM yet)
# -----------------------------------------------------------------------------


@dataclass
class _OrderContext:
    order: Order
    trade: Optional[Trade]
    trigger_type: str
    pick: Optional[ValidatedPick]
    signal: Optional[TradeSignal]
    strategy: Optional[Strategy]
    market_snapshot: Optional[MarketSnapshot]
    market_regime: Optional[MarketRegime]
    extras: Dict[str, Any] = field(default_factory=dict)


def _resolve_trigger_type(
    *,
    order: Order,
    pick: Optional[ValidatedPick],
    signal: Optional[TradeSignal],
    strategy: Optional[Strategy],
) -> str:
    """Pick exactly one trigger label for the order.

    Order of precedence (from most specific to least):
        pick > scan (signal w/ no strategy) > strategy > rebalance >
        manual > unknown.

    A pick promoted from a scan candidate counts as ``pick`` because
    that's the more meaningful provenance from the user's perspective
    (someone validated it).
    """
    if pick is not None:
        return "pick"
    source = (order.source or "").lower()
    if source == "rebalance":
        return "rebalance"
    if strategy is not None:
        return "strategy"
    if signal is not None:
        return "scan"
    if source == "strategy":
        return "strategy"
    if source == "manual":
        return "manual"
    return "unknown"


def _try_load_pick_from_engagements(
    db: Session, *, user_id: int, symbol: str, before: Optional[datetime]
) -> Optional[ValidatedPick]:
    """Find the most recent EXECUTED PickEngagement for this user/symbol.

    There is no FK from ``Order`` to ``ValidatedPick`` today; the
    engagement table records when a user executed a pick. We use the
    most recent ``executed`` engagement on this symbol whose
    ``occurred_at`` is on or before the order timestamp as a
    best-effort link.
    """
    if not symbol:
        return None
    q = (
        db.query(ValidatedPick)
        .join(PickEngagement, PickEngagement.pick_id == ValidatedPick.id)
        .filter(
            PickEngagement.user_id == user_id,
            PickEngagement.engagement_type.in_(("executed", "partial_executed")),
            ValidatedPick.symbol == symbol,
        )
    )
    if before is not None:
        q = q.filter(PickEngagement.occurred_at <= before)
    return q.order_by(desc(PickEngagement.occurred_at)).first()


def _load_snapshot_at_or_before(
    db: Session, *, symbol: str, at: Optional[datetime]
) -> Optional[MarketSnapshot]:
    """Most recent ``technical_snapshot`` whose ``as_of_timestamp`` is on
    or before ``at`` (defensive against intraday / future timestamps)."""
    q = db.query(MarketSnapshot).filter(
        MarketSnapshot.symbol == symbol,
        MarketSnapshot.analysis_type == "technical_snapshot",
    )
    if at is not None:
        # Some snapshots may have a NULL as_of_timestamp; we only consider
        # rows we can date-bound.
        q = q.filter(MarketSnapshot.as_of_timestamp.isnot(None))
        q = q.filter(MarketSnapshot.as_of_timestamp <= at)
        q = q.order_by(desc(MarketSnapshot.as_of_timestamp))
    else:
        q = q.order_by(desc(MarketSnapshot.analysis_timestamp))
    return q.first()


def _load_regime_at_or_before(
    db: Session, *, at: Optional[datetime]
) -> Optional[MarketRegime]:
    q = db.query(MarketRegime)
    if at is not None:
        q = q.filter(MarketRegime.as_of_date <= at)
    return q.order_by(desc(MarketRegime.as_of_date)).first()


def _order_timestamp(order: Order) -> Optional[datetime]:
    """Best date to anchor "context at order time" lookups."""
    return order.filled_at or order.submitted_at or order.created_at


def build_order_context(db: Session, *, order: Order) -> _OrderContext:
    """Assemble everything the explainer needs for one order.

    Pure orchestration; no LLM calls. Exposed for tests.
    """
    at = _order_timestamp(order)

    signal: Optional[TradeSignal] = None
    if order.signal_id is not None:
        signal = (
            db.query(TradeSignal)
            .filter(TradeSignal.id == order.signal_id)
            .one_or_none()
        )

    strategy: Optional[Strategy] = None
    if order.strategy_id is not None:
        strategy = (
            db.query(Strategy)
            .filter(Strategy.id == order.strategy_id)
            .one_or_none()
        )

    pick: Optional[ValidatedPick] = None
    if order.user_id is not None:
        pick = _try_load_pick_from_engagements(
            db, user_id=order.user_id, symbol=order.symbol, before=at
        )

    snapshot = _load_snapshot_at_or_before(db, symbol=order.symbol, at=at)
    regime = _load_regime_at_or_before(db, at=at)

    trigger_type = _resolve_trigger_type(
        order=order, pick=pick, signal=signal, strategy=strategy
    )

    trade = (
        db.query(Trade)
        .filter(Trade.order_id == str(order.broker_order_id or ""))
        .order_by(desc(Trade.execution_time))
        .first()
        if order.broker_order_id
        else None
    )

    return _OrderContext(
        order=order,
        trade=trade,
        trigger_type=trigger_type,
        pick=pick,
        signal=signal,
        strategy=strategy,
        market_snapshot=snapshot,
        market_regime=regime,
    )


# -----------------------------------------------------------------------------
# Internal: LLM payload serializers
# -----------------------------------------------------------------------------


def _json_prompt_scalar(value: Optional[Any]) -> Optional[Any]:
    """Serialize numeric order fields for JSON blocks in the LLM user prompt.

    Never cast :class:`Decimal` to ``float`` (monetary iron law). Decimals are
    emitted as strings so values stay exact in the serialized prompt.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    return value


def _as_decimal(value: Any) -> Optional[Decimal]:
    """Coerce ORM numeric (float or Decimal) to Decimal for safe arithmetic."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _order_payload(order: Order, trade: Optional[Trade]) -> Dict[str, Any]:
    return {
        "order_id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "order_type": order.order_type,
        "status": order.status,
        "quantity": _json_prompt_scalar(order.quantity),
        "limit_price": _json_prompt_scalar(order.limit_price),
        "stop_price": _json_prompt_scalar(order.stop_price),
        "filled_quantity": _json_prompt_scalar(order.filled_quantity),
        "filled_avg_price": _json_prompt_scalar(order.filled_avg_price),
        "broker_type": order.broker_type,
        "source": order.source,
        "submitted_at": order.submitted_at.isoformat()
        if order.submitted_at
        else None,
        "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "decision_price": _json_prompt_scalar(order.decision_price),
        "estimated_commission": _json_prompt_scalar(order.estimated_commission),
        "trade_id": trade.id if trade is not None else None,
        "trade_execution_time": trade.execution_time.isoformat()
        if (trade is not None and trade.execution_time)
        else None,
    }


def _lineage_payload(ctx: _OrderContext) -> Dict[str, Any]:
    out: Dict[str, Any] = {"trigger_type": ctx.trigger_type}
    if ctx.pick is not None:
        p = ctx.pick
        out["pick"] = {
            "id": p.id,
            "symbol": p.symbol,
            "action": getattr(p.action, "value", str(p.action)),
            "conviction": p.conviction,
            "validator_pseudonym": p.validator_pseudonym,
            "reason_summary": p.reason_summary,
            "suggested_entry": str(p.suggested_entry)
            if p.suggested_entry is not None
            else None,
            "suggested_stop": str(p.suggested_stop)
            if p.suggested_stop is not None
            else None,
            "suggested_target": str(p.suggested_target)
            if p.suggested_target is not None
            else None,
            "published_at": p.published_at.isoformat()
            if p.published_at
            else None,
        }
    if ctx.signal is not None:
        s = ctx.signal
        out["signal"] = {
            "id": s.id,
            "symbol": s.symbol,
            "signal_type": s.signal_type,
            "strategy_name": s.strategy_name,
            "signal_strength": s.signal_strength,
            "trigger_price": str(s.trigger_price)
            if s.trigger_price is not None
            else None,
            "stop_loss": str(s.stop_loss) if s.stop_loss is not None else None,
            "target_price": str(s.target_price)
            if s.target_price is not None
            else None,
            "rsi": s.rsi,
            "adx": s.adx,
            "atr_value": s.atr_value,
            "risk_reward_ratio": s.risk_reward_ratio,
        }
    if ctx.strategy is not None:
        st = ctx.strategy
        out["strategy"] = {
            "id": st.id,
            "name": getattr(st, "name", None),
            "description": getattr(st, "description", None),
        }
    return out


def _market_snapshot_payload(ctx: _OrderContext) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    snap = ctx.market_snapshot
    if snap is not None:
        out["snapshot"] = {
            "as_of_timestamp": snap.as_of_timestamp.isoformat()
            if snap.as_of_timestamp
            else None,
            "current_price": snap.current_price,
            "stage_label": snap.stage_label,
            "rsi": snap.rsi,
            "atr_value": snap.atr_value,
            "atr_percent": snap.atr_percent,
            "sma_50": snap.sma_50,
            "sma_150": snap.sma_150,
            "sma_200": snap.sma_200,
            "macd": snap.macd,
            "adx": snap.adx,
            "rs_mansfield_pct": snap.rs_mansfield_pct,
            "high_52w": snap.high_52w,
            "low_52w": snap.low_52w,
        }
    regime = ctx.market_regime
    if regime is not None:
        out["regime"] = {
            "as_of_date": regime.as_of_date.isoformat()
            if regime.as_of_date
            else None,
            "regime_state": regime.regime_state,
            "composite_score": regime.composite_score,
            "regime_multiplier": regime.regime_multiplier,
            "max_equity_exposure_pct": regime.max_equity_exposure_pct,
        }
    return out


def _outcome_payload(ctx: _OrderContext) -> Dict[str, Any]:
    """Compute outcome-so-far context.

    For a closed/realized order we surface ``realized_pnl``. For an open
    position we surface the entry vs current snapshot price as a
    gross-only delta -- the explainer is told (via the prompt) to label
    this as 'open' so the LLM doesn't claim profit certainty.
    """
    o = ctx.order
    snap = ctx.market_snapshot
    out: Dict[str, Any] = {}
    realized_raw = getattr(o, "realized_pnl", None)
    if realized_raw is not None:
        out["status"] = "closed"
        out["realized_pnl_usd"] = _json_prompt_scalar(realized_raw)
        return out
    fill = _as_decimal(o.filled_avg_price)
    current = (
        _as_decimal(snap.current_price)
        if (snap is not None and snap.current_price is not None)
        else None
    )
    qty = _as_decimal(o.quantity)
    if fill is not None and current is not None and qty and qty != 0:
        sign = Decimal(1) if str(o.side).lower() == "buy" else Decimal(-1)
        unrealized = sign * (current - fill) * qty
        out["status"] = "open"
        out["entry_price"] = str(fill)
        out["last_known_price"] = str(current)
        out["unrealized_delta_usd"] = str(unrealized)
        return out
    out["status"] = "unknown"
    return out


# -----------------------------------------------------------------------------
# LLM result validation
# -----------------------------------------------------------------------------


class _MalformedLLMOutput(ValueError):
    """Internal signal that the LLM payload didn't pass our schema gate."""


def _validate_payload(raw: str) -> Dict[str, Any]:
    if not raw or not raw.strip():
        raise _MalformedLLMOutput("empty response")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise _MalformedLLMOutput(f"invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise _MalformedLLMOutput("top-level value is not an object")
    required = OUTPUT_JSON_SCHEMA["required"]
    for key in required:
        if key not in payload:
            raise _MalformedLLMOutput(f"missing required field: {key}")
    trigger = payload.get("trigger")
    if trigger not in TRIGGER_TYPES:
        raise _MalformedLLMOutput(f"invalid trigger value: {trigger!r}")
    bullets = payload.get("rationale_bullets")
    if not isinstance(bullets, list) or not bullets:
        raise _MalformedLLMOutput("rationale_bullets must be a non-empty list")
    if not isinstance(payload.get("risk_context"), dict):
        raise _MalformedLLMOutput("risk_context must be an object")
    if not isinstance(payload.get("outcome_so_far"), dict):
        raise _MalformedLLMOutput("outcome_so_far must be an object")
    return payload


def _coerce_decimal_cost(value: Any) -> Decimal:
    """Best-effort coerce a raw token cost into Numeric(10, 6)."""
    if value is None:
        return Decimal("0")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
    if d < 0:
        return Decimal("0")
    return d.quantize(Decimal("0.000001"))


# -----------------------------------------------------------------------------
# Provider construction
# -----------------------------------------------------------------------------


def _build_provider() -> LLMProvider:
    """Pick the best available LLM provider based on env config.

    LLM gateway integration: when
    ``backend/services/agent/llm_gateway.py`` lands with a
    constitution-enforced budget cap, replace this function so the
    provider routes through the gateway. The interface
    (``complete_json(system_prompt, user_prompt)``) stays identical.
    """
    try:
        from backend.config import settings
    except ImportError:
        return StubLLMProvider(
            [
                json.dumps(_DETERMINISTIC_FALLBACK_PAYLOAD),
            ]
        )

    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        return StubLLMProvider(
            [
                json.dumps(_DETERMINISTIC_FALLBACK_PAYLOAD),
            ]
        )
    model = (
        getattr(settings, "TRADE_DECISION_EXPLAINER_MODEL", None)
        or getattr(settings, "OPENAI_MODEL", None)
        or "gpt-4o-mini"
    )
    try:
        return OpenAIChatProvider(api_key=api_key, model=model)
    except Exception as exc:  # noqa: BLE001 -- degrade, don't crash
        logger.warning(
            "trade_decision_explainer: failed to construct OpenAIChatProvider "
            "(%s); falling back to StubLLMProvider.",
            exc,
        )
        return StubLLMProvider(
            [
                json.dumps(_DETERMINISTIC_FALLBACK_PAYLOAD),
            ]
        )


_DETERMINISTIC_FALLBACK_PAYLOAD: Dict[str, Any] = {
    "trigger": "unknown",
    "headline": "Trade decision explainer unavailable",
    "rationale_bullets": [
        "LLM gateway is not configured for this environment.",
        "Re-running the explainer once OPENAI_API_KEY is present (or the "
        "LLM gateway has been wired) will produce a grounded explanation.",
    ],
    "risk_context": {
        "position_size_label": "not analyzed",
        "stop_placement": "not analyzed",
        "regime_alignment": "not analyzed",
    },
    "outcome_so_far": {
        "status": "unknown",
        "summary": "Outcome lookup deferred until the LLM gateway is configured.",
    },
    "narrative": (
        "The Trade Decision Explainer was invoked without an LLM "
        "provider. This row is a deterministic fallback so the UI can "
        "render a degraded state. Re-run the regenerate endpoint after "
        "the explainer's provider is configured to obtain a grounded "
        "explanation."
    ),
}


# -----------------------------------------------------------------------------
# Service
# -----------------------------------------------------------------------------


class TradeDecisionExplainer:
    """Stateless service. Construct once per request / task and call."""

    SCHEMA_VERSION = SCHEMA_VERSION

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider: LLMProvider = provider or _build_provider()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def explain(
        self, db: Session, *, order_id: int, user_id: int
    ) -> ExplainerResult:
        """Return the (cached or freshly generated) explanation."""
        cached = _latest_explanation(db, order_id=order_id, user_id=user_id)
        if cached is not None:
            return _row_to_result(cached, reused=True)
        return self._generate_and_persist(
            db, order_id=order_id, user_id=user_id, force_new_version=False
        )

    def regenerate(
        self, db: Session, *, order_id: int, user_id: int
    ) -> ExplainerResult:
        """Force a new explanation row with ``version = previous + 1``."""
        return self._generate_and_persist(
            db, order_id=order_id, user_id=user_id, force_new_version=True
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _generate_and_persist(
        self,
        db: Session,
        *,
        order_id: int,
        user_id: int,
        force_new_version: bool,
    ) -> ExplainerResult:
        order = (
            db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .one_or_none()
        )
        if order is None:
            raise OrderNotFoundError(
                f"Order id={order_id} not found for user_id={user_id}"
            )

        ctx = build_order_context(db, order=order)
        order_payload = _order_payload(ctx.order, ctx.trade)
        lineage_payload = _lineage_payload(ctx)
        snapshot_payload = _market_snapshot_payload(ctx)
        outcome_payload = _outcome_payload(ctx)

        user_prompt = build_user_prompt(
            trigger_type=ctx.trigger_type,
            order_payload=order_payload,
            lineage_payload=lineage_payload,
            market_snapshot_payload=snapshot_payload,
            outcome_payload=outcome_payload,
        )

        is_fallback = False
        try:
            raw = self.provider.complete_json(SYSTEM_PROMPT, user_prompt)
            payload = _validate_payload(raw)
            narrative = str(payload.get("narrative") or "").strip()
            if not narrative:
                raise _MalformedLLMOutput("narrative empty after parse")
        except (LLMProviderError, _MalformedLLMOutput) as e:
            logger.warning(
                "trade_decision_explainer: provider %s failed for order=%s: %s",
                self.provider.name,
                order_id,
                e,
            )
            payload, narrative = _fallback_for(ctx)
            is_fallback = True
        except Exception as e:  # noqa: BLE001 -- belt-and-suspenders
            logger.exception(
                "trade_decision_explainer: unexpected error for order=%s: %s",
                order_id,
                e,
            )
            payload, narrative = _fallback_for(ctx)
            is_fallback = True

        # Force the trigger field to reflect the lineage we resolved
        # locally; we do not let the LLM rewrite our audit-derived label.
        payload["trigger"] = ctx.trigger_type

        prev_version = _max_version(db, order_id=order_id)
        next_version = prev_version + 1 if force_new_version else max(1, prev_version + 1)
        # If no cached row existed and we're not forcing, version starts at 1.
        if not force_new_version and prev_version == 0:
            next_version = 1

        # Token / cost telemetry: providers don't surface this through
        # the abstract Protocol today; we record zeros so downstream
        # cost analytics doesn't crash, and leave a TODO marker for the
        # gateway integration to populate.
        prompt_tokens = 0
        completion_tokens = 0
        cost_usd = Decimal("0")

        row = TradeDecisionExplanation(
            user_id=user_id,
            order_id=order_id,
            trade_id=ctx.trade.id if ctx.trade is not None else None,
            schema_version=SCHEMA_VERSION,
            version=next_version,
            trigger_type=ctx.trigger_type,
            model_used=self.provider.name[:64],
            prompt_token_count=prompt_tokens,
            completion_token_count=completion_tokens,
            cost_usd=_coerce_decimal_cost(cost_usd),
            is_fallback=is_fallback,
            payload_json=payload,
            narrative=narrative[:4000],
            generated_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()
        logger.info(
            "trade_decision_explanation persisted id=%s order_id=%s version=%s "
            "trigger=%s model=%s fallback=%s",
            row.id,
            row.order_id,
            row.version,
            row.trigger_type,
            row.model_used,
            row.is_fallback,
        )
        return _row_to_result(row, reused=False)


# -----------------------------------------------------------------------------
# Helpers (queries + serialization)
# -----------------------------------------------------------------------------


def _latest_explanation(
    db: Session, *, order_id: int, user_id: int
) -> Optional[TradeDecisionExplanation]:
    return (
        db.query(TradeDecisionExplanation)
        .filter(
            TradeDecisionExplanation.order_id == order_id,
            TradeDecisionExplanation.user_id == user_id,
        )
        .order_by(desc(TradeDecisionExplanation.version))
        .first()
    )


def _max_version(db: Session, *, order_id: int) -> int:
    row = (
        db.query(TradeDecisionExplanation)
        .filter(TradeDecisionExplanation.order_id == order_id)
        .order_by(desc(TradeDecisionExplanation.version))
        .first()
    )
    if row is None:
        return 0
    return int(row.version or 0)


def _row_to_result(
    row: TradeDecisionExplanation, *, reused: bool
) -> ExplainerResult:
    return ExplainerResult(
        row_id=row.id,
        order_id=row.order_id,
        user_id=row.user_id,
        version=row.version,
        trigger_type=row.trigger_type,
        schema_version=row.schema_version,
        model_used=row.model_used,
        is_fallback=bool(row.is_fallback),
        cost_usd=Decimal(str(row.cost_usd)) if row.cost_usd is not None else Decimal("0"),
        prompt_token_count=int(row.prompt_token_count or 0),
        completion_token_count=int(row.completion_token_count or 0),
        payload=dict(row.payload_json or {}),
        narrative=row.narrative or "",
        generated_at=row.generated_at,
        reused=reused,
    )


def explainer_result_to_dict(result: ExplainerResult) -> Dict[str, Any]:
    """Centralized API serializer (Decimal -> str, datetime -> ISO)."""
    return {
        "row_id": result.row_id,
        "order_id": result.order_id,
        "user_id": result.user_id,
        "version": result.version,
        "trigger_type": result.trigger_type,
        "schema_version": result.schema_version,
        "model_used": result.model_used,
        "is_fallback": result.is_fallback,
        "cost_usd": str(result.cost_usd),
        "prompt_token_count": result.prompt_token_count,
        "completion_token_count": result.completion_token_count,
        "payload": result.payload,
        "narrative": result.narrative,
        "generated_at": result.generated_at.isoformat()
        if result.generated_at
        else None,
        "reused": result.reused,
    }


def _fallback_for(ctx: _OrderContext) -> tuple[Dict[str, Any], str]:
    """Return a deterministic-fallback payload + narrative for ``ctx``.

    Used when the LLM provider failed or returned malformed output. The
    payload still satisfies the schema gate and is honest about the
    degradation -- the persisted row sets ``is_fallback=True`` so the UI
    can show a "degraded" badge (no silent fallback).
    """
    payload: Dict[str, Any] = dict(_DETERMINISTIC_FALLBACK_PAYLOAD)
    payload["trigger"] = ctx.trigger_type
    bullets: List[str] = []
    bullets.append(
        f"Order {ctx.order.symbol} {ctx.order.side} qty="
        f"{ctx.order.quantity} (status={ctx.order.status})."
    )
    if ctx.pick is not None:
        bullets.append(
            f"Linked validated pick (id={ctx.pick.id}, conviction="
            f"{ctx.pick.conviction}): {ctx.pick.reason_summary}."
        )
    if ctx.signal is not None:
        bullets.append(
            f"Linked scanner signal (id={ctx.signal.id}, type="
            f"{ctx.signal.signal_type}, strategy={ctx.signal.strategy_name})."
        )
    if ctx.market_snapshot is not None:
        snap = ctx.market_snapshot
        bullets.append(
            f"Snapshot at {snap.as_of_timestamp}: stage="
            f"{snap.stage_label}, RSI={snap.rsi}, ATR%={snap.atr_percent}."
        )
    if ctx.market_regime is not None:
        bullets.append(
            f"Regime {ctx.market_regime.regime_state} on "
            f"{ctx.market_regime.as_of_date} (composite="
            f"{ctx.market_regime.composite_score})."
        )
    payload["rationale_bullets"] = bullets or payload["rationale_bullets"]
    narrative = (
        "The Trade Decision Explainer is currently in degraded mode for "
        "this order. The bullets above were assembled directly from the "
        "audit trail without an LLM call. Re-run the regenerate endpoint "
        "once the LLM provider is healthy to produce a grounded, "
        "narrative-quality explanation."
    )
    return payload, narrative


__all__ = [
    "ExplainerResult",
    "OrderNotFoundError",
    "SCHEMA_VERSION",
    "TradeDecisionExplainer",
    "TradeDecisionExplainerError",
    "build_order_context",
    "explainer_result_to_dict",
]
