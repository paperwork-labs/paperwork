from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory
from backend.models.market_tracked_plan import MarketTrackedPlan
from backend.services.market.constants import (
    SECTOR_ETF_DISPLAY_NAMES,
    SECTOR_ETF_PROXY_SYMBOLS,
    SECTOR_ETF_SYMBOLS_ORDER,
)
from backend.services.market.market_data_service import MarketDataService
from backend.services.market.universe import tracked_symbols


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


class MarketDashboardService:
    """Build read-only market dashboard summaries from tracked snapshots."""

    def _fetch_rows(self, db: Session) -> tuple[list[str], list[_SummaryRow], dict[str, MarketTrackedPlan]]:
        def _coalesce(primary, secondary):
            return primary if primary is not None else secondary

        svc = MarketDataService()
        tracked = tracked_symbols(db, redis_client=svc.redis_client)
        if not tracked:
            return [], [], {}

        rows = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.symbol.in_(tracked),
            )
            # Keep newest row first per symbol, then dedupe in Python.
            .order_by(MarketSnapshot.symbol.asc(), MarketSnapshot.analysis_timestamp.desc())
            .all()
        )

        latest_by_symbol: dict[str, MarketSnapshot] = {}
        for r in rows:
            sym = str(getattr(r, "symbol", "")).upper()
            if sym and sym not in latest_by_symbol:
                latest_by_symbol[sym] = r

        history_rows = (
            db.query(MarketSnapshotHistory)
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
                )
            )
        return tracked, out, plan_map

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

    def build_dashboard(self, db: Session) -> dict[str, Any]:
        tracked, rows, plan_map = self._fetch_rows(db)
        tracked_count = len(tracked)
        snapshot_count = len(rows)

        if tracked_count == 0:
            return {
                "generated_at": datetime.utcnow().isoformat(),
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
            }

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

        scored = sorted(
            [(self._momentum_score(r), r) for r in rows if self._is_num(r.perf_20d) and self._is_num(r.rs_mansfield_pct)],
            key=lambda x: x[0],
            reverse=True,
        )
        leaders = [self._to_item(r, include_score=True, score=s) for s, r in scored[:12]]

        stage2_labels = {"2", "2A", "2B", "2C"}
        breakout_rows = [
            r
            for r in rows
            if r.stage_label in stage2_labels
            and self._is_pos(r.perf_5d)
            and self._is_pos(r.rs_mansfield_pct)
            and self._is_num(r.current_price)
            and self._is_num(r.sma_50)
            and float(r.current_price or 0.0) > float(r.sma_50 or 0.0)
        ]
        pullback_rows = [
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
        # Rank setup lists before truncation so dashboard cards show best candidates,
        # not whichever symbols happen to appear first in source ordering.
        breakout_rows = sorted(
            breakout_rows,
            key=self._momentum_score,
            reverse=True,
        )
        pullback_rows = sorted(
            pullback_rows,
            key=self._momentum_score,
            reverse=True,
        )
        rs_leaders = sorted(
            [r for r in rows if self._is_num(r.rs_mansfield_pct)],
            key=lambda x: float(x.rs_mansfield_pct or 0.0),
            reverse=True,
        )

        by_sector: dict[str, list[_SummaryRow]] = defaultdict(list)
        for r in rows:
            sec = (r.sector or "").strip() or "Unknown"
            by_sector[sec].append(r)
        sector_momentum = []
        for sec, sec_rows in by_sector.items():
            perfs = [float(x.perf_20d) for x in sec_rows if self._is_num(x.perf_20d)]
            rs_vals = [float(x.rs_mansfield_pct) for x in sec_rows if self._is_num(x.rs_mansfield_pct)]
            if not perfs and not rs_vals:
                continue
            sector_momentum.append(
                {
                    "sector": sec,
                    "count": len(sec_rows),
                    "avg_perf_20d": round(sum(perfs) / len(perfs), 2) if perfs else None,
                    "avg_rs_mansfield_pct": round(sum(rs_vals) / len(rs_vals), 2) if rs_vals else None,
                }
            )
        sector_momentum = sorted(
            sector_momentum,
            key=lambda x: float(x.get("avg_perf_20d") or -9999.0),
            reverse=True,
        )[:10]

        action_queue = [
            self._to_item(r)
            for r in rows
            if (r.previous_stage_label and r.previous_stage_label != r.stage_label)
            or (self._is_num(r.perf_1d) and abs(float(r.perf_1d or 0.0)) >= 3.0)
            or (self._is_num(r.rs_mansfield_pct) and abs(float(r.rs_mansfield_pct or 0.0)) >= 6.0)
        ][:20]

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

        entering_stage_2a = [
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

        entering_stage_3 = [
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

        entering_stage_4 = [
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

        proximity_rows = []
        for r in rows:
            plan = plan_map.get(r.symbol)
            entry = getattr(plan, "entry_price", None) if plan else None
            exit_ = getattr(plan, "exit_price", None) if plan else None
            proximity_rows.append((r, entry, exit_))

        entry_proximity_top = sorted(
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

        exit_proximity_top = sorted(
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

        row_by_symbol = {r.symbol: r for r in rows}
        sector_etf_table: list[dict[str, Any]] = []
        for configured_symbol in SECTOR_ETF_SYMBOLS_ORDER:
            candidate_symbols = SECTOR_ETF_PROXY_SYMBOLS.get(
                configured_symbol,
                [configured_symbol],
            )
            row = next((row_by_symbol.get(candidate) for candidate in candidate_symbols if row_by_symbol.get(candidate)), None)
            sector_etf_table.append(
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

        matrix = self._build_metric_rankings(rows)

        md_svc = MarketDataService()
        coverage = md_svc.coverage.build_coverage_response(
            db,
            fill_trading_days_window=50,
            fill_lookback_days=120,
        )

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "tracked_count": tracked_count,
            "snapshot_count": snapshot_count,
            "coverage": {
                "status": coverage.get("status"),
                "daily_pct": (((coverage.get("daily") or {}).get("coverage") or {}).get("pct")),
                "m5_pct": (((coverage.get("m5") or {}).get("coverage") or {}).get("pct")),
                "daily_stale": (((coverage.get("daily") or {}).get("coverage") or {}).get("stale_count")),
                "m5_stale": (((coverage.get("m5") or {}).get("coverage") or {}).get("stale_count")),
            },
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
        }
