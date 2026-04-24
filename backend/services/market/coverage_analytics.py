"""medallion: silver"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from backend.config import settings
from backend.models.market_data import PriceData, MarketSnapshotHistory
from backend.models.index_constituent import IndexConstituent
from backend.services.market.universe import tracked_symbols_with_source
from backend.services.market.coverage_utils import compute_coverage_status

if TYPE_CHECKING:
    from backend.services.market.market_infra import MarketInfra

logger = logging.getLogger(__name__)


class CoverageAnalytics:
    """Coverage computation, freshness metrics, and benchmark health."""

    def __init__(self, infra: "MarketInfra") -> None:
        self._infra = infra

    def benchmark_health(
        self,
        db: Session,
        benchmark_symbol: str = "SPY",
        required_bars: int | None = None,
        latest_daily_dt: datetime | None = None,
    ) -> Dict[str, Any]:
        """Return benchmark health stats for Stage/RS diagnostics."""
        required = required_bars or max(
            260, int(getattr(settings, "SNAPSHOT_DAILY_BARS_LIMIT", 400))
        )
        latest_dt = (
            db.query(func.max(PriceData.date))
            .filter(PriceData.symbol == benchmark_symbol, PriceData.interval == "1d")
            .scalar()
        )
        count = (
            db.query(func.count(PriceData.id))
            .filter(PriceData.symbol == benchmark_symbol, PriceData.interval == "1d")
            .scalar()
            or 0
        )
        stale = False
        if latest_daily_dt and latest_dt:
            try:
                stale = latest_dt.date() < latest_daily_dt.date()
            except Exception as e:
                logger.warning(
                    "benchmark_health stale date compare failed for %s: %s",
                    benchmark_symbol,
                    e,
                )
                stale = False
        return {
            "symbol": benchmark_symbol,
            "latest_daily_dt": latest_dt,
            "latest_daily_date": latest_dt.date().isoformat() if latest_dt else None,
            "daily_bars": int(count),
            "required_bars": int(required),
            "ok": int(count) >= int(required),
            "stale": bool(stale),
        }

    def _compute_interval_coverage_for_symbols(
        self,
        db: Session,
        *,
        symbols: List[str],
        interval: str,
        now_utc: datetime | None = None,
        stale_sample_limit: int | None = None,
        return_full_stale: bool = False,
    ) -> tuple[Dict[str, Any], List[str] | None]:
        """Compute freshness buckets and stale/missing sets for a given symbol universe."""
        now = now_utc or datetime.now(timezone.utc)
        safe_symbols = sorted({str(s).upper() for s in (symbols or []) if s})
        sym_set = set(safe_symbols)
        if stale_sample_limit is None:
            stale_sample_limit = int(settings.COVERAGE_STALE_SAMPLE)

        last_dt: Dict[str, datetime | None] = {s: None for s in safe_symbols}
        if sym_set:
            rows = (
                db.query(PriceData.symbol, PriceData.date)
                .filter(PriceData.interval == interval, PriceData.symbol.in_(sym_set))
                .order_by(PriceData.symbol.asc(), PriceData.date.desc())
                .distinct(PriceData.symbol)
                .all()
            )
            for sym, dt in rows:
                if sym:
                    last_dt[str(sym).upper()] = dt

        def _bucketize(ts: datetime | None) -> str:
            if not ts:
                return "none"
            ts_utc = (
                ts.replace(tzinfo=timezone.utc)
                if ts.tzinfo is None
                else ts.astimezone(timezone.utc)
            )
            age = now - ts_utc
            if age <= timedelta(hours=24):
                return "<=24h"
            if age <= timedelta(hours=48):
                return "24-48h"
            return ">48h"

        freshness = {"<=24h": 0, "24-48h": 0, ">48h": 0, "none": 0}
        stale_items: List[Dict[str, Any]] = []
        stale_full: List[str] = []

        for sym in safe_symbols:
            dt = last_dt.get(sym)
            bucket = _bucketize(dt)
            freshness[bucket] = int(freshness.get(bucket, 0)) + 1
            if bucket in (">48h", "none"):
                stale_items.append(
                    {"symbol": sym, "last": dt.isoformat() if dt else None, "bucket": bucket}
                )
                stale_full.append(sym)

        stale_items.sort(
            key=lambda item: (
                item.get("bucket") or "",
                item.get("last") or "",
                item.get("symbol") or "",
            )
        )
        stale_sample = stale_items[: max(0, int(stale_sample_limit))]

        fresh_24 = int(freshness["<=24h"])
        fresh_48 = int(freshness["24-48h"])
        stale_48h = int(freshness[">48h"])
        missing = int(freshness["none"])

        last_iso_map: Dict[str, str | None] = {s: (last_dt[s].isoformat() if last_dt[s] else None) for s in safe_symbols}

        section: Dict[str, Any] = {
            "count": fresh_24 + fresh_48,
            "last": last_iso_map,
            "freshness": freshness,
            "stale": stale_sample,
            "fresh_24h": fresh_24,
            "fresh_48h": fresh_48,
            "fresh_gt48h": 0,
            "stale_48h": stale_48h,
            "missing": missing,
        }
        return section, (stale_full if return_full_stale else None)

    def coverage_snapshot(
        self,
        db: Session,
        *,
        fill_lookback_days: int | None = None,
    ) -> Dict[str, Any]:
        """Compute coverage freshness, stale lists, and tracked stats for instrumentation/UI."""
        now = datetime.now(timezone.utc)

        idx_counts: Dict[str, int] = {}
        for idx in ("SP500", "NASDAQ100", "DOW30", "RUSSELL2000"):
            idx_counts[idx] = (
                db.query(IndexConstituent)
                .filter(IndexConstituent.index_name == idx, IndexConstituent.is_active.is_(True))
                .count()
            )

        tracked_list, tracked_from_redis = tracked_symbols_with_source(
            db, redis_client=self._infra._sync_redis
        )
        tracked_total = len(set(tracked_list))
        if tracked_total:
            universe = sorted(set(tracked_list))
        else:
            universe = sorted(
                {
                    str(s).upper()
                    for (s,) in db.query(PriceData.symbol).distinct().all()
                    if s
                }
            )
        total_symbols = len(universe)

        def _fill_by_date(interval: str, days: int | None = None) -> List[Dict[str, Any]]:
            """Return date buckets for 'has OHLCV row on that date' coverage."""
            if not universe or total_symbols == 0:
                return []
            lookback = int(
                days
                if days is not None
                else (
                    int(fill_lookback_days)
                    if fill_lookback_days is not None
                    else getattr(settings, "COVERAGE_FILL_LOOKBACK_DAYS", 90)
                )
            )
            start_dt = (now - timedelta(days=lookback)).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None,
            )
            rows = (
                db.query(
                    func.date(PriceData.date).label("d"),
                    func.count(distinct(PriceData.symbol)).label("symbol_count"),
                )
                .filter(
                    PriceData.interval == interval,
                    PriceData.symbol.in_(set(universe)),
                    PriceData.date >= start_dt,
                )
                .group_by(func.date(PriceData.date))
                .order_by(func.date(PriceData.date).asc())
                .all()
            )
            out: List[Dict[str, Any]] = []
            for d, symbol_count in rows:
                if not d:
                    continue
                n = int(symbol_count or 0)
                out.append(
                    {
                        "date": str(d),
                        "symbol_count": n,
                        "pct_of_universe": round((n / total_symbols) * 100.0, 1) if total_symbols else 0.0,
                    }
                )
            return out

        def _snapshot_fill_by_date(days: int | None = None) -> List[Dict[str, Any]]:
            """Per-date snapshot coverage for technical snapshots (MarketSnapshotHistory ledger)."""
            if not universe or total_symbols == 0:
                return []
            lookback = int(
                days
                if days is not None
                else (
                    int(fill_lookback_days)
                    if fill_lookback_days is not None
                    else getattr(settings, "COVERAGE_FILL_LOOKBACK_DAYS", 90)
                )
            )
            start_dt = (now - timedelta(days=lookback)).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None,
            )
            snap_dt = MarketSnapshotHistory.as_of_date
            rows = (
                db.query(
                    func.date(snap_dt).label("d"),
                    func.count(distinct(MarketSnapshotHistory.symbol)).label("symbol_count"),
                )
                .filter(
                    MarketSnapshotHistory.analysis_type == "technical_snapshot",
                    MarketSnapshotHistory.symbol.in_(set(universe)),
                    snap_dt >= start_dt,
                )
                .group_by(func.date(snap_dt))
                .order_by(func.date(snap_dt).asc())
                .all()
            )
            out: List[Dict[str, Any]] = []
            for d, symbol_count in rows:
                if not d:
                    continue
                n = int(symbol_count or 0)
                out.append(
                    {
                        "date": str(d),
                        "symbol_count": n,
                        "pct_of_universe": round((n / total_symbols) * 100.0, 1) if total_symbols else 0.0,
                    }
                )
            return out

        daily_section, _ = self._compute_interval_coverage_for_symbols(
            db,
            symbols=universe,
            interval="1d",
            now_utc=now,
            return_full_stale=False,
        )
        m5_section, _ = self._compute_interval_coverage_for_symbols(
            db,
            symbols=universe,
            interval="5m",
            now_utc=now,
            return_full_stale=False,
        )

        snapshot = {
            "generated_at": now.isoformat(),
            "symbols": total_symbols,
            "tracked_count": tracked_total if tracked_from_redis else total_symbols,
            "tracked_sample": tracked_list[:10],
            "indices": idx_counts,
            "daily": daily_section,
            "m5": m5_section,
        }
        try:
            snapshot["daily"]["fill_by_date"] = _fill_by_date("1d", days=None)
        except Exception as e:
            logger.warning("coverage_snapshot fill_by_date failed: %s", e)
            snapshot["daily"]["fill_by_date"] = []
        try:
            snapshot["daily"]["snapshot_fill_by_date"] = _snapshot_fill_by_date(days=None)
        except Exception as e:
            logger.warning("coverage_snapshot snapshot_fill_by_date failed: %s", e)
            snapshot["daily"]["snapshot_fill_by_date"] = []
        snapshot["status"] = compute_coverage_status(snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Full API response builder (moved from CoverageService facade)
    # ------------------------------------------------------------------

    COVERAGE_CACHE_SCHEMA_VERSION = 1

    def build_coverage_response(
        self,
        db: Session,
        *,
        fill_trading_days_window: int | None = None,
        fill_lookback_days: int | None = None,
    ) -> Dict[str, Any]:
        """Return coverage summary with cache, history sparkline, KPI cards, and SLA thresholds."""
        snapshot: Dict[str, Any] | None = None
        updated_at: str | None = None
        source = "cache"
        history_entries: List[Dict[str, Any]] = []
        backfill_5m_enabled = self._infra.is_backfill_5m_enabled()

        def _ensure_status(snap: Dict[str, Any]) -> Dict[str, Any]:
            if "status" not in snap or not snap["status"]:
                snap["status"] = compute_coverage_status(snap)
            return snap["status"]

        def _is_valid_cached_payload(payload: Dict[str, Any]) -> bool:
            if not isinstance(payload, dict):
                return False
            if payload.get("schema_version") != self.COVERAGE_CACHE_SCHEMA_VERSION:
                return False
            if not isinstance(payload.get("snapshot"), dict):
                return False
            if not payload.get("updated_at"):
                return False
            return True

        use_cache = fill_lookback_days is None
        if use_cache:
            try:
                raw = self._infra.redis_client.get("coverage:health:last")
                if raw:
                    cached = json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
                    if _is_valid_cached_payload(cached):
                        snapshot = cached.get("snapshot")
                        updated_at = cached.get("updated_at")
                        if snapshot is not None and cached.get("status"):
                            snapshot.setdefault("status", cached["status"])
            except Exception as e:
                logger.warning("Failed to read or parse coverage health cache from Redis: %s", e)
                snapshot = None

        if snapshot is None:
            snapshot = self.coverage_snapshot(
                db,
                fill_lookback_days=fill_lookback_days,
            )
            updated_at = snapshot.get("generated_at")
            source = "db"

        try:
            snapshot.setdefault("meta", {})["backfill_5m_enabled"] = backfill_5m_enabled
        except Exception:
            logger.debug("Failed to set backfill_5m_enabled in coverage meta")

        try:
            bench = self.benchmark_health(db)
            snapshot.setdefault("meta", {})["benchmark"] = {
                "symbol": bench.get("symbol"),
                "latest_daily_date": bench.get("latest_daily_date"),
                "daily_bars": int(bench.get("daily_bars") or 0),
                "required_bars": int(bench.get("required_bars") or 0),
                "ok": bool(bench.get("ok")),
            }
        except Exception as exc:
            logger.exception("Failed to attach benchmark coverage health to snapshot: %s", exc)

        status_info = _ensure_status(snapshot)

        try:
            raw_history = self._infra.redis_client.lrange("coverage:health:history", 0, 47)
            for entry in raw_history or []:
                try:
                    payload = json.loads(entry.decode() if isinstance(entry, (bytes, bytearray)) else entry)
                    history_entries.append(payload)
                except Exception as entry_err:
                    logger.warning("Skipping invalid coverage history Redis entry: %s", entry_err)
                    continue
            if history_entries:
                history_entries = list(reversed(history_entries))
        except Exception as e:
            logger.warning("Failed to load coverage history from Redis: %s", e)
            history_entries = []

        if not history_entries and updated_at:
            history_entries = [
                {
                    "ts": updated_at,
                    "daily_pct": status_info.get("daily_pct"),
                    "m5_pct": status_info.get("m5_pct"),
                    "stale_daily": status_info.get("stale_daily"),
                    "stale_m5": status_info.get("stale_m5"),
                    "label": status_info.get("label"),
                }
            ]

        snapshot["history"] = history_entries

        sparkline_meta = {
            "daily_pct": [float(entry.get("daily_pct") or 0) for entry in history_entries],
            "m5_pct": [float(entry.get("m5_pct") or 0) for entry in history_entries],
            "labels": [entry.get("ts") for entry in history_entries],
            "stale_daily": [int(entry.get("stale_daily") or 0) for entry in history_entries],
            "stale_m5": [int(entry.get("stale_m5") or 0) for entry in history_entries],
        }

        def _kpi_cards() -> List[Dict[str, Any]]:
            tracked = int(snapshot.get("tracked_count") or 0)
            total_symbols = int(snapshot.get("symbols") or 0)
            stale_m5 = int(status_info.get("stale_m5") or 0)
            return [
                {"id": "tracked", "label": "Tracked Symbols", "value": tracked, "help": "Universe size"},
                {"id": "daily_pct", "label": "Daily Coverage %", "value": status_info.get("daily_pct"), "unit": "%", "help": f"{snapshot.get('daily', {}).get('count', 0)} / {total_symbols} bars"},
                {"id": "m5_pct", "label": "5m Coverage %", "value": status_info.get("m5_pct"), "unit": "%", "help": f"{snapshot.get('m5', {}).get('count', 0)} / {total_symbols} bars"},
                {"id": "stale_daily", "label": "Stale (>48h)", "value": status_info.get("stale_daily"), "help": "All 5m covered" if stale_m5 == 0 else f"{stale_m5} missing 5m"},
            ]

        sla_meta = {
            "daily_pct": status_info.get("thresholds", {}).get("daily_pct"),
            "m5_expectation": status_info.get("thresholds", {}).get("m5_expectation"),
        }

        def _clamp_pct(val: Any) -> float:
            try:
                v = float(val or 0)
                return max(0.0, min(100.0, v))
            except Exception as e:
                logger.warning("Could not clamp coverage pct value %r: %s", val, e)
                return 0.0

        status_info["daily_pct"] = _clamp_pct(status_info.get("daily_pct"))
        status_info["m5_pct"] = _clamp_pct(status_info.get("m5_pct"))

        total_symbols = int(snapshot.get("symbols") or 0)
        daily_section = snapshot.get("daily", {}) or {}
        fresh_24 = int(daily_section.get("fresh_24h") or 0)
        fresh_48 = int(daily_section.get("fresh_48h") or 0)
        stale_48h = int(daily_section.get("stale_48h") or 0)
        missing = int(daily_section.get("missing") or (daily_section.get("freshness") or {}).get("none") or 0)
        fresh_gt48 = max(0, total_symbols - fresh_24 - fresh_48 - stale_48h - missing)

        snapshot["daily"] = {
            **daily_section,
            "fresh_24h": fresh_24,
            "fresh_48h": fresh_48,
            "fresh_gt48h": fresh_gt48,
            "stale_48h": stale_48h,
            "missing": missing,
            "count": daily_section.get("count", daily_section.get("daily_count")),
        }

        age_seconds = None
        if updated_at:
            try:
                parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
            except Exception as e:
                logger.warning("coverage snapshot_age parse failed for updated_at=%r: %s", updated_at, e)
                age_seconds = None

        meta = snapshot.setdefault("meta", {})
        meta["sparkline"] = sparkline_meta
        meta["kpis"] = _kpi_cards()
        meta["sla"] = sla_meta
        meta["snapshot_age_seconds"] = age_seconds
        meta["source"] = source
        meta["updated_at"] = updated_at
        meta["history"] = history_entries
        meta["backfill_5m_enabled"] = backfill_5m_enabled
        meta["fill_lookback_days"] = int(
            int(fill_lookback_days) if fill_lookback_days is not None
            else getattr(settings, "COVERAGE_FILL_LOOKBACK_DAYS", 90)
        )
        meta["fill_trading_days_window"] = int(
            int(fill_trading_days_window) if fill_trading_days_window is not None
            else getattr(settings, "COVERAGE_FILL_TRADING_DAYS_WINDOW", 50)
        )

        return snapshot
