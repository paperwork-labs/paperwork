"""medallion: silver"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypeVar

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, load_only

from app.models.market_data import MarketSnapshot, MarketSnapshotHistory
from app.models.market_tracked_plan import MarketTrackedPlan
from app.models import Position
from app.services.silver.math.constants import (
    SECTOR_ETF_DISPLAY_NAMES,
    SECTOR_ETF_PROXY_SYMBOLS,
    SECTOR_ETF_SYMBOLS_ORDER,
)
from app.services.market.market_data_service import coverage_analytics, infra
from app.services.market.universe import tracked_symbols

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


@dataclass
class _SummaryRow:
    symbol: str
    stage_label: str
    previous_stage_label: str | None = None
    current_stage_days: int | None = None
    current_price: float | None = None
    perf_1d: float | None = None
    perf_5d: float | None = None
    perf_20d: float | None = None
    rs_mansfield_pct: float | None = None
    atr_14: float | None = None
    sma_21: float | None = None
    sector: str | None = None
    industry: str | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    atrx_sma_21: float | None = None
    atrx_sma_50: float | None = None
    range_pos_52w: float | None = None
    rsi: float | None = None
    pe_ttm: float | None = None
    eps_growth_yoy: float | None = None
    revenue_growth_yoy: float | None = None
    next_earnings: datetime | None = None
    td_buy_setup: int | None = None
    td_sell_setup: int | None = None
    td_buy_countdown: int | None = None
    td_sell_countdown: int | None = None
    td_perfect_buy: bool | None = None
    td_perfect_sell: bool | None = None
    gaps_unfilled_up: int | None = None
    gaps_unfilled_down: int | None = None


class MarketDashboardService:
    """Build read-only market dashboard summaries from tracked snapshots."""

    @staticmethod
    def _safe_section(section: str, fn: Callable[[], _T], default: _T) -> _T:
        try:
            return fn()
        except Exception as e:
            logger.warning("market dashboard section %s failed: %s", section, e)
            return default

    def _fetch_rows(self, db: Session, *, universe: str = "all") -> tuple[list[str], list[_SummaryRow], dict[str, MarketTrackedPlan], datetime | None]:
        def _coalesce(primary, secondary):
            return primary if primary is not None else secondary

        tracked = tracked_symbols(db, redis_client=infra.redis_client)
        if not tracked:
            return [], [], {}, None

        if universe == "etf":
            etf_set = set(SECTOR_ETF_SYMBOLS_ORDER)
            tracked = [s for s in tracked if s in etf_set]
        elif universe == "holdings":
            held = {
                str(s).upper()
                for (s,) in db.query(Position.symbol).distinct()
                if s
            }
            tracked = [s for s in tracked if s in held]

        if not tracked:
            return [], [], {}, None

        rows = (
            db.query(MarketSnapshot)
            .options(load_only(
                MarketSnapshot.symbol, MarketSnapshot.analysis_timestamp,
                MarketSnapshot.analysis_type,
                MarketSnapshot.stage_label, MarketSnapshot.previous_stage_label,
                MarketSnapshot.current_stage_days, MarketSnapshot.current_price,
                MarketSnapshot.perf_1d, MarketSnapshot.perf_5d,
                MarketSnapshot.perf_20d, MarketSnapshot.perf_252d,
                MarketSnapshot.rs_mansfield_pct,
                MarketSnapshot.atr_14, MarketSnapshot.sma_21,
                MarketSnapshot.sma_50, MarketSnapshot.sma_200,
                MarketSnapshot.sector, MarketSnapshot.industry,
                MarketSnapshot.atrx_sma_21, MarketSnapshot.atrx_sma_50,
                MarketSnapshot.range_pos_52w, MarketSnapshot.rsi,
                MarketSnapshot.pe_ttm, MarketSnapshot.eps_growth_yoy,
                MarketSnapshot.revenue_growth_yoy, MarketSnapshot.next_earnings,
                MarketSnapshot.scan_tier,
                MarketSnapshot.action_label,
                MarketSnapshot.td_buy_setup, MarketSnapshot.td_sell_setup,
                MarketSnapshot.td_buy_countdown, MarketSnapshot.td_sell_countdown,
                MarketSnapshot.td_perfect_buy, MarketSnapshot.td_perfect_sell,
                MarketSnapshot.gaps_unfilled_up, MarketSnapshot.gaps_unfilled_down,
            ))
            .filter(
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.symbol.in_(tracked),
            )
            .distinct(MarketSnapshot.symbol)
            .order_by(MarketSnapshot.symbol, MarketSnapshot.analysis_timestamp.desc())
            .all()
        )

        latest_by_symbol: dict[str, MarketSnapshot] = {}
        for r in rows:
            sym = str(getattr(r, "symbol", "")).upper()
            if sym and sym not in latest_by_symbol:
                latest_by_symbol[sym] = r

        history_rows = (
            db.query(MarketSnapshotHistory)
            .options(load_only(
                MarketSnapshotHistory.symbol, MarketSnapshotHistory.as_of_date,
                MarketSnapshotHistory.analysis_type,
                MarketSnapshotHistory.stage_label, MarketSnapshotHistory.previous_stage_label,
                MarketSnapshotHistory.current_stage_days, MarketSnapshotHistory.current_price,
                MarketSnapshotHistory.perf_1d, MarketSnapshotHistory.perf_5d,
                MarketSnapshotHistory.perf_20d,
                MarketSnapshotHistory.rs_mansfield_pct,
                MarketSnapshotHistory.atr_14, MarketSnapshotHistory.sma_21,
                MarketSnapshotHistory.sma_50, MarketSnapshotHistory.sma_200,
                MarketSnapshotHistory.sector, MarketSnapshotHistory.industry,
                MarketSnapshotHistory.atrx_sma_21, MarketSnapshotHistory.atrx_sma_50,
                MarketSnapshotHistory.range_pos_52w, MarketSnapshotHistory.rsi,
            ))
            .filter(
                MarketSnapshotHistory.analysis_type == "technical_snapshot",
                MarketSnapshotHistory.symbol.in_(list(latest_by_symbol.keys())),
            )
            .order_by(MarketSnapshotHistory.symbol.asc(), MarketSnapshotHistory.as_of_date.desc())
            .distinct(MarketSnapshotHistory.symbol)
            .all()
        )
        latest_history_by_symbol: dict[str, MarketSnapshotHistory] = {}
        for h in history_rows:
            sym = str(getattr(h, "symbol", "")).upper()
            if sym and sym not in latest_history_by_symbol:
                latest_history_by_symbol[sym] = h

        plans = (
            db.query(MarketTrackedPlan)
            .filter(MarketTrackedPlan.symbol.in_(list(latest_by_symbol.keys())))
            .all()
        )
        plan_map = {str(p.symbol).upper(): p for p in plans}

        out: list[_SummaryRow] = []
        for sym in sorted(latest_by_symbol.keys()):
            r = latest_by_symbol[sym]
            h = latest_history_by_symbol.get(sym)
            out.append(
                _SummaryRow(
                    symbol=sym,
                    stage_label=str(_coalesce(getattr(r, "stage_label", None), getattr(h, "stage_label", None)) or "UNKNOWN"),
                    previous_stage_label=_coalesce(getattr(r, "previous_stage_label", None), getattr(h, "previous_stage_label", None)),
                    current_stage_days=_coalesce(getattr(r, "current_stage_days", None), getattr(h, "current_stage_days", None)),
                    current_price=_coalesce(getattr(r, "current_price", None), getattr(h, "current_price", None)),
                    perf_1d=_coalesce(getattr(r, "perf_1d", None), getattr(h, "perf_1d", None)),
                    perf_5d=_coalesce(getattr(r, "perf_5d", None), getattr(h, "perf_5d", None)),
                    perf_20d=_coalesce(getattr(r, "perf_20d", None), getattr(h, "perf_20d", None)),
                    rs_mansfield_pct=_coalesce(getattr(r, "rs_mansfield_pct", None), getattr(h, "rs_mansfield_pct", None)),
                    atr_14=_coalesce(getattr(r, "atr_14", None), getattr(h, "atr_14", None)),
                    sma_21=_coalesce(getattr(r, "sma_21", None), getattr(h, "sma_21", None)),
                    sector=_coalesce(getattr(r, "sector", None), getattr(h, "sector", None)),
                    industry=_coalesce(getattr(r, "industry", None), getattr(h, "industry", None)),
                    sma_50=_coalesce(getattr(r, "sma_50", None), getattr(h, "sma_50", None)),
                    sma_200=_coalesce(getattr(r, "sma_200", None), getattr(h, "sma_200", None)),
                    atrx_sma_21=_coalesce(getattr(r, "atrx_sma_21", None), getattr(h, "atrx_sma_21", None)),
                    atrx_sma_50=_coalesce(getattr(r, "atrx_sma_50", None), getattr(h, "atrx_sma_50", None)),
                    range_pos_52w=_coalesce(getattr(r, "range_pos_52w", None), getattr(h, "range_pos_52w", None)),
                    rsi=getattr(r, "rsi", None),
                    pe_ttm=getattr(r, "pe_ttm", None),
                    eps_growth_yoy=getattr(r, "eps_growth_yoy", None),
                    revenue_growth_yoy=getattr(r, "revenue_growth_yoy", None),
                    next_earnings=getattr(r, "next_earnings", None),
                    td_buy_setup=getattr(r, "td_buy_setup", None),
                    td_sell_setup=getattr(r, "td_sell_setup", None),
                    td_buy_countdown=getattr(r, "td_buy_countdown", None),
                    td_sell_countdown=getattr(r, "td_sell_countdown", None),
                    td_perfect_buy=getattr(r, "td_perfect_buy", None),
                    td_perfect_sell=getattr(r, "td_perfect_sell", None),
                    gaps_unfilled_up=getattr(r, "gaps_unfilled_up", None),
                    gaps_unfilled_down=getattr(r, "gaps_unfilled_down", None),
                )
            )
        timestamps = [getattr(r, "analysis_timestamp", None) for r in latest_by_symbol.values() if getattr(r, "analysis_timestamp", None) is not None]
        latest_ts = max(timestamps) if timestamps else None
        return tracked, out, plan_map, latest_ts

    @staticmethod
    def _is_pos(v: float | None) -> bool:
        return isinstance(v, (int, float)) and float(v) > 0

    @staticmethod
    def _is_num(v: float | None) -> bool:
        return isinstance(v, (int, float))

    @staticmethod
    def _normalize_stage_label(stage_label: str | None) -> str | None:
        raw = str(stage_label or "").strip().upper()
        if not raw:
            return None
        if "2A" in raw:
            return "2A"
        if "2B" in raw:
            return "2B"
        if "2C" in raw:
            return "2C"
        if raw in {"2", "STAGE 2"}:
            # Legacy coarse stage "2" maps to the first Stage 2 bucket.
            return "2A"
        if "1" == raw or raw.endswith(" 1") or raw == "STAGE 1":
            return "1"
        if "3" == raw or raw.endswith(" 3") or raw == "STAGE 3":
            return "3"
        if "4" == raw or raw.endswith(" 4") or raw == "STAGE 4":
            return "4"
        return None

    @staticmethod
    def _to_item(r: _SummaryRow, include_score: bool = False, score: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": r.symbol,
            "stage_label": r.stage_label,
            "previous_stage_label": r.previous_stage_label,
            "current_price": r.current_price,
            "perf_1d": r.perf_1d,
            "perf_5d": r.perf_5d,
            "perf_20d": r.perf_20d,
            "rs_mansfield_pct": r.rs_mansfield_pct,
            "sector": r.sector,
            "industry": r.industry,
            "current_stage_days": r.current_stage_days,
        }
        if include_score:
            payload["momentum_score"] = score
        return payload

    @staticmethod
    def _momentum_score(r: _SummaryRow) -> float:
        perf20 = float(r.perf_20d or 0.0)
        perf5 = float(r.perf_5d or 0.0)
        rs = float(r.rs_mansfield_pct or 0.0)
        return round((0.45 * perf20) + (0.35 * rs) + (0.20 * perf5), 2)

    @staticmethod
    def _abs_percent_distance(current_price: float | None, target_price: float | None) -> float | None:
        if not isinstance(current_price, (int, float)) or not isinstance(target_price, (int, float)):
            return None
        if float(target_price) <= 0:
            return None
        return abs((float(current_price) - float(target_price)) / float(target_price)) * 100.0

    @staticmethod
    def _abs_atr_distance(r: _SummaryRow, target_price: float | None) -> float | None:
        if not isinstance(r.current_price, (int, float)) or not isinstance(target_price, (int, float)):
            return None
        if not isinstance(r.atr_14, (int, float)) or float(r.atr_14) <= 0:
            return None
        return abs((float(r.current_price) - float(target_price)) / float(r.atr_14))

    @staticmethod
    def _price_vs_sma_atr(current_price: float | None, sma: float | None, atr: float | None) -> float | None:
        if not isinstance(current_price, (int, float)):
            return None
        if not isinstance(sma, (int, float)):
            return None
        if not isinstance(atr, (int, float)) or float(atr) <= 0:
            return None
        return (float(current_price) - float(sma)) / float(atr)

    def _build_range_histogram(self, rows: list[_SummaryRow]) -> list[dict[str, Any]]:
        bins = [0] * 10
        for r in rows:
            v = r.range_pos_52w
            if not isinstance(v, (int, float)):
                continue
            idx = min(int(float(v) / 10), 9)
            idx = max(0, idx)
            bins[idx] += 1
        return [
            {"bin": f"{i * 10}-{(i + 1) * 10}%", "count": bins[i]}
            for i in range(10)
        ]

    def _build_breadth_series(self, db: Session, tracked: list[str]) -> list[dict[str, Any]]:
        """Breadth over full technical_snapshot universe (MV → raw fallback).

        The ``tracked`` parameter is accepted for interface compatibility but
        breadth is intentionally computed over all snapshot symbols so
        MV and raw paths produce identical results.
        """
        from app.services.market.market_mv_service import market_mv_service
        return market_mv_service.get_breadth_series(db, days=120)

    def _build_rrg_sectors(self, rows: list[_SummaryRow]) -> list[dict[str, Any]]:
        row_by_symbol = {r.symbol: r for r in rows}
        result = []
        for sym in SECTOR_ETF_SYMBOLS_ORDER:
            candidates = SECTOR_ETF_PROXY_SYMBOLS.get(sym, [sym])
            row = next((row_by_symbol.get(c) for c in candidates if row_by_symbol.get(c)), None)
            if not row:
                continue
            rs = row.rs_mansfield_pct
            perf5 = row.perf_5d
            if not isinstance(rs, (int, float)):
                continue
            rs_ratio = float(rs)
            rs_momentum = float(perf5) if isinstance(perf5, (int, float)) else 0.0
            result.append({
                "symbol": sym,
                "name": SECTOR_ETF_DISPLAY_NAMES.get(sym, sym),
                "rs_ratio": round(rs_ratio, 2),
                "rs_momentum": round(rs_momentum, 2),
            })
        return result

    def _build_upcoming_earnings(self, rows: list[_SummaryRow]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(days=7)
        result = []
        for r in rows:
            if not isinstance(r.next_earnings, datetime):
                continue
            ne = r.next_earnings
            ne_utc = (
                ne.replace(tzinfo=timezone.utc)
                if ne.tzinfo is None
                else ne.astimezone(timezone.utc)
            )
            if now <= ne_utc <= horizon:
                result.append({
                    "symbol": r.symbol,
                    "next_earnings": r.next_earnings.isoformat(),
                    "stage_label": r.stage_label,
                    "rs_mansfield_pct": r.rs_mansfield_pct,
                    "sector": r.sector,
                })
        return sorted(result, key=lambda x: x["next_earnings"])

    def _build_fundamental_leaders(self, rows: list[_SummaryRow]) -> list[dict[str, Any]]:
        scored = []
        for r in rows:
            eps = r.eps_growth_yoy
            rs = r.rs_mansfield_pct
            if not isinstance(eps, (int, float)) or not isinstance(rs, (int, float)):
                continue
            composite = round(0.5 * float(eps) + 0.5 * float(rs), 2)
            scored.append({
                "symbol": r.symbol,
                "eps_growth_yoy": round(float(eps), 2),
                "rs_mansfield_pct": round(float(rs), 2),
                "pe_ttm": round(float(r.pe_ttm), 2) if isinstance(r.pe_ttm, (int, float)) else None,
                "stage_label": r.stage_label,
                "sector": r.sector,
                "composite_score": composite,
            })
        return sorted(scored, key=lambda x: x["composite_score"], reverse=True)[:10]

    def _build_rsi_divergences(self, rows: list[_SummaryRow]) -> dict[str, list[dict[str, Any]]]:
        bearish = []
        bullish = []
        for r in rows:
            perf20 = r.perf_20d
            rsi = r.rsi
            if not isinstance(perf20, (int, float)) or not isinstance(rsi, (int, float)):
                continue
            if float(perf20) > 5 and float(rsi) < 50:
                bearish.append({
                    "symbol": r.symbol,
                    "perf_20d": round(float(perf20), 1),
                    "rsi": round(float(rsi), 1),
                    "stage_label": r.stage_label,
                    "sector": r.sector,
                })
            elif float(perf20) < -5 and float(rsi) > 50:
                bullish.append({
                    "symbol": r.symbol,
                    "perf_20d": round(float(perf20), 1),
                    "rsi": round(float(rsi), 1),
                    "stage_label": r.stage_label,
                    "sector": r.sector,
                })
        bearish.sort(key=lambda x: x["perf_20d"], reverse=True)
        bullish.sort(key=lambda x: x["perf_20d"])
        return {"bearish": bearish[:10], "bullish": bullish[:10]}

    def _build_td_signals(self, rows: list[_SummaryRow]) -> list[dict[str, Any]]:
        result = []
        for r in rows:
            signals = []
            if isinstance(r.td_buy_setup, int) and r.td_buy_setup >= 9:
                signals.append("Buy Setup 9")
            if isinstance(r.td_sell_setup, int) and r.td_sell_setup >= 9:
                signals.append("Sell Setup 9")
            if isinstance(r.td_buy_countdown, int) and r.td_buy_countdown >= 13:
                signals.append("Buy Countdown 13")
            if isinstance(r.td_sell_countdown, int) and r.td_sell_countdown >= 13:
                signals.append("Sell Countdown 13")
            if r.td_perfect_buy:
                signals.append("Perfect Buy")
            if r.td_perfect_sell:
                signals.append("Perfect Sell")
            if signals:
                result.append({
                    "symbol": r.symbol,
                    "signals": signals,
                    "stage_label": r.stage_label,
                    "perf_1d": r.perf_1d,
                    "sector": r.sector,
                })
        result.sort(
            key=lambda x: (
                len(x["signals"]),
                abs(float(x.get("perf_1d") or 0)),
            ),
            reverse=True,
        )
        return result[:30]

    def _build_gap_leaders(self, rows: list[_SummaryRow]) -> list[dict[str, Any]]:
        result = []
        for r in rows:
            up = r.gaps_unfilled_up if isinstance(r.gaps_unfilled_up, int) else 0
            down = r.gaps_unfilled_down if isinstance(r.gaps_unfilled_down, int) else 0
            total = up + down
            if total <= 0:
                continue
            result.append({
                "symbol": r.symbol,
                "gaps_up": up,
                "gaps_down": down,
                "total_gaps": total,
                "stage_label": r.stage_label,
                "sector": r.sector,
            })
        return sorted(result, key=lambda x: x["total_gaps"], reverse=True)[:10]

    def _build_metric_rankings(self, rows: list[_SummaryRow]) -> dict[str, dict[str, list[dict[str, Any]]]]:
        def _entries(metric_name: str, value_getter) -> list[dict[str, Any]]:
            values = []
            for r in rows:
                value = value_getter(r)
                if isinstance(value, (int, float)):
                    values.append({"symbol": r.symbol, "value": float(value), "metric": metric_name})
            return values

        metric_values = {
            "perf_1d": _entries("perf_1d", lambda r: r.perf_1d),
            "perf_5d": _entries("perf_5d", lambda r: r.perf_5d),
            "perf_20d": _entries("perf_20d", lambda r: r.perf_20d),
            "atrx_sma_21": _entries("atrx_sma_21", lambda r: r.atrx_sma_21),
            "atrx_sma_50": _entries("atrx_sma_50", lambda r: r.atrx_sma_50),
            "atrx_sma_200": _entries(
                "atrx_sma_200",
                lambda r: self._price_vs_sma_atr(r.current_price, r.sma_200, r.atr_14),
            ),
        }

        out: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for metric, values in metric_values.items():
            values_sorted = sorted(values, key=lambda x: x["value"], reverse=True)
            out[metric] = {
                "top": values_sorted[:10],
                "bottom": sorted(values, key=lambda x: x["value"])[:10],
            }
        return out

    def build_dashboard(self, db: Session, *, universe: str = "all") -> dict[str, Any]:
        empty_payload: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "latest_snapshot_at": None,
            "tracked_count": 0,
            "snapshot_count": 0,
            "coverage": None,
            "regime": {},
            "leaders": [],
            "setups": {"breakout_candidates": [], "pullback_candidates": [], "rs_leaders": []},
            "sector_momentum": [],
            "action_queue": [],
            "entry_proximity_top": [],
            "exit_proximity_top": [],
            "sector_etf_table": [],
            "entering_stage_2a": [],
            "entering_stage_3": [],
            "entering_stage_4": [],
            "top10_matrix": {},
            "bottom10_matrix": {},
            "range_histogram": [],
            "breadth_series": [],
            "rrg_sectors": [],
            "upcoming_earnings": [],
            "fundamental_leaders": [],
            "rsi_divergences": {"bearish": [], "bullish": []},
            "td_signals": [],
            "gap_leaders": [],
            "constituent_symbols": [],
        }
        try:
            tracked, rows, plan_map, latest_snapshot_ts = self._fetch_rows(db, universe=universe)
        except Exception as e:
            logger.warning("market dashboard fetch failed: %s", e)
            return empty_payload

        tracked_count = len(tracked)
        snapshot_count = len(rows)
        if tracked_count == 0:
            return empty_payload

        stage_norm_default = {"1": 0, "2A": 0, "2B": 0, "2C": 0, "3": 0, "4": 0}

        def empty_sector_etf_table() -> list[dict[str, Any]]:
            return [
                {
                    "symbol": configured_symbol,
                    "sector_name": SECTOR_ETF_DISPLAY_NAMES.get(configured_symbol, configured_symbol),
                    "change_1d": None,
                    "change_5d": None,
                    "change_20d": None,
                    "rs_mansfield_pct": None,
                    "atrx_sma_50": None,
                    "stage_label": None,
                    "days_in_stage": None,
                }
                for configured_symbol in SECTOR_ETF_SYMBOLS_ORDER
            ]

        def regime_stats() -> tuple[dict[str, int], int, int, int, int, int]:
            stage_counts: dict[str, int] = defaultdict(int)
            up_1d = 0
            down_1d = 0
            flat_1d = 0
            above_50 = 0
            above_200 = 0
            for r in rows:
                stage_counts[r.stage_label] += 1
                if self._is_num(r.perf_1d):
                    p1 = float(r.perf_1d or 0.0)
                    if p1 > 0:
                        up_1d += 1
                    elif p1 < 0:
                        down_1d += 1
                    else:
                        flat_1d += 1
                if self._is_num(r.current_price) and self._is_num(r.sma_50) and float(r.current_price or 0.0) > float(r.sma_50 or 0.0):
                    above_50 += 1
                if self._is_num(r.current_price) and self._is_num(r.sma_200) and float(r.current_price or 0.0) > float(r.sma_200 or 0.0):
                    above_200 += 1
            return stage_counts, up_1d, down_1d, flat_1d, above_50, above_200

        stage_counts, up_1d, down_1d, flat_1d, above_50, above_200 = self._safe_section(
            "regime_stats",
            regime_stats,
            (defaultdict(int), 0, 0, 0, 0, 0),
        )

        def leaders_and_setups() -> tuple[list[dict[str, Any]], list[_SummaryRow], list[_SummaryRow], list[_SummaryRow]]:
            scored = sorted(
                [(self._momentum_score(r), r) for r in rows if self._is_num(r.perf_20d) and self._is_num(r.rs_mansfield_pct)],
                key=lambda x: x[0],
                reverse=True,
            )
            leaders_local = [self._to_item(r, include_score=True, score=s) for s, r in scored[:12]]
            stage2_labels = {"2", "2A", "2B", "2C"}
            breakout = [
                r
                for r in rows
                if r.stage_label in stage2_labels
                and self._is_pos(r.perf_5d)
                and self._is_pos(r.rs_mansfield_pct)
                and self._is_num(r.current_price)
                and self._is_num(r.sma_50)
                and float(r.current_price or 0.0) > float(r.sma_50 or 0.0)
            ]
            pullback = [
                r
                for r in rows
                if r.stage_label in stage2_labels
                and self._is_num(r.perf_5d)
                and -4.0 <= float(r.perf_5d or 0.0) <= 2.0
                and self._is_pos(r.rs_mansfield_pct)
                and self._is_num(r.current_price)
                and self._is_num(r.sma_50)
                and float(r.current_price or 0.0) > float(r.sma_50 or 0.0)
            ]
            breakout = sorted(breakout, key=self._momentum_score, reverse=True)
            pullback = sorted(pullback, key=self._momentum_score, reverse=True)
            rs_lead = sorted(
                [r for r in rows if self._is_num(r.rs_mansfield_pct)],
                key=lambda x: float(x.rs_mansfield_pct or 0.0),
                reverse=True,
            )
            return leaders_local, breakout, pullback, rs_lead

        leaders, breakout_rows, pullback_rows, rs_leaders = self._safe_section(
            "leaders_and_setups",
            leaders_and_setups,
            ([], [], [], []),
        )

        def sector_momentum_section() -> list[dict[str, Any]]:
            by_sector: dict[str, list[_SummaryRow]] = defaultdict(list)
            for r in rows:
                sec = (r.sector or "").strip() or "Unknown"
                by_sector[sec].append(r)
            sector_momentum_local: list[dict[str, Any]] = []
            for sec, sec_rows in by_sector.items():
                perfs = [float(x.perf_20d) for x in sec_rows if self._is_num(x.perf_20d)]
                rs_vals = [float(x.rs_mansfield_pct) for x in sec_rows if self._is_num(x.rs_mansfield_pct)]
                if not perfs and not rs_vals:
                    continue
                sector_momentum_local.append(
                    {
                        "sector": sec,
                        "count": len(sec_rows),
                        "avg_perf_20d": round(sum(perfs) / len(perfs), 2) if perfs else None,
                        "avg_rs_mansfield_pct": round(sum(rs_vals) / len(rs_vals), 2) if rs_vals else None,
                    }
                )
            return sorted(
                sector_momentum_local,
                key=lambda x: float(x.get("avg_perf_20d") or -9999.0),
                reverse=True,
            )[:10]

        sector_momentum = self._safe_section("sector_momentum", sector_momentum_section, [])

        def action_queue_section() -> list[dict[str, Any]]:
            def _aq_urgency(r: _SummaryRow) -> float:
                score = 0.0
                if r.previous_stage_label and r.previous_stage_label != r.stage_label:
                    score += 10.0
                if self._is_num(r.perf_1d):
                    score += abs(float(r.perf_1d or 0.0))
                if self._is_num(r.rs_mansfield_pct):
                    score += abs(float(r.rs_mansfield_pct or 0.0)) * 0.5
                return score

            aq_candidates = [
                r for r in rows
                if (r.previous_stage_label and r.previous_stage_label != r.stage_label)
                or (self._is_num(r.perf_1d) and abs(float(r.perf_1d or 0.0)) >= 3.0)
                or (self._is_num(r.rs_mansfield_pct) and abs(float(r.rs_mansfield_pct or 0.0)) >= 6.0)
            ]
            aq_candidates.sort(key=_aq_urgency, reverse=True)
            return [self._to_item(r) for r in aq_candidates[:30]]

        action_queue = self._safe_section("action_queue", action_queue_section, [])

        def stage_transitions_section() -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
            stage_counts_normalized = {
                "1": 0,
                "2A": 0,
                "2B": 0,
                "2C": 0,
                "3": 0,
                "4": 0,
            }
            for r in rows:
                key = self._normalize_stage_label(r.stage_label)
                if key:
                    stage_counts_normalized[key] += 1
            entering_2a = [
                {
                    "symbol": r.symbol,
                    "previous_stage_label": r.previous_stage_label,
                    "stage_label": r.stage_label,
                    "current_stage_days": r.current_stage_days,
                    "perf_1d": r.perf_1d,
                }
                for r in rows
                if self._normalize_stage_label(r.stage_label) == "2A"
                and self._normalize_stage_label(r.previous_stage_label) != "2A"
            ]
            entering_3 = [
                {
                    "symbol": r.symbol,
                    "previous_stage_label": r.previous_stage_label,
                    "stage_label": r.stage_label,
                    "current_stage_days": r.current_stage_days,
                    "perf_1d": r.perf_1d,
                }
                for r in rows
                if self._normalize_stage_label(r.stage_label) == "3"
                and self._normalize_stage_label(r.previous_stage_label) != "3"
            ]
            entering_4 = [
                {
                    "symbol": r.symbol,
                    "previous_stage_label": r.previous_stage_label,
                    "stage_label": r.stage_label,
                    "current_stage_days": r.current_stage_days,
                    "perf_1d": r.perf_1d,
                }
                for r in rows
                if self._normalize_stage_label(r.stage_label) == "4"
                and self._normalize_stage_label(r.previous_stage_label) != "4"
            ]
            return stage_counts_normalized, entering_2a, entering_3, entering_4

        stage_counts_normalized, entering_stage_2a, entering_stage_3, entering_stage_4 = self._safe_section(
            "stage_transitions",
            stage_transitions_section,
            (dict(stage_norm_default), [], [], []),
        )

        def proximity_section() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            proximity_rows = []
            for r in rows:
                plan = plan_map.get(r.symbol)
                entry = getattr(plan, "entry_price", None) if plan else None
                exit_ = getattr(plan, "exit_price", None) if plan else None
                proximity_rows.append((r, entry, exit_))
            entry_top = sorted(
                [
                    {
                        "symbol": r.symbol,
                        "current_price": r.current_price,
                        "entry_price": entry,
                        "distance_pct": self._abs_percent_distance(r.current_price, entry),
                        "distance_atr": self._abs_atr_distance(r, entry),
                        "sector": r.sector,
                        "stage_label": r.stage_label,
                        "current_stage_days": r.current_stage_days,
                    }
                    for (r, entry, _exit) in proximity_rows
                    if self._abs_percent_distance(r.current_price, entry) is not None
                ],
                key=lambda x: float(x["distance_pct"] or 999999.0),
            )[:10]
            exit_top = sorted(
                [
                    {
                        "symbol": r.symbol,
                        "current_price": r.current_price,
                        "exit_price": exit_,
                        "distance_pct": self._abs_percent_distance(r.current_price, exit_),
                        "distance_atr": self._abs_atr_distance(r, exit_),
                        "sector": r.sector,
                        "stage_label": r.stage_label,
                        "current_stage_days": r.current_stage_days,
                    }
                    for (r, _entry, exit_) in proximity_rows
                    if self._abs_percent_distance(r.current_price, exit_) is not None
                ],
                key=lambda x: float(x["distance_pct"] or 999999.0),
            )[:10]
            return entry_top, exit_top

        entry_proximity_top, exit_proximity_top = self._safe_section(
            "proximity",
            proximity_section,
            ([], []),
        )

        def sector_etf_section() -> list[dict[str, Any]]:
            row_by_symbol = {r.symbol: r for r in rows}
            sector_etf_table_local: list[dict[str, Any]] = []
            for configured_symbol in SECTOR_ETF_SYMBOLS_ORDER:
                candidate_symbols = SECTOR_ETF_PROXY_SYMBOLS.get(
                    configured_symbol,
                    [configured_symbol],
                )
                row = next((row_by_symbol.get(candidate) for candidate in candidate_symbols if row_by_symbol.get(candidate)), None)
                sector_etf_table_local.append(
                    {
                        "symbol": configured_symbol,
                        "sector_name": SECTOR_ETF_DISPLAY_NAMES.get(configured_symbol, configured_symbol),
                        "change_1d": row.perf_1d if row else None,
                        "change_5d": row.perf_5d if row else None,
                        "change_20d": row.perf_20d if row else None,
                        "rs_mansfield_pct": row.rs_mansfield_pct if row else None,
                        "atrx_sma_50": row.atrx_sma_50 if row else None,
                        "stage_label": row.stage_label if row else None,
                        "days_in_stage": row.current_stage_days if row else None,
                    }
                )
            return sector_etf_table_local

        sector_etf_table = self._safe_section("sector_etf_table", sector_etf_section, empty_sector_etf_table())

        matrix = self._safe_section(
            "metric_rankings",
            lambda: self._build_metric_rankings(rows),
            {},
        )
        range_histogram = self._safe_section(
            "range_histogram",
            lambda: self._build_range_histogram(rows),
            [],
        )
        breadth_series = self._safe_section(
            "breadth_series",
            lambda: self._build_breadth_series(db, tracked),
            [],
        )
        rrg_sectors = self._safe_section(
            "rrg_sectors",
            lambda: self._build_rrg_sectors(rows),
            [],
        )
        upcoming_earnings = self._safe_section(
            "upcoming_earnings",
            lambda: self._build_upcoming_earnings(rows),
            [],
        )
        fundamental_leaders = self._safe_section(
            "fundamental_leaders",
            lambda: self._build_fundamental_leaders(rows),
            [],
        )
        rsi_divergences = self._safe_section(
            "rsi_divergences",
            lambda: self._build_rsi_divergences(rows),
            {"bearish": [], "bullish": []},
        )
        td_signals = self._safe_section(
            "td_signals",
            lambda: self._build_td_signals(rows),
            [],
        )
        gap_leaders = self._safe_section(
            "gap_leaders",
            lambda: self._build_gap_leaders(rows),
            [],
        )

        constituent_syms = sorted(str(s).upper() for s in tracked)

        coverage_out: dict[str, Any] | None = None

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "latest_snapshot_at": latest_snapshot_ts.isoformat() if latest_snapshot_ts else None,
            "tracked_count": tracked_count,
            "snapshot_count": snapshot_count,
            "coverage": coverage_out,
            "regime": {
                "up_1d_count": up_1d,
                "down_1d_count": down_1d,
                "flat_1d_count": flat_1d,
                "above_sma50_count": above_50,
                "above_sma200_count": above_200,
                "stage_counts": dict(sorted(stage_counts.items(), key=lambda x: (-x[1], x[0]))),
                "stage_counts_normalized": stage_counts_normalized,
            },
            "leaders": leaders,
            "setups": {
                "breakout_candidates": [self._to_item(r) for r in breakout_rows[:10]],
                "pullback_candidates": [self._to_item(r) for r in pullback_rows[:10]],
                "rs_leaders": [self._to_item(r) for r in rs_leaders[:10]],
            },
            "sector_momentum": sector_momentum,
            "action_queue": action_queue,
            "entry_proximity_top": entry_proximity_top,
            "exit_proximity_top": exit_proximity_top,
            "sector_etf_table": sector_etf_table,
            "entering_stage_2a": entering_stage_2a,
            "entering_stage_3": entering_stage_3,
            "entering_stage_4": entering_stage_4,
            "top10_matrix": {k: v.get("top", []) for k, v in matrix.items()},
            "bottom10_matrix": {k: v.get("bottom", []) for k, v in matrix.items()},
            "range_histogram": range_histogram,
            "breadth_series": breadth_series,
            "rrg_sectors": rrg_sectors,
            "upcoming_earnings": upcoming_earnings,
            "fundamental_leaders": fundamental_leaders,
            "rsi_divergences": rsi_divergences,
            "td_signals": td_signals,
            "gap_leaders": gap_leaders,
            "constituent_symbols": constituent_syms,
        }
