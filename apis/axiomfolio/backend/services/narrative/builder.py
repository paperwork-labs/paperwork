"""Assemble structured portfolio facts and render LLM narrative with fallback.

medallion: gold
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from backend.models.broker_account import BrokerAccount
from backend.models.market_data import MarketSnapshotHistory
from backend.models.portfolio import PortfolioHistory
from backend.models.position import Position, PositionStatus
from backend.models.transaction import Dividend
from backend.services.market.regime_engine import get_regime_for_date
from backend.services.narrative.provider import (
    NarrativeProvider,
    NarrativeProviderError,
    NarrativeResult,
)
from backend.services.narrative.providers.fallback_template import render_from_summary

logger = logging.getLogger(__name__)

TECH_SNAPSHOT = "technical_snapshot"
MOVE_THRESHOLD_PCT = 2.0

_REGIME_LABELS: Dict[str, str] = {
    "R1": "R1 (Bull)",
    "R2": "R2 (Bull Extended)",
    "R3": "R3 (Chop)",
    "R4": "R4 (Bear Rally)",
    "R5": "R5 (Bear)",
}


def _regime_display(regime_state: Optional[str]) -> str:
    if not regime_state:
        return "unknown"
    return _REGIME_LABELS.get(regime_state, regime_state)


def build_portfolio_summary(db: Session, user_id: int, target_date: date) -> Dict[str, Any]:
    """Collect structured facts for the narrative. Best-effort: omits sections on failure."""
    summary: Dict[str, Any] = {
        "target_date": target_date.isoformat(),
        "top_movers": [],
        "n_movers_over_threshold": 0,
        "stage_transitions": [],
        "ex_dividends": [],
        "portfolio_return_pct": None,
        "spy_return_pct": None,
        "regime": None,
        "regime_state": None,
        "data_gaps": [],
    }

    try:
        positions = (
            db.query(Position)
            .filter(
                Position.user_id == user_id,
                Position.status == PositionStatus.OPEN,
                Position.instrument_type == "STOCK",
            )
            .all()
        )
    except Exception as e:
        logger.warning("narrative: positions query failed for user %s: %s", user_id, e)
        summary["data_gaps"].append("positions_unavailable")
        return summary

    symbols = sorted({p.symbol for p in positions if p.symbol})
    if not symbols:
        summary["data_gaps"].append("no_open_stock_positions")
        return summary

    movers: List[Dict[str, Any]] = []
    for p in positions:
        pct = p.day_pnl_pct
        if pct is None:
            continue
        try:
            fv = float(pct)
        except (TypeError, ValueError):
            continue
        movers.append({"symbol": p.symbol, "day_pnl_pct": round(fv, 4)})
    movers.sort(key=lambda x: abs(x["day_pnl_pct"]), reverse=True)
    summary["top_movers"] = movers[:3]
    summary["n_movers_over_threshold"] = sum(
        1 for m in movers if abs(m["day_pnl_pct"]) >= MOVE_THRESHOLD_PCT
    )

    transitions: List[Dict[str, Any]] = []
    try:
        latest_today_sq = (
            db.query(
                MarketSnapshotHistory.symbol.label("sym"),
                func.max(MarketSnapshotHistory.as_of_date).label("max_as_of"),
            )
            .filter(
                MarketSnapshotHistory.symbol.in_(symbols),
                MarketSnapshotHistory.analysis_type == TECH_SNAPSHOT,
                func.date(MarketSnapshotHistory.as_of_date) == target_date,
            )
            .group_by(MarketSnapshotHistory.symbol)
            .subquery()
        )
        today_rows = (
            db.query(MarketSnapshotHistory)
            .join(
                latest_today_sq,
                and_(
                    MarketSnapshotHistory.symbol == latest_today_sq.c.sym,
                    MarketSnapshotHistory.as_of_date == latest_today_sq.c.max_as_of,
                    MarketSnapshotHistory.analysis_type == TECH_SNAPSHOT,
                ),
            )
            .all()
        )
        latest_prev_sq = (
            db.query(
                MarketSnapshotHistory.symbol.label("sym"),
                func.max(MarketSnapshotHistory.as_of_date).label("max_as_of"),
            )
            .filter(
                MarketSnapshotHistory.symbol.in_(symbols),
                MarketSnapshotHistory.analysis_type == TECH_SNAPSHOT,
                func.date(MarketSnapshotHistory.as_of_date) < target_date,
            )
            .group_by(MarketSnapshotHistory.symbol)
            .subquery()
        )
        prev_rows = (
            db.query(MarketSnapshotHistory)
            .join(
                latest_prev_sq,
                and_(
                    MarketSnapshotHistory.symbol == latest_prev_sq.c.sym,
                    MarketSnapshotHistory.as_of_date == latest_prev_sq.c.max_as_of,
                    MarketSnapshotHistory.analysis_type == TECH_SNAPSHOT,
                ),
            )
            .all()
        )
        today_by = {r.symbol: r for r in today_rows}
        prev_by = {r.symbol: r for r in prev_rows}
        for sym in symbols:
            today_row = today_by.get(sym)
            prev_row = prev_by.get(sym)
            if not today_row or not prev_row:
                continue
            t_stage = today_row.stage_label
            p_stage = prev_row.stage_label
            if not t_stage or not p_stage or t_stage == p_stage:
                continue
            vol_ratio = today_row.vol_ratio
            transitions.append(
                {
                    "symbol": sym,
                    "from": p_stage,
                    "to": t_stage,
                    "vol_ratio": float(vol_ratio) if vol_ratio is not None else None,
                }
            )
    except Exception as e:
        logger.warning("narrative: batched stage history failed: %s", e)
        summary["data_gaps"].append("stage_history_unavailable")
    summary["stage_transitions"] = transitions[:8]

    try:
        ex_rows = (
            db.query(Dividend)
            .join(BrokerAccount, Dividend.account_id == BrokerAccount.id)
            .filter(
                BrokerAccount.user_id == user_id,
                func.date(Dividend.ex_date) == target_date,
                Dividend.symbol.in_(symbols),
            )
            .all()
        )
        summary["ex_dividends"] = [
            {
                "symbol": d.symbol,
                "dividend_per_share": float(d.dividend_per_share)
                if d.dividend_per_share is not None
                else None,
            }
            for d in ex_rows
        ]
    except Exception as e:
        logger.warning("narrative: ex-div query failed for user %s: %s", user_id, e)
        summary["data_gaps"].append("ex_dividends_unavailable")

    try:
        sum_today = (
            db.query(func.coalesce(func.sum(PortfolioHistory.total_value), 0))
            .filter(
                PortfolioHistory.user_id == user_id,
                PortfolioHistory.as_of_date == target_date,
            )
            .scalar()
        )
        prev_date = (
            db.query(func.max(PortfolioHistory.as_of_date))
            .filter(
                PortfolioHistory.user_id == user_id,
                PortfolioHistory.as_of_date < target_date,
            )
            .scalar()
        )
        if prev_date is not None:
            sum_prev = (
                db.query(func.coalesce(func.sum(PortfolioHistory.total_value), 0))
                .filter(
                    PortfolioHistory.user_id == user_id,
                    PortfolioHistory.as_of_date == prev_date,
                )
                .scalar()
            )
            if sum_prev and Decimal(str(sum_prev)) > 0 and sum_today is not None:
                s0 = Decimal(str(sum_prev))
                s1 = Decimal(str(sum_today))
                summary["portfolio_return_pct"] = float(((s1 - s0) / s0) * 100)
        else:
            summary["data_gaps"].append("portfolio_history_no_prior_date")
    except Exception as e:
        logger.warning("narrative: portfolio history failed for user %s: %s", user_id, e)
        summary["data_gaps"].append("portfolio_history_unavailable")

    try:
        spy_row = (
            db.query(MarketSnapshotHistory)
            .filter(
                MarketSnapshotHistory.symbol == "SPY",
                MarketSnapshotHistory.analysis_type == TECH_SNAPSHOT,
                func.date(MarketSnapshotHistory.as_of_date) == target_date,
            )
            .order_by(MarketSnapshotHistory.as_of_date.desc())
            .first()
        )
        if spy_row and spy_row.perf_1d is not None:
            summary["spy_return_pct"] = float(spy_row.perf_1d)
        else:
            summary["data_gaps"].append("spy_perf_missing")
    except Exception as e:
        logger.warning("narrative: SPY perf lookup failed: %s", e)
        summary["data_gaps"].append("spy_perf_unavailable")

    try:
        row = get_regime_for_date(db, target_date)
        if row is None:
            summary["data_gaps"].append("regime_missing_for_date")
        else:
            summary["regime_state"] = row.regime_state
            summary["regime"] = _regime_display(row.regime_state)
    except Exception as e:
        logger.warning("narrative: regime lookup failed for %s: %s", target_date, e)
        summary["data_gaps"].append("regime_unavailable")

    return summary


NARRATIVE_USER_PROMPT = """You are AxiomFolio's portfolio analyst. Summarize today's portfolio activity for the user in 3-4 short sentences. Be specific with tickers and numbers; do NOT use marketing language. Use US date format. Today's data:

Top movers: {top_movers_json}
Stage transitions: {stage_transitions_json}
Ex-dividends today: {ex_div_json}
Portfolio return: {portfolio_pct} vs SPY {spy_pct}
Macro regime: {regime}

Output: a single paragraph, markdown allowed for emphasis. No headers."""


def build_narrative_prompt(summary: Dict[str, Any]) -> str:
    def _fmt_pct(key: str) -> str:
        v = summary.get(key)
        if v is None:
            return "n/a"
        return f"{float(v):+.2f}%"

    return NARRATIVE_USER_PROMPT.format(
        top_movers_json=json.dumps(summary.get("top_movers") or [], sort_keys=True),
        stage_transitions_json=json.dumps(summary.get("stage_transitions") or [], sort_keys=True),
        ex_div_json=json.dumps(summary.get("ex_dividends") or [], sort_keys=True),
        portfolio_pct=_fmt_pct("portfolio_return_pct"),
        spy_pct=_fmt_pct("spy_return_pct"),
        regime=str(summary.get("regime") or summary.get("regime_state") or "unknown"),
    )


def render_narrative(summary: Dict[str, Any], provider: NarrativeProvider) -> NarrativeResult:
    """Call LLM; on failure return template-based :class:`NarrativeResult` (never raises)."""
    prompt = build_narrative_prompt(summary)
    try:
        return provider.generate(prompt, max_tokens=400)
    except NarrativeProviderError as e:
        logger.warning("narrative: provider failed, using template fallback: %s", e)
        fb = render_from_summary(summary)
        return NarrativeResult(
            text=fb.text,
            provider=fb.provider,
            model=fb.model,
            tokens_used=fb.tokens_used,
            cost_usd=fb.cost_usd,
            is_fallback=True,
            prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("narrative: unexpected provider error: %s", e)
        fb = render_from_summary(summary)
        return NarrativeResult(
            text=fb.text,
            provider=fb.provider,
            model=fb.model,
            tokens_used=fb.tokens_used,
            cost_usd=fb.cost_usd,
            is_fallback=True,
            prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        )
