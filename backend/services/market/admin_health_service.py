"""
Admin Health Service -- Composite health aggregation.

Composes coverage, stage quality, jobs, audit, fundamentals, regime, data accuracy,
and task-run data into a single response so the Admin Dashboard needs only one fetch.

Mode-aware: when market_only_mode is true (AppSettings), broker dimensions
(portfolio_sync, ibkr_gateway) are advisory and excluded from composite scoring.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.market.market_data_service import coverage_analytics, infra, stage_quality

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds -- tune here, not scattered across code
# ---------------------------------------------------------------------------
HEALTH_THRESHOLDS: Dict[str, float] = {
    "coverage_daily_pct_min": 95.0,
    "coverage_stale_daily_max": 25,
    "stage_unknown_rate_max": 0.35,
    "stage_invalid_max": 0,
    "stage_monotonicity_max": 15,
    "jobs_success_rate_min": 0.90,
    "jobs_lookback_hours": 24,
    "audit_daily_fill_pct_min": 95.0,
    "audit_snapshot_fill_pct_min": 90.0,
    "fundamentals_fill_pct_pass": 80.0,
    "fundamentals_fill_pct_warn": 50.0,
    "data_accuracy_mismatch_max": 5,
    "data_accuracy_max_age_days": 10,
}

MARKET_DIMS = {"coverage", "stage_quality", "jobs", "audit", "regime", "fundamentals", "data_accuracy"}
BROKER_DIMS = {"portfolio_sync", "ibkr_gateway"}
# G28: deploys dim is infra-level — not part of the market/broker split.
# It still counts toward composite; a red deploy dim must surface regardless
# of market_only_mode (a stuck API deploy breaks everything).
INFRA_DIMS = {"deploys"}

_COMPOSITE_HEALTH_CACHE_KEY = "admin:composite_health"
_COMPOSITE_HEALTH_TTL_S = 60

# Task-status keys we pull from Redis for the Agent Activity panel.
_TASK_STATUS_KEYS: List[str] = sorted({
    "admin_backfill_5m",
    "admin_backfill_daily",
    "admin_backfill_daily_since_date",
    "admin_backfill_daily_symbols",
    "admin_backfill_since_date",
    "admin_coverage_backfill",
    "admin_coverage_backfill_stale",
    "admin_coverage_refresh",
    "admin_indicators_recompute_universe",
    "admin_market_data_audit",
    "admin_recover_stale_job_runs",
    "admin_snapshots_history_backfill",
    "admin_snapshots_history_backfill_date",
    "admin_snapshots_history_record",
    "auto_ops_health_check",
    "compute_daily_regime",
    "market_indices_constituents_refresh",
    "market_snapshots_fundamentals_fill",
    "ohlcv_reconciliation",
    "market_universe_tracked_refresh",
})


def _dim_status(ok: bool) -> str:
    return "green" if ok else "red"


def _composite_dimension_ok(status: Optional[str]) -> bool:
    """True if dimension passes composite aggregation.

    Accepts green/ok (fully healthy) and yellow/warning (degraded but operational).
    """
    return status in ("green", "ok", "yellow", "warning")


class AdminHealthService:
    """Aggregates all health dimensions into one response."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_composite_health(self, db: Session) -> Dict[str, Any]:
        r = infra.redis_client
        try:
            raw = r.get(_COMPOSITE_HEALTH_CACHE_KEY)
            if raw:
                return json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
        except Exception as e:
            logger.warning("composite health cache read failed: %s", e)

        payload = self._compute_composite_health(db)
        try:
            r.setex(
                _COMPOSITE_HEALTH_CACHE_KEY,
                _COMPOSITE_HEALTH_TTL_S,
                json.dumps(payload),
            )
        except Exception as e:
            logger.warning("composite health cache write failed: %s", e)
        return payload

    def _compute_composite_health(self, db: Session) -> Dict[str, Any]:
        from backend.services.core.app_settings_service import get_or_create_app_settings

        coverage = self._build_coverage_dimension(db)
        stage = self._build_stage_dimension(db)
        jobs = self._build_jobs_dimension(db)
        audit = self._build_audit_dimension(db)
        regime = self._build_regime_dimension(db)
        fundamentals = self._build_fundamentals_dimension(db)
        portfolio_sync = self._build_portfolio_sync_dimension(db)
        ibkr_gateway = self._build_ibkr_gateway_dimension()
        data_accuracy = self._build_data_accuracy_dimension()
        deploys = self._build_deploys_dimension(db)
        task_runs = self._build_task_runs()

        market_only = True
        try:
            app_settings = get_or_create_app_settings(db)
            market_only = bool(app_settings.market_only_mode)
        except Exception as e:
            logger.warning("Failed to read app_settings for market_only_mode: %s", e)

        dims: Dict[str, Any] = {
            "coverage": coverage,
            "stage_quality": stage,
            "jobs": jobs,
            "audit": audit,
            "regime": regime,
            "fundamentals": fundamentals,
            "data_accuracy": data_accuracy,
            "portfolio_sync": portfolio_sync,
            "ibkr_gateway": ibkr_gateway,
            "deploys": deploys,
        }

        for name in dims:
            if name in MARKET_DIMS:
                dims[name]["category"] = "market"
            elif name in INFRA_DIMS:
                dims[name]["category"] = "infra"
            else:
                dims[name]["category"] = "broker"

        if market_only:
            for name in BROKER_DIMS:
                dims[name]["advisory"] = True

        # Composite scoring: always include market + infra dims; broker dims
        # are excluded in market_only_mode. Deploys must never be advisory —
        # a stuck build pipeline breaks market AND broker syncs alike.
        scored_dims = (
            dims
            if not market_only
            else {k: v for k, v in dims.items() if k in MARKET_DIMS or k in INFRA_DIMS}
        )
        failures = [name for name, dim in scored_dims.items() if not _composite_dimension_ok(dim.get("status"))]

        if not failures:
            composite_status = "green"
            composite_reason = "All health dimensions pass."
        elif len(failures) >= 2:
            composite_status = "red"
            composite_reason = f"Multiple failures: {', '.join(failures)}."
        else:
            composite_status = "yellow"
            composite_reason = f"Degraded: {failures[0]}."

        return {
            "composite_status": composite_status,
            "composite_reason": composite_reason,
            "market_only_mode": market_only,
            "dimensions": dims,
            "task_runs": task_runs,
            "thresholds": dict(HEALTH_THRESHOLDS),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "provider_metrics": self._build_provider_metrics() or None,
        }

    def check_pre_market_readiness(self, db: Session) -> Dict[str, Any]:
        """Check if the system is ready for the next trading session.

        Validates:
        - Daily bars exist for previous trading day (>95% of tracked symbols)
        - Indicators recomputed (snapshot age < 12 hours)
        - Regime computed (age < 48 hours)
        """
        from backend.services.market.market_data_service import _last_n_trading_sessions

        gaps: List[str] = []
        sessions = _last_n_trading_sessions(1)
        last_session = sessions[0] if sessions else None

        coverage = self._build_coverage_dimension(db)
        daily_pct = float(coverage.get("daily_pct", 0))
        if daily_pct < 95.0:
            gaps.append(f"Daily coverage at {daily_pct:.1f}% (need 95%)")

        audit = self._build_audit_dimension(db)
        snapshot_fill = float(audit.get("snapshot_fill_pct", 0))
        if snapshot_fill < 90.0:
            gaps.append(f"Snapshot fill at {snapshot_fill:.1f}% (need 90%)")

        regime = self._build_regime_dimension(db)
        age_hours = float(regime.get("age_hours", 999))
        if age_hours > 48:
            gaps.append(f"Regime is {age_hours:.0f}h old (need <48h)")

        ready = len(gaps) == 0
        result = {
            "ready": ready,
            "gaps": gaps,
            "last_trading_session": str(last_session) if last_session else None,
            "daily_pct": daily_pct,
            "snapshot_fill_pct": snapshot_fill,
            "regime_age_hours": round(age_hours, 1),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            infra.redis_client.setex(
                "health:pre_market_readiness",
                1800,
                json.dumps(result),
            )
        except Exception as e:
            logger.warning("Failed to cache pre-market readiness result: %s", e)

        return result

    # ------------------------------------------------------------------
    # Dimension builders
    # ------------------------------------------------------------------

    def _build_coverage_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            from backend.services.market.coverage_utils import compute_coverage_status

            snapshot = coverage_analytics.coverage_snapshot(db)
            status_info = compute_coverage_status(snapshot)
            daily_pct = float(status_info.get("daily_pct") or 0)
            stale_daily = int(status_info.get("stale_daily") or 0)
            ok = (
                daily_pct >= HEALTH_THRESHOLDS["coverage_daily_pct_min"]
                and stale_daily <= HEALTH_THRESHOLDS["coverage_stale_daily_max"]
            )

            indices = snapshot.get("indices", {})
            constituent_issues: List[str] = []
            tracked_indices = ["SP500", "NASDAQ100", "DOW30", "RUSSELL2000"]
            for idx_name in tracked_indices:
                idx_value = indices.get(idx_name)
                if isinstance(idx_value, dict):
                    count = int(idx_value.get("count") or 0)
                elif isinstance(idx_value, (int, float)):
                    count = int(idx_value)
                else:
                    count = 0
                if count == 0:
                    constituent_issues.append(idx_name)

            if constituent_issues:
                ok = False

            curated_etf_count = 0
            try:
                from backend.services.market.constants import CURATED_MARKET_SYMBOLS
                curated_etf_count = len(CURATED_MARKET_SYMBOLS)
            except Exception:
                logger.debug("Failed to read CURATED_MARKET_SYMBOLS for ETF count")

            return {
                "status": _dim_status(ok),
                "daily_pct": daily_pct,
                "m5_pct": float(status_info.get("m5_pct") or 0),
                "stale_daily": stale_daily,
                "stale_m5": int(status_info.get("stale_m5") or 0),
                "tracked_count": int(status_info.get("tracked_count") or 0),
                "expected_date": status_info.get("daily_expected_date"),
                "summary": status_info.get("summary", ""),
                "indices": indices,
                "constituent_issues": constituent_issues,
                "providers": self._check_provider_keys(),
                "curated_etf_count": curated_etf_count,
            }
        except Exception as exc:
            logger.exception("coverage dimension failed: %s", exc)
            return {"status": "red", "error": str(exc)}

    def _build_stage_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            data = stage_quality.stage_quality_summary(db, lookback_days=120)
            unknown_rate = float(data.get("unknown_rate") or 0)
            invalid_count = int(data.get("invalid_stage_count") or 0)
            monotonicity = int(data.get("monotonicity_issues") or 0)
            ok = (
                unknown_rate <= HEALTH_THRESHOLDS["stage_unknown_rate_max"]
                and invalid_count <= HEALTH_THRESHOLDS["stage_invalid_max"]
                and monotonicity <= HEALTH_THRESHOLDS["stage_monotonicity_max"]
            )
            return {
                "status": _dim_status(ok),
                "unknown_rate": round(unknown_rate, 4),
                "invalid_count": invalid_count,
                "monotonicity_issues": monotonicity,
                "stale_stage_count": int(data.get("stale_stage_count") or 0),
                "total_symbols": int(data.get("total_symbols") or 0),
                "stage_counts": data.get("stage_counts", {}),
            }
        except Exception as exc:
            logger.exception("stage dimension failed: %s", exc)
            return {"status": "red", "error": str(exc)}

    def _build_jobs_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            from backend.models.market_data import JobRun

            lookback = int(HEALTH_THRESHOLDS["jobs_lookback_hours"])
            since = datetime.now(timezone.utc) - timedelta(hours=lookback)
            base = db.query(JobRun).filter(JobRun.started_at >= since)

            status_rows = (
                base.with_entities(JobRun.status, func.count())
                .group_by(JobRun.status)
                .all()
            )
            by_status = {row[0]: int(row[1]) for row in status_rows if row[0] is not None}
            total = sum(by_status.values())
            ok_count = by_status.get("ok", 0)
            error_count = by_status.get("error", 0)
            running_count = by_status.get("running", 0)
            cancelled_count = by_status.get("cancelled", 0)
            completed = ok_count + error_count + cancelled_count
            success_rate = (ok_count / completed) if completed else 0.0

            latest_failed = (
                base.filter(JobRun.status == "error")
                .order_by(JobRun.started_at.desc())
                .first()
            )

            ok = (completed == 0) or (success_rate >= HEALTH_THRESHOLDS["jobs_success_rate_min"])

            return {
                "status": _dim_status(ok),
                "window_hours": lookback,
                "total": total,
                "ok_count": ok_count,
                "error_count": error_count,
                "running_count": running_count,
                "cancelled_count": cancelled_count,
                "completed_count": completed,
                "success_rate": round(success_rate, 4),
                "latest_failed": (
                    {
                        "id": latest_failed.id,
                        "task_name": latest_failed.task_name,
                        "status": latest_failed.status,
                        "started_at": (
                            latest_failed.started_at.isoformat()
                            if latest_failed.started_at
                            else None
                        ),
                        "error": latest_failed.error,
                    }
                    if latest_failed
                    else None
                ),
            }
        except Exception as exc:
            logger.exception("jobs dimension failed: %s", exc)
            return {"status": "red", "error": str(exc)}

    def _build_regime_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            from backend.models.market_data import MarketRegime

            latest = (
                db.query(MarketRegime)
                .order_by(MarketRegime.as_of_date.desc())
                .first()
            )
            if latest is None:
                return {"status": "red", "error": "no regime data computed"}

            age_hours = 0.0
            if latest.as_of_date:
                as_of = latest.as_of_date
                if as_of.tzinfo is None:
                    as_of = as_of.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - as_of).total_seconds() / 3600

            ok = age_hours < 48
            return {
                "status": _dim_status(ok),
                "regime_state": latest.regime_state,
                "composite_score": latest.composite_score,
                "as_of_date": latest.as_of_date.isoformat() if latest.as_of_date else None,
                "age_hours": round(age_hours, 1),
                "multiplier": latest.regime_multiplier,
                "max_equity_pct": latest.max_equity_exposure_pct,
                "cash_floor_pct": latest.cash_floor_pct,
            }
        except Exception as exc:
            logger.exception("regime dimension failed: %s", exc)
            return {"status": "red", "error": str(exc)}

    _AUDIT_CACHE_KEY = "market_audit:computed"
    _AUDIT_CACHE_TTL = 300  # 5 minutes

    def compute_audit_metrics(self, db: Session) -> Dict[str, Any]:
        """Canonical audit computation — single source of truth.

        Queries DB directly with analysis_type='technical_snapshot' filter
        (matching the /coverage/sanity endpoint). Results cached in Redis
        for 5 min. Called by _build_audit_dimension and by the audit_quality
        Celery task (cache-warmer).
        """
        from backend.models.market_data import PriceData, MarketSnapshotHistory
        from backend.services.market.universe import tracked_symbols_with_source

        tracked_list, _ = tracked_symbols_with_source(
            db, redis_client=infra.redis_client
        )
        tracked_set = {str(s).upper() for s in (tracked_list or []) if s}
        tracked_total = len(tracked_set)

        latest_daily_dt = (
            db.query(func.max(PriceData.date))
            .filter(PriceData.interval == "1d")
            .scalar()
        )
        daily_count = 0
        if latest_daily_dt and tracked_set:
            daily_count = (
                db.query(func.count(distinct(PriceData.symbol)))
                .filter(
                    PriceData.interval == "1d",
                    PriceData.symbol.in_(tracked_set),
                    func.date(PriceData.date) == func.date(latest_daily_dt),
                )
                .scalar()
            ) or 0

        latest_hist_dt = (
            db.query(func.max(MarketSnapshotHistory.as_of_date))
            .filter(MarketSnapshotHistory.analysis_type == "technical_snapshot")
            .scalar()
        )
        hist_count = 0
        missing_sample: List[str] = []
        if latest_hist_dt and tracked_set:
            hist_syms = (
                db.query(MarketSnapshotHistory.symbol)
                .filter(
                    MarketSnapshotHistory.analysis_type == "technical_snapshot",
                    MarketSnapshotHistory.symbol.in_(tracked_set),
                    func.date(MarketSnapshotHistory.as_of_date) == func.date(latest_hist_dt),
                )
                .distinct()
                .all()
            )
            hist_set = {s[0].upper() for s in hist_syms if s and s[0]}
            hist_count = len(hist_set)
            missing_sample = sorted(list(tracked_set - hist_set))[:20]

        daily_fill = round((int(daily_count) / tracked_total) * 100.0, 1) if tracked_total else 0.0
        snapshot_fill = round((hist_count / tracked_total) * 100.0, 1) if tracked_total else 0.0

        history_depth_years: Optional[float] = None
        earliest_date_str: Optional[str] = None
        ohlcv_earliest_str: Optional[str] = None
        ohlcv_symbol_count: Optional[int] = None
        try:
            earliest = (
                db.query(func.min(MarketSnapshotHistory.as_of_date))
                .filter(MarketSnapshotHistory.analysis_type == "technical_snapshot")
                .scalar()
            )
            if earliest:
                if hasattr(earliest, "date"):
                    earliest_date = earliest.date() if callable(earliest.date) else earliest.date
                else:
                    earliest_date = earliest
                earliest_date_str = earliest_date.isoformat()
                from datetime import date as _date
                delta = _date.today() - earliest_date
                history_depth_years = round(delta.days / 365.25, 1)

            ohlcv_min = db.query(func.min(PriceData.date)).filter(PriceData.interval == "1d").scalar()
            if ohlcv_min:
                ohlcv_earliest_str = (ohlcv_min.date() if callable(getattr(ohlcv_min, "date", None)) else ohlcv_min).isoformat()
            ohlcv_symbol_count = db.query(func.count(func.distinct(PriceData.symbol))).filter(PriceData.interval == "1d").scalar()
        except Exception:
            logger.debug("Failed to compute history depth / OHLCV depth in audit metrics")

        payload = {
            "tracked_total": tracked_total,
            "latest_daily_date": latest_daily_dt.isoformat() if hasattr(latest_daily_dt, "isoformat") else str(latest_daily_dt) if latest_daily_dt else None,
            "latest_daily_symbol_count": int(daily_count),
            "daily_fill_pct": daily_fill,
            "latest_snapshot_history_date": latest_hist_dt.isoformat() if hasattr(latest_hist_dt, "isoformat") else str(latest_hist_dt) if latest_hist_dt else None,
            "latest_snapshot_history_symbol_count": hist_count,
            "snapshot_fill_pct": snapshot_fill,
            "missing_snapshot_history_sample": missing_sample,
            "history_depth_years": history_depth_years,
            "earliest_date": earliest_date_str,
            "ohlcv_earliest_date": ohlcv_earliest_str,
            "ohlcv_symbol_count": ohlcv_symbol_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            infra.redis_client.set(
                self._AUDIT_CACHE_KEY, json.dumps(payload), ex=self._AUDIT_CACHE_TTL
            )
        except Exception as e:
            logger.warning("audit cache write failed: %s", e)

        return payload

    def _build_audit_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            raw = infra.redis_client.get(self._AUDIT_CACHE_KEY)
            if raw:
                payload = json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
            else:
                payload = self.compute_audit_metrics(db)

            daily_fill = float(payload.get("daily_fill_pct", 0))
            snapshot_fill = float(payload.get("snapshot_fill_pct", 0))

            ok = (
                daily_fill >= HEALTH_THRESHOLDS["audit_daily_fill_pct_min"]
                and snapshot_fill >= HEALTH_THRESHOLDS["audit_snapshot_fill_pct_min"]
            )

            return {
                "status": _dim_status(ok),
                "tracked_total": payload.get("tracked_total"),
                "daily_fill_pct": round(daily_fill, 1),
                "snapshot_fill_pct": round(snapshot_fill, 1),
                "missing_sample": payload.get("missing_snapshot_history_sample", [])[:5],
                "history_depth_years": payload.get("history_depth_years"),
                "earliest_date": payload.get("earliest_date"),
                "ohlcv_earliest_date": payload.get("ohlcv_earliest_date"),
                "ohlcv_symbol_count": payload.get("ohlcv_symbol_count"),
            }
        except Exception as exc:
            logger.exception("audit dimension failed: %s", exc)
            return {"status": "red", "error": str(exc)}

    def _build_fundamentals_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            from backend.models.market_data import MarketSnapshot
            from backend.services.market.universe import tracked_symbols_with_source

            tracked_list, _ = tracked_symbols_with_source(
                db, redis_client=infra.redis_client
            )
            universe = sorted({str(s).upper() for s in (tracked_list or []) if s})
            total = len(universe)
            if total == 0:
                return {
                    "status": "error",
                    "error": "no tracked symbols",
                    "fundamentals_fill_pct": 0.0,
                    "tracked_total": 0,
                    "filled_count": 0,
                }

            filled = (
                db.query(func.count(distinct(MarketSnapshot.symbol)))
                .filter(
                    MarketSnapshot.analysis_type == "technical_snapshot",
                    MarketSnapshot.symbol.in_(universe),
                    MarketSnapshot.sector.isnot(None),
                )
                .scalar()
            )
            filled_n = int(filled or 0)
            pct = (float(filled_n) / float(total)) * 100.0

            pass_pct = float(HEALTH_THRESHOLDS["fundamentals_fill_pct_pass"])
            warn_pct = float(HEALTH_THRESHOLDS["fundamentals_fill_pct_warn"])
            if pct >= pass_pct:
                st = "ok"
            elif pct >= warn_pct:
                st = "warning"
            else:
                st = "error"

            return {
                "status": st,
                "fundamentals_fill_pct": round(pct, 1),
                "tracked_total": total,
                "filled_count": filled_n,
            }
        except Exception as exc:
            logger.exception("fundamentals dimension failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def _build_data_accuracy_dimension(self) -> Dict[str, Any]:
        """Data accuracy from OHLCV spot-check reconciliation results."""
        try:
            r = infra.redis_client
            raw = r.get("ohlcv:reconciliation:last")
            if not raw:
                return {
                    "status": "yellow",
                    "note": "reconciliation has not run yet",
                    "mismatch_count": 0,
                    "bars_checked": 0,
                    "bars_matched": 0,
                    "match_rate": 0.0,
                    "missing_in_db": 0,
                    "sample_size": 0,
                    "checked_at": None,
                    "age_days": None,
                    "mismatches": [],
                }
            data = json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)

            mismatch_count = int(data.get("mismatch_count", 0))
            max_mismatches = int(HEALTH_THRESHOLDS["data_accuracy_mismatch_max"])
            max_age_days = int(HEALTH_THRESHOLDS["data_accuracy_max_age_days"])

            checked_at = data.get("checked_at")
            age_days = 999
            if checked_at:
                try:
                    checked_dt = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
                    if checked_dt.tzinfo is None:
                        checked_dt = checked_dt.replace(tzinfo=timezone.utc)
                    age_days = (datetime.now(timezone.utc) - checked_dt).days
                except Exception:
                    logger.debug("Failed to parse checked_at timestamp for age calculation")

            if age_days > max_age_days:
                status = "red"
            elif mismatch_count > max_mismatches:
                status = "red"
            elif mismatch_count > 0:
                status = "yellow"
            else:
                status = "green"

            return {
                "status": status,
                "mismatch_count": mismatch_count,
                "bars_checked": int(data.get("bars_checked", 0)),
                "bars_matched": int(data.get("bars_matched", 0)),
                "match_rate": float(data.get("match_rate", 0)),
                "missing_in_db": int(data.get("missing_in_db", 0)),
                "sample_size": int(data.get("sample_size", 0)),
                "checked_at": checked_at,
                "age_days": age_days,
                "mismatches": data.get("mismatches", [])[:10],
            }
        except Exception as exc:
            logger.warning("data_accuracy dimension failed: %s", exc)
            return {
                "status": "yellow",
                "note": f"check failed: {exc}",
                "error": str(exc),
                "mismatch_count": 0,
                "bars_checked": 0,
                "bars_matched": 0,
                "match_rate": 0.0,
                "missing_in_db": 0,
                "sample_size": 0,
                "checked_at": None,
                "age_days": None,
                "mismatches": [],
            }

    def _build_portfolio_sync_dimension(self, db: Session) -> Dict[str, Any]:
        """Check if broker accounts have synced recently (within 24h)."""
        try:
            from backend.models import BrokerAccount

            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            accounts = db.query(BrokerAccount).filter(
                BrokerAccount.is_enabled.is_(True)
            ).all()

            if not accounts:
                return {
                    "status": "ok",
                    "total_accounts": 0,
                    "stale_accounts": 0,
                    "stale_list": [],
                    "note": "no broker accounts configured",
                }

            stale = [
                a for a in accounts
                if not a.last_successful_sync or a.last_successful_sync < cutoff
            ]

            return {
                "status": "green" if not stale else "red",
                "total_accounts": len(accounts),
                "stale_accounts": len(stale),
                "stale_list": [a.account_number for a in stale[:5]],
            }
        except Exception as exc:
            logger.exception("portfolio_sync dimension failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def _build_ibkr_gateway_dimension(self) -> Dict[str, Any]:
        """Check IBKR Gateway connection status.
        
        Uses the connection_health property from the IBKR client which is
        updated by the ibkr_watchdog task.
        """
        try:
            from backend.services.clients.ibkr_client import ibkr_client
            
            health = getattr(ibkr_client, "connection_health", {})
            status = health.get("status", "unknown")
            last_ping = health.get("last_ping")
            
            # Check if last ping was recent (within 10 minutes)
            is_stale = True
            if last_ping:
                try:
                    if isinstance(last_ping, str):
                        last_ping_dt = datetime.fromisoformat(last_ping.replace("Z", "+00:00"))
                    else:
                        last_ping_dt = last_ping
                    if last_ping_dt.tzinfo is None:
                        last_ping_dt = last_ping_dt.replace(tzinfo=timezone.utc)
                    is_stale = (datetime.now(timezone.utc) - last_ping_dt) > timedelta(minutes=10)
                except Exception:
                    logger.debug("Failed to parse last_ping timestamp for staleness check")
            
            if status == "connected" and not is_stale:
                dim_status = "green"
            elif status in ("connected", "reconnected"):
                dim_status = "yellow"  # Connected but stale ping
            else:
                dim_status = "red"
            
            return {
                "status": dim_status,
                "connection_status": status,
                "last_ping": str(last_ping) if last_ping else None,
                "is_stale": is_stale,
            }
        except Exception as exc:
            logger.warning("ibkr_gateway dimension failed: %s", exc)
            return {"status": "yellow", "error": str(exc), "note": "IBKR client not available"}

    def _build_deploys_dimension(self, db: Session) -> Dict[str, Any]:
        """Build the deploys dimension payload (G28, D120).

        Reads ``DEPLOY_HEALTH_SERVICE_IDS`` from settings (comma-separated
        Render service ids) and aggregates :class:`DeployHealthEvent`
        rows via :func:`summarize_composite`.

        Never raises — the composite aggregator must remain resilient even
        if the deploys model / migration is not yet applied.
        """
        try:
            from backend.services.deploys.poll_service import summarize_composite
            from backend.services.deploys.service_resolver import resolve_services

            services = resolve_services()
            payload = summarize_composite(db, services)
            return payload
        except Exception as exc:
            logger.warning("deploys dimension failed: %s", exc)
            return {
                "status": "yellow",
                "reason": f"deploy-health telemetry unavailable: {exc}",
                "services": [],
                "consecutive_failures_max": 0,
                "failures_24h_total": 0,
            }

    def _build_task_runs(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        try:
            r = infra.redis_client
            keys = [f"taskstatus:{tn}:last" for tn in _TASK_STATUS_KEYS]
            values = r.mget(keys)
            for task_name, raw in zip(_TASK_STATUS_KEYS, values):
                try:
                    out[task_name] = json.loads(raw) if raw else None
                except Exception as e:
                    logger.warning("failed to parse task status for %s: %s", task_name, e)
                    out[task_name] = None
        except Exception as exc:
            logger.exception("task runs load failed: %s", exc)
        return out

    # ------------------------------------------------------------------
    # Provider metrics
    # ------------------------------------------------------------------

    def _build_provider_metrics(self) -> Dict[str, Any]:
        """Read today's provider call counters from Redis."""
        try:
            r = infra.redis_client
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            raw = r.hgetall(f"provider:calls:{date_key}")
            if not raw:
                return {}
            counters = {}
            for k, v in raw.items():
                key = k.decode() if isinstance(k, bytes) else k
                val = int(v.decode() if isinstance(v, bytes) else v)
                counters[key] = val

            budgets = {
                "fmp": settings.provider_policy.fmp_daily_budget,
                "twelvedata": settings.provider_policy.twelvedata_daily_budget,
                "yfinance": settings.provider_policy.yfinance_daily_budget,
            }

            l1_hits = counters.get("l1_hit", 0)
            l2_hits = counters.get("l2_hit", 0)
            api_calls = sum(v for k, v in counters.items() if k not in ("l1_hit", "l2_hit"))
            total_requests = l1_hits + l2_hits + api_calls

            providers = {}
            for name in ("fmp", "twelvedata", "yfinance", "finnhub"):
                calls = counters.get(name, 0)
                budget = budgets.get(name, 10000)
                providers[name] = {
                    "calls": calls,
                    "budget": budget,
                    "pct": round((calls / budget) * 100, 1) if budget > 0 else 0,
                }

            result = {
                "providers": providers,
                "l1_hits": l1_hits,
                "l2_hits": l2_hits,
                "api_calls": api_calls,
                "total_requests": total_requests,
                "l2_hit_rate": round((l2_hits / max(l2_hits + api_calls, 1)) * 100, 1),
                "cache_hit_rate": round(((l1_hits + l2_hits) / max(total_requests, 1)) * 100, 1),
                "date": date_key,
                "policy_tier": settings.MARKET_PROVIDER_POLICY,
            }

            fmp_7d_total = 0
            from datetime import timedelta
            for i in range(7):
                day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
                redis_key = f"provider:calls:{day}"
                try:
                    day_val = r.hget(redis_key, "fmp")
                    if day_val:
                        fmp_7d_total += int(day_val.decode() if isinstance(day_val, bytes) else day_val)
                except Exception as exc:
                    logger.debug("failed to read provider metrics for day=%s key=%s: %s", day, redis_key, exc)
            result["fmp_7d_total"] = fmp_7d_total

            return result
        except Exception as exc:
            logger.warning("provider metrics build failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Provider key health probe
    # ------------------------------------------------------------------

    _PROVIDER_PROBE_CACHE_KEY = "health:provider_keys"
    _PROVIDER_PROBE_TTL = 1800  # 30 min

    def _check_provider_keys(self) -> Dict[str, str]:
        """Return cached provider key health status.

        The probe is populated by auto_remediate_health (Celery) which runs
        every 15 min.  On the API request path we only read the cache —
        never make outbound HTTP calls that could block the event loop.
        """
        r = infra.redis_client
        try:
            cached = r.get(self._PROVIDER_PROBE_CACHE_KEY)
            if cached:
                return json.loads(cached if isinstance(cached, str) else cached.decode())
        except Exception:
            logger.debug("Failed to read provider probe cache")
        return {"fmp": "unchecked", "finnhub": "unchecked"}

    def refresh_provider_probe(self) -> Dict[str, str]:
        """Actually probe provider APIs and cache the result.

        Called from sync Celery context (auto_ops), NOT from the API path.
        """
        r = infra.redis_client
        result: Dict[str, str] = {}

        if getattr(settings, "FMP_API_KEY", None):
            try:
                import httpx
                resp = httpx.get(
                    f"https://financialmodelingprep.com/stable/quote?symbol=SPY&apikey={settings.FMP_API_KEY}",
                    timeout=10,
                )
                result["fmp"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
            except Exception as exc:
                result["fmp"] = f"error: {exc}"
        else:
            result["fmp"] = "not_configured"

        if getattr(settings, "FINNHUB_API_KEY", None):
            try:
                import httpx
                resp = httpx.get(
                    f"https://finnhub.io/api/v1/quote?symbol=SPY&token={settings.FINNHUB_API_KEY}",
                    timeout=10,
                )
                result["finnhub"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
            except Exception as exc:
                result["finnhub"] = f"error: {exc}"
        else:
            result["finnhub"] = "not_configured"

        try:
            r.setex(self._PROVIDER_PROBE_CACHE_KEY, self._PROVIDER_PROBE_TTL, json.dumps(result))
        except Exception:
            logger.debug("Failed to cache provider probe result")

        return result
