"""Intelligence Brief Generator — produces daily/weekly/monthly summaries.

Queries MarketSnapshot, MarketRegime, positions, and stage transitions
to produce structured briefs that can be rendered in-app or sent via Brain webhook.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory, MarketRegime

logger = logging.getLogger(__name__)


def generate_daily_digest(db: Session, as_of: date | None = None) -> dict[str, Any]:
    """Produce the daily intelligence digest after the nightly pipeline."""
    today = as_of or date.today()
    yesterday = today - timedelta(days=1)

    regime = (
        db.query(MarketRegime)
        .filter(MarketRegime.as_of_date <= today)
        .order_by(MarketRegime.as_of_date.desc())
        .first()
    )
    prev_regime = (
        db.query(MarketRegime)
        .filter(MarketRegime.as_of_date < (regime.as_of_date if regime else today))
        .order_by(MarketRegime.as_of_date.desc())
        .first()
    )

    regime_section = _build_regime_section(regime, prev_regime)

    snapshots = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.analysis_type == "technical_snapshot")
        .all()
    )

    stage_transitions = _find_stage_transitions(snapshots)
    scan_changes = _find_scan_changes(snapshots)
    breadth = _compute_breadth(snapshots)
    stage_distribution = _compute_stage_distribution(snapshots)

    exit_alerts: list[dict] = []
    try:
        from backend.models.position import Position
        positions = db.query(Position).filter(Position.is_open.is_(True)).all()
        for pos in positions:
            snap = next((s for s in snapshots if s.symbol == pos.symbol), None)
            if snap and snap.stage_label and snap.stage_label.startswith(('3', '4')):
                exit_alerts.append({
                    "symbol": pos.symbol,
                    "stage": snap.stage_label,
                    "pnl_pct": _calc_pnl_pct(pos, snap),
                })
    except Exception as e:
        logger.warning("Could not compute exit alerts: %s", e)

    return {
        "type": "daily",
        "as_of": today.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regime": regime_section,
        "stage_transitions": stage_transitions,
        "scan_changes": scan_changes,
        "breadth": breadth,
        "stage_distribution": stage_distribution,
        "exit_alerts": exit_alerts,
        "snapshot_count": len(snapshots),
    }


def generate_weekly_brief(db: Session, as_of: date | None = None) -> dict[str, Any]:
    """Produce the weekly strategy brief (generated Sunday/Monday pre-market)."""
    today = as_of or date.today()
    week_ago = today - timedelta(days=7)

    regimes = (
        db.query(MarketRegime)
        .filter(MarketRegime.as_of_date >= week_ago)
        .order_by(MarketRegime.as_of_date.asc())
        .all()
    )
    regime_trend = [
        {"date": r.as_of_date.isoformat(), "state": r.regime_state, "score": float(r.composite_score or 0)}
        for r in regimes
    ]

    snapshots = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.analysis_type == "technical_snapshot")
        .all()
    )

    current_distribution = _compute_stage_distribution(snapshots)

    set1_entries = [
        {"symbol": s.symbol, "stage": s.stage_label, "scan_tier": s.scan_tier}
        for s in snapshots
        if s.scan_tier and "Set 1" in str(s.scan_tier)
    ]

    sector_analysis = _compute_sector_analysis(snapshots)

    top_picks = _compute_top_picks(snapshots)

    return {
        "type": "weekly",
        "as_of": today.isoformat(),
        "week_start": week_ago.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regime_trend": regime_trend,
        "stage_distribution": current_distribution,
        "set1_entries": set1_entries[:20],
        "sector_analysis": sector_analysis,
        "top_picks": top_picks,
        "snapshot_count": len(snapshots),
    }


def generate_monthly_review(db: Session, as_of: date | None = None) -> dict[str, Any]:
    """Produce the monthly/quarterly review."""
    today = as_of or date.today()
    month_ago = today - timedelta(days=30)

    regimes = (
        db.query(MarketRegime)
        .filter(MarketRegime.as_of_date >= month_ago)
        .order_by(MarketRegime.as_of_date.asc())
        .all()
    )

    regime_transitions = 0
    for i in range(1, len(regimes)):
        if regimes[i].regime_state != regimes[i - 1].regime_state:
            regime_transitions += 1

    regime_history = [
        {"date": r.as_of_date.isoformat(), "state": r.regime_state, "score": float(r.composite_score or 0)}
        for r in regimes
    ]

    snapshots = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.analysis_type == "technical_snapshot")
        .all()
    )

    performance_summary = _compute_performance_summary(snapshots)

    return {
        "type": "monthly",
        "as_of": today.isoformat(),
        "period_start": month_ago.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regime_history": regime_history,
        "regime_transitions": regime_transitions,
        "performance_summary": performance_summary,
        "snapshot_count": len(snapshots),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_regime_section(regime: MarketRegime | None, prev: MarketRegime | None) -> dict:
    if not regime:
        return {"state": "UNKNOWN", "score": 0, "changed": False}
    changed = prev is not None and prev.regime_state != regime.regime_state
    return {
        "state": regime.regime_state,
        "score": float(regime.composite_score or 0),
        "multiplier": float(regime.regime_multiplier or 1),
        "max_equity_pct": float(regime.max_equity_exposure_pct or 100),
        "cash_floor_pct": float(regime.cash_floor_pct or 0),
        "as_of": regime.as_of_date.isoformat() if regime.as_of_date else None,
        "changed": changed,
        "previous_state": prev.regime_state if prev else None,
        "vix_spot": float(regime.vix_spot) if regime.vix_spot else None,
        "vix3m_vix_ratio": float(regime.vix3m_vix_ratio) if regime.vix3m_vix_ratio else None,
        "nh_nl": int(regime.nh_nl) if regime.nh_nl else None,
        "pct_above_200d": float(regime.pct_above_200d) if regime.pct_above_200d else None,
        "pct_above_50d": float(regime.pct_above_50d) if regime.pct_above_50d else None,
    }


def _find_stage_transitions(snapshots: list) -> list[dict]:
    transitions = []
    for s in snapshots:
        prev = getattr(s, "previous_stage_label", None) or getattr(s, "prior_stage", None)
        curr = s.stage_label
        if prev and curr and prev != curr:
            transitions.append({
                "symbol": s.symbol,
                "from_stage": prev,
                "to_stage": curr,
                "days_in_stage": getattr(s, "current_stage_days", None),
            })
    return sorted(transitions, key=lambda x: x.get("to_stage", ""))


def _find_scan_changes(snapshots: list) -> list[dict]:
    changes = []
    for s in snapshots:
        if s.scan_tier and s.stage_label:
            tier_str = str(s.scan_tier)
            if "Set 1" in tier_str or "Short" in tier_str:
                changes.append({
                    "symbol": s.symbol,
                    "scan_tier": tier_str,
                    "stage": s.stage_label,
                    "action": getattr(s, "action_label", None),
                })
    return changes[:30]


def _compute_breadth(snapshots: list) -> dict:
    total = len(snapshots)
    if total == 0:
        return {"above_50d": 0, "above_200d": 0, "total": 0}
    above_50 = sum(1 for s in snapshots if s.sma_50 and s.current_price and s.current_price > s.sma_50)
    above_200 = sum(1 for s in snapshots if s.sma_200 and s.current_price and s.current_price > s.sma_200)
    return {
        "above_50d": above_50,
        "above_50d_pct": round(above_50 / total * 100, 1),
        "above_200d": above_200,
        "above_200d_pct": round(above_200 / total * 100, 1),
        "total": total,
    }


def _compute_stage_distribution(snapshots: list) -> dict[str, int]:
    dist: dict[str, int] = {}
    for s in snapshots:
        stage = s.stage_label or "unknown"
        dist[stage] = dist.get(stage, 0) + 1
    return dict(sorted(dist.items()))


def _compute_sector_analysis(snapshots: list) -> list[dict]:
    sectors: dict[str, list] = {}
    for s in snapshots:
        sector = getattr(s, "sector", None) or "Unknown"
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(s)

    result = []
    for sector, stocks in sectors.items():
        n = len(stocks)
        avg_rs = sum(getattr(s, "rs_mansfield_pct", 0) or 0 for s in stocks) / n if n else 0
        stage2_pct = sum(1 for s in stocks if s.stage_label and s.stage_label.startswith("2")) / n * 100 if n else 0
        result.append({
            "sector": sector,
            "count": n,
            "avg_rs": round(avg_rs, 2),
            "stage2_pct": round(stage2_pct, 0),
        })
    return sorted(result, key=lambda x: x["avg_rs"], reverse=True)


def _compute_top_picks(snapshots: list) -> dict:
    buy_list = [
        {"symbol": s.symbol, "stage": s.stage_label, "scan_tier": s.scan_tier}
        for s in snapshots
        if s.stage_label and s.stage_label.startswith("2") and s.scan_tier and "Set 1" in str(s.scan_tier)
    ]
    watch_list = [
        {"symbol": s.symbol, "stage": s.stage_label}
        for s in snapshots
        if s.stage_label in ("1B", "2A") and (getattr(s, "rs_mansfield_pct", 0) or 0) > 0
    ]
    short_list = [
        {"symbol": s.symbol, "stage": s.stage_label, "scan_tier": s.scan_tier}
        for s in snapshots
        if s.scan_tier and "Short" in str(s.scan_tier)
    ]
    return {
        "buy": buy_list[:10],
        "watch": watch_list[:15],
        "short": short_list[:10],
    }


def _compute_performance_summary(snapshots: list) -> dict:
    perfs = [s.perf_20d for s in snapshots if s.perf_20d is not None]
    if not perfs:
        return {"avg_20d": 0, "median_20d": 0, "best": [], "worst": []}
    perfs_sorted = sorted(perfs)
    median = perfs_sorted[len(perfs_sorted) // 2]

    best = sorted(snapshots, key=lambda s: s.perf_20d or 0, reverse=True)[:5]
    worst = sorted(snapshots, key=lambda s: s.perf_20d or 0)[:5]

    return {
        "avg_20d": round(sum(perfs) / len(perfs), 2),
        "median_20d": round(median, 2),
        "best": [{"symbol": s.symbol, "perf_20d": round(s.perf_20d or 0, 2)} for s in best],
        "worst": [{"symbol": s.symbol, "perf_20d": round(s.perf_20d or 0, 2)} for s in worst],
    }


def _calc_pnl_pct(pos: Any, snap: Any) -> float | None:
    entry = getattr(pos, "average_cost", None) or getattr(pos, "cost_basis", None)
    price = getattr(snap, "current_price", None)
    if entry and price and entry > 0:
        return round((price - entry) / entry * 100, 2)
    return None
