"""
Nightly coverage bootstrap, scan overlay, exit cascade hooks, and coverage health.

The Stage Analysis spec nightly computation steps 0–10 (regime inputs through
persist) run inside ``recompute_universe`` / ``indicator_engine``;
this module orchestrates data refresh, that recompute, market regime persistence,
scan overlay, history archive, and downstream evaluation tasks.
"""

from __future__ import annotations

import bisect
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from backend.database import SessionLocal
from backend.models import Position
from backend.models.market_data import MarketSnapshot
from backend.services.market.market_data_service import coverage_analytics, infra
from backend.tasks.utils.task_utils import _resolve_history_days, task_run

logger = logging.getLogger(__name__)


@task_run("scan_overlay")
def _run_scan_overlay() -> dict:
    """Run scan overlay engine: assign scan_tier + action_label to all snapshots."""
    session = SessionLocal()
    try:
        from backend.services.market.regime_engine import get_current_regime
        from backend.services.market.scan_engine import (
            ScanInput,
            classify_scan_tier,
            derive_action_label,
        )

        regime = get_current_regime(session)
        regime_state = regime.regime_state if regime else "R3"

        snapshots = (
            session.query(MarketSnapshot)
            .filter(
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.is_valid.is_(True),
            )
            .all()
        )

        atrx_vals = sorted(
            [float(s.atrx_sma_150) for s in snapshots if s.atrx_sma_150 is not None]
        )
        atrx_count = len(atrx_vals)

        def _atrx_percentile(val: float) -> float:
            if atrx_count == 0 or val is None:
                return 0.0
            rank = bisect.bisect_left(atrx_vals, val)
            return (rank / atrx_count) * 100

        _ALERT_TIERS = {"Breakout Elite", "Breakout Standard"}
        previous_tiers = {snap.symbol: snap.scan_tier for snap in snapshots}
        new_candidates = []

        updated = 0
        for snap in snapshots:
            try:
                atrx_raw = (
                    float(snap.atrx_sma_150) if snap.atrx_sma_150 is not None else None
                )
                scan_input = ScanInput(
                    symbol=snap.symbol,
                    stage_label=snap.stage_label or "UNKNOWN",
                    rs_mansfield=snap.rs_mansfield_pct,
                    ema10_dist_n=snap.ema10_dist_n,
                    atre_150_pctile=_atrx_percentile(atrx_raw)
                    if atrx_raw is not None
                    else None,
                    range_pos_52w=snap.range_pos_52w,
                    ext_pct=snap.ext_pct,
                    atrp_14=snap.atrp_14,
                )
                tier = classify_scan_tier(scan_input, regime_state)
                label = derive_action_label(
                    stage_label=scan_input.stage_label,
                    scan_tier=tier,
                    regime=regime_state,
                )
                prev = previous_tiers.get(snap.symbol)
                if tier in _ALERT_TIERS and prev not in _ALERT_TIERS:
                    new_candidates.append({
                        "symbol": snap.symbol,
                        "scan_tier": tier,
                        "action_label": label,
                        "stage": scan_input.stage_label,
                        "rs_mansfield": float(snap.rs_mansfield_pct) if snap.rs_mansfield_pct is not None else None,
                    })
                snap.scan_tier = tier
                snap.action_label = label
                updated += 1
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.warning(
                    "Scan overlay failed for %s: %s", getattr(snap, "symbol", "?"), e
                )
                continue

        session.commit()

        if new_candidates:
            from backend.services.brain.webhook_client import brain_webhook
            brain_webhook.notify_sync(
                "scan_alert",
                {
                    "regime_state": regime_state,
                    "new_candidates": new_candidates,
                    "count": len(new_candidates),
                },
            )

        return {"status": "ok", "updated": updated, "total": len(snapshots), "new_alerts": len(new_candidates)}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@task_run("exit_cascade_evaluation")
def _evaluate_exit_cascade_all() -> dict:
    """Evaluate exit cascade for all open positions. Logs warnings, does not auto-sell."""
    session = SessionLocal()
    try:
        from backend.services.execution.exit_cascade import (
            ExitAction,
            PositionContext,
            evaluate_exit_cascade,
        )
        from backend.services.market.regime_engine import get_current_regime

        regime = get_current_regime(session)
        regime_state = regime.regime_state if regime else "R3"

        positions = (
            session.query(Position)
            .filter(
                Position.status == "open",
                Position.quantity > 0,
            )
            .all()
        )

        signals_generated = 0
        for pos in positions:
            try:
                snap = (
                    session.query(MarketSnapshot)
                    .filter(
                        MarketSnapshot.symbol == pos.symbol,
                        MarketSnapshot.analysis_type == "technical_snapshot",
                    )
                    .order_by(MarketSnapshot.id.desc())
                    .first()
                )
                if not snap:
                    continue

                entry_price = float(pos.average_cost or 0)
                current_price = float(snap.current_price or 0)
                pnl_pct = (
                    ((current_price - entry_price) / entry_price * 100)
                    if entry_price
                    else 0
                )
                is_short = (
                    getattr(pos, "position_type", None) is not None
                    and str(getattr(pos, "position_type", ""))
                    .lower()
                    .startswith("short")
                )

                ctx = PositionContext(
                    symbol=pos.symbol,
                    side="SHORT" if is_short else "LONG",
                    entry_price=entry_price,
                    current_price=current_price,
                    atr_14=float(getattr(snap, "atr_14", 0) or 0),
                    atrp_14=float(snap.atrp_14 or 2.0),
                    stage_label=snap.stage_label or "UNKNOWN",
                    previous_stage_label=snap.previous_stage_label,
                    current_stage_days=int(getattr(snap, "current_stage_days", 0) or 0),
                    ext_pct=float(getattr(snap, "ext_pct", 0) or 0),
                    sma150_slope=float(getattr(snap, "sma150_slope", 0) or 0),
                    ema10_dist_n=float(getattr(snap, "ema10_dist_n", 0) or 0),
                    rs_mansfield=float(snap.rs_mansfield_pct or 0),
                    regime_state=regime_state,
                    previous_regime_state=None,
                    days_held=0,
                    pnl_pct=pnl_pct,
                )

                result = evaluate_exit_cascade(ctx)
                if result.final_action != ExitAction.HOLD:
                    signals_generated += 1
                    logger.info(
                        "Exit cascade signal for %s: %s (tier=%s, reason=%s)",
                        pos.symbol,
                        result.final_action.value,
                        result.final_tier,
                        result.final_reason,
                    )
            except SoftTimeLimitExceeded:
                raise
            except Exception:
                logger.warning(
                    "Exit cascade failed for position %s", pos.symbol, exc_info=True
                )
                continue

        return {
            "status": "ok",
            "positions_checked": len(positions),
            "signals": signals_generated,
        }
    finally:
        session.close()


def _summarize_bootstrap_step(step: str, payload: Optional[dict]) -> str:
    data = payload or {}
    if step == "market_indices_constituents_refresh":
        idx = data.get("indices") or {}
        parts = [
            f"{name}: {stats.get('fetched', 0)} via {stats.get('provider_used', 'n/a')}"
            for name, stats in idx.items()
        ]
        return "; ".join(parts) or "Refreshed constituents"
    if step == "market_universe_tracked_refresh":
        return f"{data.get('tracked_all', 0)} tracked ({data.get('new', 0)} new)"
    if step == "admin_backfill_daily":
        if data.get("api_calls") is not None:
            return (
                f"Bulk EOD: {data.get('persisted', 0)} bars for "
                f"{data.get('matched_tracked', 0)}/{data.get('tracked_total', 0)} "
                f"tracked ({data.get('api_calls', 0)} API call{'s' if data.get('api_calls', 0) != 1 else ''})"
            )
        return (
            f"Inserted {data.get('bars_inserted_total', 0)} bars across "
            f"{data.get('tracked_total', 0)} tracked"
        )
    if step == "admin_indicators_recompute_universe":
        return (
            f"Recomputed {data.get('processed_ok', data.get('symbols', 0))} / "
            f"{data.get('symbols', 0)}"
        )
    if step == "admin_snapshots_history_backfill":
        return (
            f"Snapshot history: {data.get('processed_symbols', 0)} syms, "
            f"{data.get('written_rows', 0)} rows (days={data.get('days', 0)})"
        )
    if step == "admin_coverage_refresh":
        return f"Coverage: {data.get('daily_pct', 0)}% daily; stale={data.get('stale_daily', 0)}"
    if step == "compute_daily_regime":
        return f"Regime: {data.get('regime_state', '?')} (score={data.get('composite_score', '?')})"
    if step == "scan_overlay":
        return f"Scan: {data.get('updated', 0)}/{data.get('total', 0)} snapshots classified"
    if step == "exit_cascade_evaluation":
        return (
            f"Exits: {data.get('signals', 0)} signals from "
            f"{data.get('positions_checked', 0)} positions"
        )
    if step == "strategy_evaluation":
        return (
            f"Strategies: {data.get('evaluated', 0)} evaluated, "
            f"{data.get('total_signals', 0)} signals"
        )
    if step == "intelligence_digest":
        return f"Brief: {data.get('type', '?')} as_of={data.get('as_of', '?')}"
    return data.get("status", "ok")


@shared_task(
    soft_time_limit=7000,
    time_limit=7200,
)
@task_run("admin_coverage_backfill", lock_key=lambda: "admin_coverage_backfill", lock_ttl_seconds=7500)
def daily_bootstrap(
    history_days: Optional[int] = None,
    history_batch_size: int = 25,
    backfill_days: int = 200,
    *,
    pipeline_run_id: Optional[str] = None,
) -> dict:
    """Backfill DAILY coverage for the tracked universe (no 5m).

    When ``PIPELINE_DAG_ENABLED`` is True (default), delegates to the DAG
    orchestrator which tracks per-step state in Redis, supports resume from
    failure, and enables individual step retry from the admin UI.

    The legacy sequential path is preserved as a fallback.
    """
    import uuid as _uuid

    from backend.config import settings as _settings

    if _settings.PIPELINE_DAG_ENABLED:
        # TODO: DAG mode doesn't yet deep-backfill OHLCV for newly added
        # symbols (the legacy path used tracked_cache().new + backfill_days).
        # Add a conditional deep-backfill step when new symbols are detected.
        from backend.services.pipeline.orchestrator import run_pipeline

        run_id = pipeline_run_id or f"nightly-{_uuid.uuid4().hex[:12]}"
        _triggered_by = "admin" if pipeline_run_id else "celery_beat"
        _hist_days = history_days if history_days is not None else 20
        params = {
            "snapshot_history": {
                "days": int(_hist_days),
                "batch_size": int(history_batch_size),
            },
        }
        return run_pipeline(
            run_id,
            params=params,
            triggered_by=_triggered_by,
        )

    # -- Legacy sequential fallback (PIPELINE_DAG_ENABLED=False) -----------
    from backend.tasks.market.backfill import (
        constituents,
        daily_bars,
        tracked_cache,
    )
    from backend.tasks.market.history import snapshot_last_n_days
    from backend.tasks.market.indicators import recompute_universe
    from backend.tasks.market.regime import compute_daily

    try:
        _backfill_days = max(1, min(int(backfill_days), 3000))
    except (TypeError, ValueError):
        _backfill_days = 200

    rollup: Dict[str, Any] = {"steps": []}
    import time as _time

    def _append(step_name: str, result: dict, duration_s: float = 0.0) -> None:
        rollup["steps"].append(
            {
                "name": step_name,
                "summary": _summarize_bootstrap_step(step_name, result),
                "result": result,
                "duration_s": round(duration_s, 2),
            }
        )

    _t0 = _time.monotonic()
    try:
        res1 = constituents()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("daily_bootstrap: constituents failed (non-fatal): %s", exc)
        res1 = {"status": "error", "error": str(exc)}
    _append("market_indices_constituents_refresh", res1, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        res2 = tracked_cache()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("daily_bootstrap: tracked_cache failed (non-fatal): %s", exc)
        res2 = {"status": "error", "error": str(exc)}
    _append("market_universe_tracked_refresh", res2, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        res3 = daily_bars(days=_backfill_days)
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("daily_bootstrap: daily_bars failed: %s", exc)
        res3 = {"status": "error", "error": str(exc)}
    _append("admin_backfill_daily", res3, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        res4 = recompute_universe(batch_size=50)
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("daily_bootstrap: recompute_universe failed (non-fatal): %s", exc)
        res4 = {"status": "error", "error": str(exc)}
    _append("admin_indicators_recompute_universe", res4, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        res5 = compute_daily()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("Regime computation failed (non-fatal): %s", exc)
        res5 = {"status": "error", "error": str(exc)}
    _append("compute_daily_regime", res5, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        res6 = _run_scan_overlay()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("Scan overlay failed (non-fatal): %s", exc)
        res6 = {"status": "error", "error": str(exc)}
    _append("scan_overlay", res6, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        resolved_days = _resolve_history_days(history_days)
        res7 = snapshot_last_n_days(
            days=int(resolved_days), batch_size=int(history_batch_size)
        )
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        res7 = {"status": "error", "error": str(exc)}
    _append("admin_snapshots_history_backfill", res7, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        res8 = _evaluate_exit_cascade_all()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("Exit cascade evaluation failed (non-fatal): %s", exc)
        res8 = {"status": "error", "error": str(exc)}
    _append("exit_cascade_evaluation", res8, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        from backend.tasks.strategy.tasks import evaluate_strategies_task

        res9 = evaluate_strategies_task()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("Strategy evaluation failed (non-fatal): %s", exc)
        res9 = {"status": "error", "error": str(exc)}
    _append("strategy_evaluation", res9, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        res10 = health_check()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("daily_bootstrap: health_check failed (non-fatal): %s", exc)
        res10 = {"status": "error", "error": str(exc)}
    _append("admin_coverage_refresh", res10, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        from backend.tasks.market.maintenance import refresh_market_mvs as _refresh_mvs
        res_mv = _refresh_mvs()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("MV refresh failed (non-fatal): %s", exc)
        res_mv = {"status": "error", "error": str(exc)}
    _append("admin_refresh_market_mvs", res_mv, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        from backend.tasks.market.maintenance import warm_dashboard_cache as _warm_dash
        res_dash = _warm_dash()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("Dashboard cache warm failed (non-fatal): %s", exc)
        res_dash = {"status": "error", "error": str(exc)}
    _append("admin_warm_dashboard", res_dash, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        from backend.tasks.market.maintenance import audit_quality as _audit_quality
        res10b = _audit_quality()
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("Audit quality refresh failed (non-fatal): %s", exc)
        res10b = {"status": "error", "error": str(exc)}
    _append("admin_market_data_audit", res10b, _time.monotonic() - _t0)

    _t0 = _time.monotonic()
    try:
        from backend.tasks.intelligence.tasks import generate_daily_digest_task

        res11 = generate_daily_digest_task(deliver_brain=True)
    except SoftTimeLimitExceeded:
        logger.warning("Task %s hit soft time limit", "admin_coverage_backfill")
        raise
    except Exception as exc:
        logger.warning("Daily digest generation failed (non-fatal): %s", exc)
        res11 = {"status": "error", "error": str(exc)}
    _append("intelligence_digest", res11, _time.monotonic() - _t0)

    step_results = [s.get("result") or {} for s in rollup["steps"]]
    n = len(step_results)
    err_n = sum(1 for r in step_results if r.get("status") == "error")
    if n == 0 or err_n == 0:
        rollup["status"] = "ok"
    elif err_n == n:
        rollup["status"] = "error"
    else:
        rollup["status"] = "partial"
    rollup["overall_summary"] = "; ".join(
        step["summary"] for step in rollup["steps"] if step.get("summary")
    )
    return rollup


@shared_task(
    soft_time_limit=120,
    time_limit=180,
)
@task_run("admin_coverage_refresh")
def health_check() -> dict:
    """Snapshot coverage health into Redis so the Admin UI can show stale counts."""
    from backend.services.market.coverage_utils import compute_coverage_status

    session = SessionLocal()
    try:
        snapshot = coverage_analytics.coverage_snapshot(session)
        try:
            snapshot.setdefault("meta", {})["backfill_5m_enabled"] = (
                infra.is_backfill_5m_enabled()
            )
        except Exception as e:
            logger.warning("backfill_5m_toggle_read failed: %s", e)
        status_info = compute_coverage_status(snapshot)
        snapshot["status"] = status_info
        payload = {
            "schema_version": 1,
            "snapshot": snapshot,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": status_info,
        }
        redis_client = infra.redis_client
        history_entry = {
            "ts": payload["updated_at"],
            "daily_pct": status_info.get("daily_pct"),
            "m5_pct": status_info.get("m5_pct"),
            "stale_daily": status_info.get("stale_daily"),
            "stale_m5": status_info.get("stale_m5"),
            "label": status_info.get("label"),
        }
        try:
            pipe = redis_client.pipeline()
            pipe.set("coverage:health:last", json.dumps(payload), ex=86400)
            pipe.lpush("coverage:health:history", json.dumps(history_entry))
            pipe.ltrim("coverage:health:history", 0, 47)
            pipe.execute()
        except Exception as e:
            logger.warning("redis_coverage_health_cache failed: %s", e)
        return {
            "status": status_info.get("label"),
            "daily_pct": status_info.get("daily_pct"),
            "m5_pct": status_info.get("m5_pct"),
            "stale_daily": status_info.get("stale_daily"),
            "stale_m5": status_info.get("stale_m5"),
            "tracked_count": snapshot.get("tracked_count", 0),
            "symbols": snapshot.get("symbols", 0),
        }
    finally:
        session.close()


@shared_task(
    soft_time_limit=3600,
    time_limit=3660,
)
def retry_pipeline_step(run_id: str, step: str) -> dict:
    """Retry a single pipeline step on a Celery worker (dispatched from admin UI)."""
    from backend.services.pipeline.orchestrator import run_pipeline

    return run_pipeline(
        run_id,
        steps=[step],
        triggered_by="admin_retry",
    )
