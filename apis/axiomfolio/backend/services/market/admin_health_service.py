"""
Admin Health Service -- Composite health aggregation.

Composes coverage, stage quality, jobs, audit, fundamentals, regime, data accuracy,
and task-run data into a single response so the Admin Dashboard needs only one fetch.

medallion: silver
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from backend.config import settings

# Not cached: refreshed every /admin/health read (per-request RSS is fast to read)
_RSS_OBSERVABILITY_KEYS = frozenset(
    {
        "top_rss_endpoints",
        "worker_request_count_last_hour",
        "rss_observability",
        "hottest_endpoints",
        "hottest_endpoints_error",
    }
)
from backend.services.market.market_data_service import coverage_analytics, infra, stage_quality

logger = logging.getLogger(__name__)


def _datetime_as_utc_aware(dt: datetime) -> datetime:
    """Coerce to timezone-aware UTC for comparisons against ``datetime.now(timezone.utc)``."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Thresholds -- tune here, not scattered across code
# ---------------------------------------------------------------------------
HEALTH_THRESHOLDS: Dict[str, float] = {
    "coverage_daily_pct_min": 95.0,
    "coverage_stale_daily_max": 25,
    # Stage-quality thresholds. Historical note: we used to have a single
    # absolute-count cap `stage_monotonicity_max: 15`, which is
    # scale-dependent (violations grow linearly with universe size × history
    # window) and caused the dim to be pinned to "Critical" forever against
    # a ~2500-symbol × 120-day universe. The counter is now evaluated as a
    # *drift percentage* of history rows checked, with separate warn/crit
    # thresholds. See docs/handoffs/STAGE_QUALITY_DIAGNOSIS_2026Q2.md.
    "stage_unknown_rate_max": 0.35,       # warn if unknowns exceed this
    "stage_unknown_rate_crit": 0.60,      # critical if unknowns exceed this
    "stage_invalid_max": 0,               # any invalid row == critical
    "stage_days_drift_pct_warn": 2.0,     # warn if drift_pct above this
    "stage_days_drift_pct_crit": 10.0,    # critical if drift_pct above this
    "jobs_success_rate_min": 0.90,
    "jobs_lookback_hours": 24,
    "audit_daily_fill_pct_min": 95.0,
    "audit_snapshot_fill_pct_min": 90.0,
    "fundamentals_fill_pct_pass": 80.0,
    "fundamentals_fill_pct_warn": 50.0,
    "data_accuracy_mismatch_max": 5,
    "data_accuracy_max_age_days": 10,
    # G5: IV coverage warm-up and floors. Below 95% we emit a warning
    # pointing ops at docs/plans/G5_IV_RANK_SURFACE.md (paid-provider
    # escalation). During the 30-day warm-up we do not degrade the
    # composite -- the pipeline ingests incrementally.
    "iv_coverage_pct_warn": 95.0,
    "iv_coverage_warmup_days": 30,
}

MARKET_DIMS = {"coverage", "stage_quality", "jobs", "audit", "regime", "fundamentals", "data_accuracy", "iv_coverage"}
BROKER_DIMS = {"portfolio_sync", "ibkr_gateway", "plaid"}
# G28: deploys dim is infra-level — not part of the market/broker split.
# It still counts toward composite; a red deploy dim must surface regardless
# of broker sync health (a stuck API deploy breaks everything).
INFRA_DIMS = {"deploys", "universe_coverage"}

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
        payload: Optional[Dict[str, Any]] = None
        try:
            raw = r.get(_COMPOSITE_HEALTH_CACHE_KEY)
            if raw:
                payload = json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
        except Exception as e:
            logger.warning("composite health cache read failed: %s", e)

        if payload is None:
            payload = self._compute_composite_health(db)
            try:
                cache_body = {k: v for k, v in payload.items() if k not in _RSS_OBSERVABILITY_KEYS}
                r.setex(
                    _COMPOSITE_HEALTH_CACHE_KEY,
                    _COMPOSITE_HEALTH_TTL_S,
                    json.dumps(cache_body),
                )
            except Exception as e:
                logger.warning("composite health cache write failed: %s", e)

        self._merge_rss_observability_fields(payload, r)
        self._merge_peak_hottest_endpoints(payload, r)
        return payload

    def _merge_peak_hottest_endpoints(self, payload: Dict[str, Any], r: Any) -> None:
        """S2: top-10 endpoints by recent sampled peak-RSS; explicit null + error on failure."""
        if not getattr(settings, "ENABLE_PEAK_RSS_MIDDLEWARE", True):
            payload["hottest_endpoints"] = None
            payload["hottest_endpoints_error"] = "disabled"
            return
        try:
            from backend.services.observability.peak_rss_store import get_hottest_endpoints_aggregated

            rows, err = get_hottest_endpoints_aggregated(r)
        except Exception as e:  # noqa: BLE001
            logger.warning("peak_rss: hottest merge failed: %s", e, exc_info=True)
            payload["hottest_endpoints"] = None
            payload["hottest_endpoints_error"] = "error"
            return
        if err is not None:
            payload["hottest_endpoints"] = None
            payload["hottest_endpoints_error"] = err
            return
        payload["hottest_endpoints"] = rows
        payload["hottest_endpoints_error"] = None

    def _merge_rss_observability_fields(self, payload: Dict[str, Any], r: Any) -> None:
        """Add ``top_rss_endpoints`` + counts; never from composite cache (always fresh from Redis)."""
        if not settings.ENABLE_RSS_OBSERVABILITY:
            payload["top_rss_endpoints"] = []
            payload["worker_request_count_last_hour"] = 0
            payload["rss_observability"] = {
                "available": False,
                "disabled": True,
            }
            return
        try:
            from backend.services.observability.rss_store import get_rss_health_payload

            block = get_rss_health_payload(r)
        except Exception as e:
            logger.warning("rss observability: health merge failed: %s", e, exc_info=True)
            block = {
                "top_rss_endpoints": [],
                "worker_request_count_last_hour": 0,
                "rss_observability": {
                    "available": False,
                    "reason": "error",
                },
            }
        payload["top_rss_endpoints"] = block.get("top_rss_endpoints", [])
        payload["worker_request_count_last_hour"] = int(block.get("worker_request_count_last_hour", 0) or 0)
        ro = block.get("rss_observability", {})
        payload["rss_observability"] = ro

    def _compute_composite_health(self, db: Session) -> Dict[str, Any]:
        coverage = self._build_coverage_dimension(db)
        stage = self._build_stage_dimension(db)
        jobs = self._build_jobs_dimension(db)
        audit = self._build_audit_dimension(db)
        regime = self._build_regime_dimension(db)
        fundamentals = self._build_fundamentals_dimension(db)
        portfolio_sync = self._build_portfolio_sync_dimension(db)
        ibkr_gateway = self._build_ibkr_gateway_dimension()
        plaid = self._build_plaid_dimension(db)
        data_accuracy = self._build_data_accuracy_dimension()
        deploys = self._build_deploys_dimension(db)
        universe_coverage = self._build_universe_coverage_dimension()
        iv_coverage = self._build_iv_coverage_dimension(db)
        task_runs = self._build_task_runs()

        dims: Dict[str, Any] = {
            "coverage": coverage,
            "stage_quality": stage,
            "jobs": jobs,
            "audit": audit,
            "regime": regime,
            "fundamentals": fundamentals,
            "data_accuracy": data_accuracy,
            "iv_coverage": iv_coverage,
            "portfolio_sync": portfolio_sync,
            "ibkr_gateway": ibkr_gateway,
            "plaid": plaid,
            "deploys": deploys,
            "universe_coverage": universe_coverage,
        }

        for name in dims:
            if name in MARKET_DIMS:
                dims[name]["category"] = "market"
            elif name in INFRA_DIMS:
                dims[name]["category"] = "infra"
            else:
                dims[name]["category"] = "broker"

        # Composite scoring: all dimensions including broker sync / gateway.
        scored_dims = dims
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
            "dimensions": dims,
            "task_runs": task_runs,
            "thresholds": dict(HEALTH_THRESHOLDS),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "provider_metrics": self._build_provider_metrics() or None,
            "byok_anomaly": self._build_byok_anomaly(),
            "reconcile_anomaly": self._build_reconcile_anomaly(),
            "hot_path_cache": self._build_hot_path_cache_metrics(),
        }

    def _build_byok_anomaly(self) -> Dict[str, Any]:
        """BYOK fallback counter snapshot.

        Reports separately from the composite so a BYOK hiccup is
        visible to ops (satisfies ``no-silent-fallback.mdc``) without
        being able to flip the platform composite red — BYOK is a
        per-user concern, not an infra-wide one.
        """
        try:
            from backend.services.agent.byok_anomaly import snapshot as _byok_snapshot

            return _byok_snapshot()
        except Exception as e:
            logger.warning("byok_anomaly snapshot failed: %s", e)
            return {
                "total": 0,
                "by_reason": {},
                "last_at": None,
                "available": False,
            }

    def _build_reconcile_anomaly(self) -> Dict[str, Any]:
        """Schwab (and similar) closing-lot reconciliation failure counter (Redis)."""
        from backend.services.market.market_data_service import infra
        from backend.services.portfolio.schwab_sync_service import (
            RECONCILE_ANOMALY_KEY,
        )

        try:
            r = getattr(infra, "redis_client", None)
            if r is None:
                return {"total": 0, "available": False}
            raw = r.get(RECONCILE_ANOMALY_KEY)
            if raw is None:
                return {"total": 0, "available": True}
            s = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
            return {"total": int(s), "available": True}
        except Exception as e:
            logger.warning("reconcile_anomaly snapshot failed: %s", e)
            return {"total": 0, "available": False}

    def _build_hot_path_cache_metrics(self) -> Dict[str, Any]:
        """Portfolio response-cache bypass + narrative timeout counters (Redis)."""
        from backend.api.middleware.response_cache import REDIS_BYPASS_COUNTER_KEY
        from backend.services.market.market_data_service import infra

        try:
            r = getattr(infra, "redis_client", None)
            if r is None:
                return {
                    "resp_cache_redis_bypass_total": 0,
                    "narrative_timeout_total": 0,
                    "available": False,
                }

            def _int_key(key: str) -> int:
                raw = r.get(key)
                if raw is None:
                    return 0
                s = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
                return int(s)

            return {
                "resp_cache_redis_bypass_total": _int_key(REDIS_BYPASS_COUNTER_KEY),
                "narrative_timeout_total": _int_key("narrative_timeout_total"),
                "available": True,
            }
        except Exception as e:
            logger.warning("hot_path_cache metrics snapshot failed: %s", e)
            return {
                "resp_cache_redis_bypass_total": 0,
                "narrative_timeout_total": 0,
                "available": False,
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
        """Evaluate the stage-quality dimension with scale-aware thresholds.

        Returns a three-state status:
          - ``green``  — healthy (no invalid rows, unknowns within tolerance,
            day-counter drift below the warn threshold).
          - ``yellow`` — degraded but operational (elevated unknowns or
            day-counter drift above warn but below crit).
          - ``red``    — critical: any invalid rows, or unknowns/drift above
            their critical thresholds, or the service failed entirely.

        Per ``no-silent-fallback.mdc``: if the history-rows counter is
        missing (older service versions) or zero, we do NOT silently flip to
        green — we mark status ``red`` with ``reason='unknown'`` so ops can
        see the gap rather than a misleading "Healthy" badge.
        """
        try:
            data = stage_quality.stage_quality_summary(db, lookback_days=120)
            unknown_rate = float(data.get("unknown_rate") or 0)
            invalid_count = int(data.get("invalid_stage_count") or 0)
            stage_days_drift_count = int(data.get("monotonicity_issues") or 0)
            rows_checked = int(data.get("stage_history_rows_checked") or 0)
            total_symbols = int(data.get("total_symbols") or 0)

            # Drift percentage: fraction of row-pairs with stage_days
            # discontinuities. Absent data reported as None, not 0 —
            # downstream decision branches on that explicitly.
            drift_pct: Optional[float]
            if rows_checked > 0:
                drift_pct = round(
                    100.0 * stage_days_drift_count / rows_checked, 3
                )
            else:
                drift_pct = None

            warn_unknown = HEALTH_THRESHOLDS["stage_unknown_rate_max"]
            crit_unknown = HEALTH_THRESHOLDS["stage_unknown_rate_crit"]
            warn_drift = HEALTH_THRESHOLDS["stage_days_drift_pct_warn"]
            crit_drift = HEALTH_THRESHOLDS["stage_days_drift_pct_crit"]
            max_invalid = HEALTH_THRESHOLDS["stage_invalid_max"]

            # Unknown state: counters say there's data (total_symbols>0)
            # but the drift denominator is missing. Surface as red/unknown
            # rather than falsely passing.
            if total_symbols > 0 and rows_checked == 0 and stage_days_drift_count > 0:
                status = "red"
                reason = "stage_history_rows_checked unavailable; cannot evaluate drift"
            elif invalid_count > max_invalid:
                status = "red"
                reason = f"{invalid_count} invalid stage rows"
            elif unknown_rate > crit_unknown:
                status = "red"
                reason = f"{unknown_rate * 100:.1f}% unknown rate"
            elif drift_pct is not None and drift_pct > crit_drift:
                status = "red"
                reason = f"{drift_pct:.2f}% stage-day drift"
            elif unknown_rate > warn_unknown:
                status = "yellow"
                reason = f"{unknown_rate * 100:.1f}% unknown rate"
            elif drift_pct is not None and drift_pct > warn_drift:
                status = "yellow"
                reason = f"{drift_pct:.2f}% stage-day drift"
            else:
                status = "green"
                reason = "ok"

            return {
                "status": status,
                "reason": reason,
                "unknown_rate": round(unknown_rate, 4),
                "invalid_count": invalid_count,
                # Back-compat: `monotonicity_issues` is the legacy field
                # name consumed by the frontend, runbook, and anomaly
                # builder. Kept in parallel with the clearer
                # `stage_days_drift_count` to avoid a coordinated rename.
                "monotonicity_issues": stage_days_drift_count,
                "stage_days_drift_count": stage_days_drift_count,
                "stage_days_drift_pct": drift_pct,
                "stage_history_rows_checked": rows_checked,
                # Surfaced for ops visibility (no-silent-fallback): history rows
                # where stage_label is valid but current_stage_days is null are
                # treated as "unknown" (not drift) and counted here. High
                # values during warmup are expected; persistent high values
                # indicate a write-path gap in the snapshot pipeline.
                "unknown_stage_days_count": int(
                    data.get("unknown_stage_days_count") or 0
                ),
                "empty_label_count": int(data.get("empty_label_count") or 0),
                "stale_stage_count": int(data.get("stale_stage_count") or 0),
                "total_symbols": total_symbols,
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
                a
                for a in accounts
                if not a.last_successful_sync
                or _datetime_as_utc_aware(a.last_successful_sync) < cutoff
            ]
            account_type_warnings: list[dict[str, Any]] = []
            for account in accounts:
                msg = (account.sync_error_message or "").strip()
                if not msg.startswith("ACCOUNT_TYPE_WARNING "):
                    continue
                raw_json = msg.replace("ACCOUNT_TYPE_WARNING ", "", 1).strip()
                try:
                    parsed = json.loads(raw_json)
                except Exception:
                    continue
                if isinstance(parsed, list):
                    account_type_warnings.extend(
                        item for item in parsed if isinstance(item, dict)
                    )

            status = "red" if stale else ("yellow" if account_type_warnings else "green")
            return {
                "status": status,
                "total_accounts": len(accounts),
                "stale_accounts": len(stale),
                "stale_list": [a.account_number for a in stale[:5]],
                "account_type_warnings": account_type_warnings,
            }
        except Exception as exc:
            logger.exception("portfolio_sync dimension failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def _build_plaid_dimension(self, db: Session) -> Dict[str, Any]:
        """Plaid aggregator health: connection statuses + last sync age.

        Status buckets:

        * ``ok``      — no connections, OR all ACTIVE and last sync < 26h
        * ``yellow``  — at least one ERROR or NEEDS_REAUTH row
        * ``red``     — more than half of non-revoked rows stale (>26h)
          OR Plaid is not configured on this instance (so Pro users
          paying for the feature cannot use it).
        * ``error``   — the dimension itself failed to compute; surfaces
          as red in the composite.

        Plaid configuration absence does NOT get silently coerced to "ok"
        (no-silent-fallback); we report ``configured=false`` and let the
        composite mark the system degraded.
        """
        try:
            from backend.models.plaid_connection import (
                PlaidConnection,
                PlaidConnectionStatus,
            )

            configured = bool(
                getattr(settings, "PLAID_CLIENT_ID", None)
                and getattr(settings, "PLAID_SECRET", None)
            )

            rows: List[PlaidConnection] = (
                db.query(PlaidConnection)
                .filter(
                    PlaidConnection.status != PlaidConnectionStatus.REVOKED.value
                )
                .all()
            )

            total = len(rows)
            status_counts: Dict[str, int] = {}
            for r in rows:
                status_counts[r.status] = status_counts.get(r.status, 0) + 1

            cutoff = datetime.now(timezone.utc) - timedelta(hours=26)
            stale = [
                r
                for r in rows
                if r.last_sync_at is None
                or _datetime_as_utc_aware(r.last_sync_at) < cutoff
            ]

            error_count = status_counts.get(
                PlaidConnectionStatus.ERROR.value, 0
            )
            reauth_count = status_counts.get(
                PlaidConnectionStatus.NEEDS_REAUTH.value, 0
            )

            if not configured and total > 0:
                status = "red"
            elif total == 0:
                status = "ok"
            elif len(stale) * 2 > total:
                status = "red"
            elif error_count > 0 or reauth_count > 0:
                status = "yellow"
            else:
                status = "green"

            return {
                "status": status,
                "configured": configured,
                "total_connections": total,
                "stale_connections": len(stale),
                "status_counts": status_counts,
                "error_count": error_count,
                "needs_reauth_count": reauth_count,
            }
        except Exception as exc:
            logger.exception("plaid dimension failed: %s", exc)
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

    def _build_iv_coverage_dimension(self, db: Session) -> Dict[str, Any]:
        """G5: daily IV-coverage stats over the tracked universe.

        Six sub-metrics required by ``docs/plans/G5_IV_RANK_SURFACE.md`` §6:

        - ``tracked_symbols``: size of today's scanned universe.
        - ``with_iv_30d_today``: how many have a ``HistoricalIV.iv_30d``
          row stamped for today's last trading day.
        - ``with_hv_20d_today``: how many of those carry a 20-day
          realized-vol reading (requires ≥21 contiguous daily closes).
        - ``with_iv_rank_252``: populated by the ``compute_iv_rank`` task
          after ≥20 daily samples.
        - ``coverage_pct_iv_30d`` = ``with_iv_30d_today / tracked_symbols``.
        - ``source_breakdown`` (IBKR vs Yahoo) + ``last_successful_snapshot_at``.

        Status: green when ``coverage_pct_iv_30d >= 95`` OR we're still
        inside the 30-day warm-up. Yellow with the paid-provider pointer
        otherwise. Never flips red on its own (broker-independent feature).
        """
        try:
            from backend.models.historical_iv import HistoricalIV
            from backend.services.market.historical_iv_service import (
                iv_source_breakdown,
                last_trading_day,
            )
            from backend.services.market.market_data_service import infra as _infra
            from backend.services.market.universe import tracked_symbols

            today = last_trading_day()
            try:
                universe = tracked_symbols(db, redis_client=_infra.redis_client) or []
            except Exception as e:
                logger.warning("iv_coverage: tracked symbols lookup failed: %s", e)
                universe = []
            n_tracked = len(universe)

            # Row counts for today.
            q_today = db.query(HistoricalIV).filter(HistoricalIV.date == today)
            with_iv_30d_today = int(
                q_today.filter(HistoricalIV.iv_30d.isnot(None)).count() or 0
            )
            with_hv_20d_today = int(
                q_today.filter(HistoricalIV.hv_20d.isnot(None)).count() or 0
            )
            with_iv_rank_252 = int(
                db.query(HistoricalIV)
                .filter(HistoricalIV.iv_rank_252.isnot(None))
                .count()
                or 0
            )

            coverage_pct: Optional[float] = None
            if n_tracked > 0:
                coverage_pct = round(100.0 * with_iv_30d_today / n_tracked, 2)

            last_row = (
                db.query(func.max(HistoricalIV.date))
                .filter(HistoricalIV.iv_30d.isnot(None))
                .scalar()
            )
            last_successful_snapshot_at = str(last_row) if last_row is not None else None

            source_breakdown = iv_source_breakdown(db, as_of=today)

            # Status / reason logic. Warm-up: if the most-recent snapshot
            # is within 30 days of "first ever" snapshot we still hold
            # green so the dim doesn't scream during the initial ramp.
            first_row = (
                db.query(func.min(HistoricalIV.date))
                .filter(HistoricalIV.iv_30d.isnot(None))
                .scalar()
            )
            warmup_days = int(HEALTH_THRESHOLDS.get("iv_coverage_warmup_days", 30))
            warn_pct = float(HEALTH_THRESHOLDS.get("iv_coverage_pct_warn", 95.0))
            in_warmup = False
            if first_row is not None and last_row is not None:
                in_warmup = (last_row - first_row).days < warmup_days
            elif first_row is None:
                # Never snapshotted -- call this a "pre-warmup" state.
                in_warmup = True

            status: str
            reason: Optional[str] = None
            if n_tracked == 0:
                status = "yellow"
                reason = "Tracked universe empty; IV coverage cannot be evaluated."
            elif coverage_pct is not None and coverage_pct >= warn_pct:
                status = "green"
            elif in_warmup:
                status = "green"
                reason = (
                    f"IV coverage at {coverage_pct}% (warm-up ≤ {warmup_days}d; "
                    "ingest still ramping)."
                )
            else:
                status = "yellow"
                reason = (
                    f"IV coverage below {warn_pct:.0f}% (at {coverage_pct}%) — "
                    "consider paid provider (see docs/plans/G5_IV_RANK_SURFACE.md)."
                )

            return {
                "status": status,
                "reason": reason,
                "tracked_symbols": n_tracked,
                "with_iv_30d_today": with_iv_30d_today,
                "with_hv_20d_today": with_hv_20d_today,
                "with_iv_rank_252": with_iv_rank_252,
                "coverage_pct_iv_30d": coverage_pct,
                "source_breakdown": source_breakdown,
                "last_successful_snapshot_at": last_successful_snapshot_at,
                "as_of": str(today),
                "in_warmup": in_warmup,
            }
        except Exception as exc:
            logger.warning("iv_coverage dimension failed: %s", exc)
            # Never flip composite red on iv-coverage alone -- it's a
            # feature dim, not a gate. Yellow + explicit `available=False`
            # so ops can still differentiate "zero" from "unavailable".
            return {
                "status": "yellow",
                "reason": f"iv_coverage unavailable: {exc}",
                "tracked_symbols": None,
                "with_iv_30d_today": None,
                "with_hv_20d_today": None,
                "with_iv_rank_252": None,
                "coverage_pct_iv_30d": None,
                "source_breakdown": {"available": False},
                "last_successful_snapshot_at": None,
                "available": False,
            }

    def _build_universe_coverage_dimension(self) -> Dict[str, Any]:
        """G11: last startup snapshot of held symbols vs tracked universe (Redis)."""
        try:
            from backend.services.ops import universe_coverage as uc

            raw = uc.read_universe_coverage_for_admin_health()
            if not raw:
                return {
                    "state": "unknown",
                    "status": "yellow",
                    "users_checked": None,
                    "positions_total": None,
                    "gaps_total": None,
                    "errors": None,
                    "reason": "No snapshot yet (API startup has not written Redis, or read failed).",
                }
            st_raw = str(raw.get("state") or "")
            if st_raw == "healthy":
                status = "green"
            elif st_raw == "degraded":
                status = "yellow"
            else:
                status = "red"
            out: Dict[str, Any] = {
                "state": st_raw,
                "status": status,
                "users_checked": raw.get("users_checked"),
                "positions_total": raw.get("positions_total"),
                "gaps_total": raw.get("gaps_total"),
                "errors": raw.get("errors"),
                "checked_at": raw.get("checked_at"),
            }
            if raw.get("error_detail"):
                out["error_detail"] = raw.get("error_detail")
            if st_raw == "degraded" and raw.get("gaps_total") is not None:
                out["reason"] = (
                    f"Universe gap: {raw.get('gaps_total')} open position(s) "
                    "not in tracked set (see API logs for \"universe gap\")."
                )
            elif st_raw == "error":
                out["reason"] = "Startup universe coverage check failed or reported errors (see error_detail and API logs)."
            return out
        except Exception as exc:
            logger.exception("universe_coverage dimension failed: %s", exc)
            return {
                "state": "error",
                "status": "red",
                "errors": 1,
                "reason": str(exc)[:2000],
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
