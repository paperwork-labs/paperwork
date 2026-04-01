"""
Market regime computation (R1–R5) and intraday VIX spike monitoring.
"""

from __future__ import annotations

import logging
from datetime import date as date_type

from celery import shared_task
from sqlalchemy import func

from backend.database import SessionLocal
from backend.models.market_data import PriceData
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


def _regime_as_of_date(session) -> date_type:
    """Use latest daily bar date in DB so regime rows align with market data, not calendar today."""
    spy_dt = (
        session.query(func.max(PriceData.date))
        .filter(PriceData.symbol == "SPY", PriceData.interval == "1d")
        .scalar()
    )
    if spy_dt is not None:
        return spy_dt.date() if hasattr(spy_dt, "date") else spy_dt
    latest_dt = (
        session.query(func.max(PriceData.date))
        .filter(PriceData.interval == "1d")
        .scalar()
    )
    if latest_dt is not None:
        return latest_dt.date() if hasattr(latest_dt, "date") else latest_dt
    logger.warning(
        "Regime as_of: no 1d PriceData in DB; using calendar today (may misalign vs snapshots)"
    )
    return date_type.today()


@shared_task(
    soft_time_limit=120,
    time_limit=180,
)
@task_run("compute_daily_regime")
def compute_daily() -> dict:
    """Compute and persist the daily market regime state (R1–R5).

    Fetches VIX, breadth, and advance/decline inputs, then runs the
    regime engine to produce a composite score and state. Safe to run
    repeatedly — uses upsert semantics on as_of_date.
    """
    session = SessionLocal()
    try:
        from backend.services.market.regime_engine import compute_regime, persist_regime
        from backend.services.market.regime_inputs import gather_regime_inputs

        inputs = gather_regime_inputs(session)
        as_of = _regime_as_of_date(session)
        result = compute_regime(inputs, as_of=as_of)
        row = persist_regime(session, result)
        session.commit()

        return {
            "regime_state": result.regime_state,
            "composite_score": result.composite_score,
            "as_of_date": row.as_of_date.isoformat() if row and row.as_of_date else None,
            "inputs": {
                "vix_spot": inputs.vix_spot,
                "nh_nl": inputs.nh_nl,
                "pct_above_200d": inputs.pct_above_200d,
                "pct_above_50d": inputs.pct_above_50d,
            },
        }
    except Exception:
        logger.exception("compute_daily failed")
        raise
    finally:
        session.close()


@shared_task(
    soft_time_limit=60,
    time_limit=120,
)
@task_run("monitor_vix_spike")
def vix_alert(
    spike_threshold_pct: float = 15.0,
    absolute_threshold: float = 25.0,
) -> dict:
    """Monitor VIX for intraday spikes that warrant regime recalculation.

    Runs frequently during market hours (e.g., every 15 minutes).
    Triggers regime recomputation if VIX spikes significantly.

    Args:
        spike_threshold_pct: Percent change from prior close to trigger alert
        absolute_threshold: Absolute VIX level that always triggers recalc

    Returns:
        Dict with spike detection results and any actions taken
    """
    session = SessionLocal()
    try:
        import yfinance as yf

        vix_df = yf.download("^VIX", period="5d", progress=False)
        if vix_df is None or vix_df.empty:
            return {"status": "no_data", "vix_current": None}

        vix_current = float(vix_df["Close"].iloc[-1])
        vix_prior = (
            float(vix_df["Close"].iloc[-2]) if len(vix_df) >= 2 else vix_current
        )
        vix_change_pct = (
            ((vix_current - vix_prior) / vix_prior * 100) if vix_prior > 0 else 0
        )

        spike_detected = vix_change_pct >= spike_threshold_pct or vix_current >= absolute_threshold

        result: dict = {
            "status": "ok",
            "vix_current": round(vix_current, 2),
            "vix_prior": round(vix_prior, 2),
            "vix_change_pct": round(vix_change_pct, 2),
            "spike_detected": spike_detected,
            "regime_recalculated": False,
        }

        if spike_detected:
            logger.warning(
                "VIX spike detected: %.1f (%.1f%% change from %.1f)",
                vix_current,
                vix_change_pct,
                vix_prior,
            )

            try:
                from backend.services.market.regime_engine import compute_regime, persist_regime
                from backend.services.market.regime_inputs import gather_regime_inputs

                inputs = gather_regime_inputs(session)
                as_of = _regime_as_of_date(session)
                regime_result = compute_regime(inputs, as_of=as_of)
                persist_regime(session, regime_result)
                session.commit()

                result["regime_recalculated"] = True
                result["new_regime_state"] = regime_result.regime_state
                result["new_composite_score"] = regime_result.composite_score

                logger.info(
                    "Regime recalculated due to VIX spike: %s (score: %.1f)",
                    regime_result.regime_state,
                    regime_result.composite_score,
                )

                try:
                    from backend.services.notifications.notification_service import (
                        notification_service,
                    )

                    if notification_service.is_brain_configured():
                        notification_service.notify_system_sync(
                            "VIX spike — regime recalculated",
                            (
                                f"VIX: {vix_current:.1f} ({vix_change_pct:+.1f}% from {vix_prior:.1f}). "
                                f"Regime: {regime_result.regime_state} "
                                f"(score: {regime_result.composite_score:.1f}). "
                                f"Multiplier: {regime_result.regime_multiplier:.2f}x"
                            ),
                            brain_event="vix_spike_regime",
                            extra_data={
                                "vix_current": vix_current,
                                "vix_prior": vix_prior,
                                "vix_change_pct": vix_change_pct,
                                "regime_state": regime_result.regime_state,
                                "composite_score": regime_result.composite_score,
                                "regime_multiplier": regime_result.regime_multiplier,
                            },
                        )
                except Exception as e:
                    logger.debug("Brain notification failed: %s", e)

            except Exception as e:
                logger.warning("Regime recalculation after VIX spike failed: %s", e)
                result["regime_error"] = str(e)

        return result

    except Exception:
        logger.exception("vix_alert failed")
        raise
    finally:
        session.close()
