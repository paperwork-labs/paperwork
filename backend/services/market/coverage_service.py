from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.config import settings
from backend.services.market.coverage_utils import compute_coverage_status

logger = logging.getLogger(__name__)

COVERAGE_CACHE_SCHEMA_VERSION = 1

class CoverageService:
    """Coverage and health facade for MarketDataService."""

    def __init__(self, service) -> None:
        self._service = service

    def is_backfill_5m_enabled(self) -> bool:
        return self._service.is_backfill_5m_enabled()

    def benchmark_health(self, db, benchmark_symbol: str = "SPY", required_bars=None, latest_daily_dt=None):
        return self._service.benchmark_health(
            db,
            benchmark_symbol=benchmark_symbol,
            required_bars=required_bars,
            latest_daily_dt=latest_daily_dt,
        )

    def coverage_snapshot(self, db, *, fill_lookback_days=None):
        return self._service.coverage_snapshot(db, fill_lookback_days=fill_lookback_days)

    def compute_interval_coverage_for_symbols(
        self,
        db,
        *,
        symbols: List[str],
        interval: str,
        now_utc=None,
        stale_sample_limit=None,
        return_full_stale: bool = False,
    ):
        return self._service._compute_interval_coverage_for_symbols(
            db,
            symbols=symbols,
            interval=interval,
            now_utc=now_utc,
            stale_sample_limit=stale_sample_limit,
            return_full_stale=return_full_stale,
        )

    def build_coverage_response(
        self,
        db,
        *,
        fill_trading_days_window: int | None = None,
        fill_lookback_days: int | None = None,
    ) -> Dict[str, Any]:
        """Return coverage summary across intervals with last bar timestamps and freshness buckets."""
        snapshot: Dict[str, Any] | None = None
        updated_at: str | None = None
        source = "cache"
        history_entries: List[Dict[str, Any]] = []
        backfill_5m_enabled = self.is_backfill_5m_enabled()

        def _ensure_status(snap: Dict[str, Any]) -> Dict[str, Any]:
            if "status" not in snap or not snap["status"]:
                snap["status"] = compute_coverage_status(snap)
            return snap["status"]

        def _is_valid_cached_payload(payload: Dict[str, Any]) -> bool:
            if not isinstance(payload, dict):
                return False
            if payload.get("schema_version") != COVERAGE_CACHE_SCHEMA_VERSION:
                return False
            if not isinstance(payload.get("snapshot"), dict):
                return False
            if not payload.get("updated_at"):
                return False
            return True

        use_cache = fill_lookback_days is None
        if use_cache:
            try:
                raw = self._service.redis_client.get("coverage:health:last")
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

        # Ensure downstream status logic can see the 5m toggle (for ignore-5m behavior).
        try:
            snapshot.setdefault("meta", {})["backfill_5m_enabled"] = backfill_5m_enabled
        except Exception:
            logger.debug("Failed to set backfill_5m_enabled in coverage meta")

        # Attach benchmark (SPY) health for UI diagnostics.
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
            # Benchmark diagnostics are optional; log failures but do not break the snapshot.
            logger.exception("Failed to attach benchmark coverage health to snapshot: %s", exc)

        status_info = _ensure_status(snapshot)

        try:
            raw_history = self._service.redis_client.lrange("coverage:health:history", 0, 47)
            for entry in raw_history or []:
                try:
                    payload = json.loads(entry.decode() if isinstance(entry, (bytes, bytearray)) else entry)
                    history_entries.append(payload)
                except Exception as entry_err:
                    logger.warning(
                        "Skipping invalid coverage history Redis entry: %s",
                        entry_err,
                    )
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
                {
                    "id": "tracked",
                    "label": "Tracked Symbols",
                    "value": tracked,
                    "help": "Universe size",
                },
                {
                    "id": "daily_pct",
                    "label": "Daily Coverage %",
                    "value": status_info.get("daily_pct"),
                    "unit": "%",
                    "help": f"{snapshot.get('daily', {}).get('count', 0)} / {total_symbols} bars",
                },
                {
                    "id": "m5_pct",
                    "label": "5m Coverage %",
                    "value": status_info.get("m5_pct"),
                    "unit": "%",
                    "help": f"{snapshot.get('m5', {}).get('count', 0)} / {total_symbols} bars",
                },
                {
                    "id": "stale_daily",
                    "label": "Stale (>48h)",
                    "value": status_info.get("stale_daily"),
                    "help": "All 5m covered" if stale_m5 == 0 else f"{stale_m5} missing 5m",
                },
            ]

        sla_meta = {
            "daily_pct": status_info.get("thresholds", {}).get("daily_pct"),
            "m5_expectation": status_info.get("thresholds", {}).get("m5_expectation"),
        }

        # Clamp pct and rebuild freshness buckets
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
                logger.warning(
                    "coverage snapshot_age parse failed for updated_at=%r: %s",
                    updated_at,
                    e,
                )
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
            int(fill_lookback_days)
            if fill_lookback_days is not None
            else getattr(settings, "COVERAGE_FILL_LOOKBACK_DAYS", 90)
        )
        meta["fill_trading_days_window"] = int(
            int(fill_trading_days_window)
            if fill_trading_days_window is not None
            else getattr(settings, "COVERAGE_FILL_TRADING_DAYS_WINDOW", 50)
        )

        return snapshot
