from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.market_data import MarketSnapshot
from backend.services.market.market_data_service import MarketDataService
from backend.services.market.universe import tracked_symbols


@dataclass
class _SummaryRow:
    symbol: str
    stage_label: str
    previous_stage_label: str | None
    current_price: float | None
    perf_1d: float | None
    perf_5d: float | None
    perf_20d: float | None
    rs_mansfield_pct: float | None
    sector: str | None
    industry: str | None
    sma_50: float | None
    sma_200: float | None


class MarketDashboardService:
    """Build read-only market dashboard summaries from tracked snapshots."""

    def _fetch_rows(self, db: Session) -> tuple[list[str], list[_SummaryRow]]:
        svc = MarketDataService()
        tracked = tracked_symbols(db, redis_client=svc.redis_client)
        if not tracked:
            return [], []

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

        out: list[_SummaryRow] = []
        for sym in sorted(latest_by_symbol.keys()):
            r = latest_by_symbol[sym]
            out.append(
                _SummaryRow(
                    symbol=sym,
                    stage_label=str(getattr(r, "stage_label", "") or "UNKNOWN"),
                    previous_stage_label=getattr(r, "previous_stage_label", None),
                    current_price=getattr(r, "current_price", None),
                    perf_1d=getattr(r, "perf_1d", None),
                    perf_5d=getattr(r, "perf_5d", None),
                    perf_20d=getattr(r, "perf_20d", None),
                    rs_mansfield_pct=getattr(r, "rs_mansfield_pct", None),
                    sector=getattr(r, "sector", None),
                    industry=getattr(r, "industry", None),
                    sma_50=getattr(r, "sma_50", None),
                    sma_200=getattr(r, "sma_200", None),
                )
            )
        return tracked, out

    @staticmethod
    def _is_pos(v: float | None) -> bool:
        return isinstance(v, (int, float)) and float(v) > 0

    @staticmethod
    def _is_num(v: float | None) -> bool:
        return isinstance(v, (int, float))

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

    def build_dashboard(self, db: Session) -> dict[str, Any]:
        tracked, rows = self._fetch_rows(db)
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
            },
            "leaders": leaders,
            "setups": {
                "breakout_candidates": [self._to_item(r) for r in breakout_rows[:10]],
                "pullback_candidates": [self._to_item(r) for r in pullback_rows[:10]],
                "rs_leaders": [self._to_item(r) for r in rs_leaders[:10]],
            },
            "sector_momentum": sector_momentum,
            "action_queue": action_queue,
        }
