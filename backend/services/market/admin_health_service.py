"""
Admin Health Service -- Strict composite health aggregation.

Composes coverage, stage quality, jobs, audit, fundamentals, regime, and task-run data into a
single response so the Admin Dashboard needs only one fetch.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds -- tune here, not scattered across code
# ---------------------------------------------------------------------------
HEALTH_THRESHOLDS: Dict[str, float] = {
    "coverage_daily_pct_min": 95.0,
    "coverage_stale_daily_max": 0,
    "stage_unknown_rate_max": 0.35,
    "stage_invalid_max": 0,
    "stage_monotonicity_max": 0,
    "jobs_error_max": 0,
    "jobs_lookback_hours": 24,
    "audit_daily_fill_pct_min": 95.0,
    "audit_snapshot_fill_pct_min": 90.0,
    "fundamentals_fill_pct_pass": 80.0,
    "fundamentals_fill_pct_warn": 50.0,
}

# Task-status keys we pull from Redis (matches legacy _task_status_keys logic).
_TASK_STATUS_KEYS: List[str] = sorted({
    "admin_backfill_5m",
    "admin_backfill_daily",
    "admin_coverage_backfill_stale",
    "admin_coverage_refresh",
    "admin_coverage_backfill",
    "admin_indicators_recompute_universe",
    "admin_recover_stale_job_runs",
    "admin_snapshots_history_backfill",
    "admin_snapshots_history_record",
    "market_indices_constituents_refresh",
    "market_universe_tracked_refresh",
    "admin_backfill_since_date",
    "compute_daily_regime",
    "market_snapshots_fundamentals_fill",
})


def _dim_status(ok: bool) -> str:
    return "green" if ok else "red"


def _composite_dimension_ok(status: Optional[str]) -> bool:
    """True if dimension passes composite aggregation (green, or fundamentals ok)."""
    return status in ("green", "ok")


class AdminHealthService:
    """Aggregates all health dimensions into one response."""

    def __init__(self) -> None:
        from backend.services.market.market_data_service import market_data_service
        self._svc = market_data_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_composite_health(self, db: Session) -> Dict[str, Any]:
        coverage = self._build_coverage_dimension(db)
        stage = self._build_stage_dimension(db)
        jobs = self._build_jobs_dimension(db)
        audit = self._build_audit_dimension()
        regime = self._build_regime_dimension(db)
        fundamentals = self._build_fundamentals_dimension(db)
        portfolio_sync = self._build_portfolio_sync_dimension(db)
        task_runs = self._build_task_runs()

        dims = {
            "coverage": coverage,
            "stage_quality": stage,
            "jobs": jobs,
            "audit": audit,
            "regime": regime,
            "fundamentals": fundamentals,
            "portfolio_sync": portfolio_sync,
        }

        failures = [name for name, dim in dims.items() if not _composite_dimension_ok(dim.get("status"))]
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
            "dimensions": dims,
            "task_runs": task_runs,
            "thresholds": dict(HEALTH_THRESHOLDS),
            "checked_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Dimension builders
    # ------------------------------------------------------------------

    def _build_coverage_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            from backend.services.market.coverage_utils import compute_coverage_status

            snapshot = self._svc.coverage.coverage_snapshot(db)
            status_info = compute_coverage_status(snapshot)
            daily_pct = float(status_info.get("daily_pct") or 0)
            stale_daily = int(status_info.get("stale_daily") or 0)
            ok = (
                daily_pct >= HEALTH_THRESHOLDS["coverage_daily_pct_min"]
                and stale_daily <= HEALTH_THRESHOLDS["coverage_stale_daily_max"]
            )
            return {
                "status": _dim_status(ok),
                "daily_pct": daily_pct,
                "m5_pct": float(status_info.get("m5_pct") or 0),
                "stale_daily": stale_daily,
                "stale_m5": int(status_info.get("stale_m5") or 0),
                "tracked_count": int(status_info.get("tracked_count") or 0),
                "expected_date": status_info.get("daily_expected_date"),
                "summary": status_info.get("summary", ""),
            }
        except Exception as exc:
            logger.exception("coverage dimension failed: %s", exc)
            return {"status": "red", "error": str(exc)}

    def _build_stage_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            data = self._svc.stage_quality_summary(db, lookback_days=120)
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
            since = datetime.utcnow() - timedelta(hours=lookback)
            recent_q = db.query(JobRun).filter(JobRun.started_at >= since)

            total = recent_q.count()
            ok_count = recent_q.filter(JobRun.status == "ok").count()
            error_count = recent_q.filter(JobRun.status == "error").count()
            running_count = recent_q.filter(JobRun.status == "running").count()
            cancelled_count = recent_q.filter(JobRun.status == "cancelled").count()
            completed = ok_count + error_count + cancelled_count
            success_rate = (ok_count / completed) if completed else 0.0

            latest_failed = (
                recent_q.filter(JobRun.status == "error")
                .order_by(JobRun.started_at.desc())
                .first()
            )

            ok = error_count <= HEALTH_THRESHOLDS["jobs_error_max"]

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
                age_hours = (datetime.utcnow() - latest.as_of_date).total_seconds() / 3600

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

    def _build_audit_dimension(self) -> Dict[str, Any]:
        try:
            raw = self._svc.redis_client.get("market_audit:last")
            payload = (
                json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
                if raw
                else None
            )
            if payload is None:
                return {"status": "red", "error": "no audit data in cache"}

            tracked_total = int(payload.get("tracked_total") or 0)

            # The audit cache stores symbol counts, not percentages.
            # Compute fill % from count / tracked_total.
            daily_fill_pct_raw = payload.get("latest_daily_fill_pct")
            snapshot_fill_pct_raw = payload.get("latest_snapshot_history_fill_pct")

            if daily_fill_pct_raw is not None:
                daily_fill = float(daily_fill_pct_raw)
            elif tracked_total > 0:
                daily_fill = float(payload.get("latest_daily_symbol_count") or 0) / tracked_total * 100
            else:
                daily_fill = 0.0

            if snapshot_fill_pct_raw is not None:
                snapshot_fill = float(snapshot_fill_pct_raw)
            elif tracked_total > 0:
                snapshot_fill = float(payload.get("latest_snapshot_history_symbol_count") or 0) / tracked_total * 100
            else:
                snapshot_fill = 0.0
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
            }
        except Exception as exc:
            logger.exception("audit dimension failed: %s", exc)
            return {"status": "red", "error": str(exc)}

    def _build_fundamentals_dimension(self, db: Session) -> Dict[str, Any]:
        try:
            from backend.models.market_data import MarketSnapshot
            from backend.services.market.universe import tracked_symbols_with_source

            tracked_list, _ = tracked_symbols_with_source(
                db, redis_client=self._svc.redis_client
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
                    MarketSnapshot.pe_ttm.isnot(None),
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

    def _build_portfolio_sync_dimension(self, db: Session) -> Dict[str, Any]:
        """Check if broker accounts have synced recently (within 24h).
        
        Uses datetime.now() to match broker_sync_service which sets
        last_successful_sync with datetime.now().
        """
        try:
            from backend.models import BrokerAccount

            cutoff = datetime.now() - timedelta(hours=24)
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

    def _build_task_runs(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        try:
            r = self._svc.redis_client
            for task_name in _TASK_STATUS_KEYS:
                try:
                    key = f"taskstatus:{task_name}:last"
                    raw = r.get(key)
                    out[task_name] = json.loads(raw) if raw else None
                except Exception as e:
                    logger.warning("failed to load task status for %s: %s", task_name, e)
                    out[task_name] = None
        except Exception as exc:
            logger.exception("task runs load failed: %s", exc)
        return out
