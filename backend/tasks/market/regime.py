"""
Market Regime Tasks
===================

Celery tasks for market regime computation and monitoring.
"""

import logging
from celery import shared_task

from backend.database import SessionLocal
from backend.tasks.task_utils import task_run

logger = logging.getLogger(__name__)


@shared_task(
    name="backend.tasks.market.regime.compute_daily_regime",
    soft_time_limit=120,
    time_limit=180,
)
@task_run("compute_daily_regime")
def compute_daily_regime() -> dict:
    """Compute daily market regime state from VIX, breadth, and advance/decline data.

    This is the modular version. The original is still available at
    backend.tasks.market_data_tasks.compute_daily_regime
    """
    session = SessionLocal()
    try:
        from backend.services.market.regime_engine import compute_regime, persist_regime
        from backend.services.market.regime_inputs import gather_regime_inputs
        from datetime import date as date_type

        inputs = gather_regime_inputs(session)
        today = date_type.today()
        result = compute_regime(inputs, as_of=today)
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
        logger.exception("compute_daily_regime failed")
        raise
    finally:
        session.close()


@shared_task(
    name="backend.tasks.market.regime.monitor_vix_spike",
    soft_time_limit=60,
    time_limit=120,
)
@task_run("monitor_vix_spike")
def monitor_vix_spike(
    spike_threshold_pct: float = 15.0,
    absolute_threshold: float = 25.0,
) -> dict:
    """Monitor VIX for intraday spikes that warrant regime recalculation.

    Args:
        spike_threshold_pct: Percent change from prior close to trigger alert
        absolute_threshold: Absolute VIX level that always triggers recalc
    """
    session = SessionLocal()
    try:
        import yfinance as yf
        from datetime import date as date_type

        vix_df = yf.download("^VIX", period="5d", progress=False)
        if vix_df is None or vix_df.empty:
            return {"status": "no_data", "vix_current": None}

        vix_current = float(vix_df["Close"].iloc[-1])
        vix_prior = float(vix_df["Close"].iloc[-2]) if len(vix_df) >= 2 else vix_current
        vix_change_pct = ((vix_current - vix_prior) / vix_prior * 100) if vix_prior > 0 else 0

        spike_detected = (
            vix_change_pct >= spike_threshold_pct or
            vix_current >= absolute_threshold
        )

        result = {
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
                vix_current, vix_change_pct, vix_prior
            )

            try:
                from backend.services.market.regime_engine import compute_regime, persist_regime
                from backend.services.market.regime_inputs import gather_regime_inputs

                inputs = gather_regime_inputs(session)
                today = date_type.today()
                regime_result = compute_regime(inputs, as_of=today)
                persist_regime(session, regime_result)
                session.commit()

                result["regime_recalculated"] = True
                result["new_regime_state"] = regime_result.regime_state
                result["new_composite_score"] = regime_result.composite_score

            except Exception as e:
                logger.warning("Regime recalculation after VIX spike failed: %s", e)
                result["regime_error"] = str(e)

        return result

    except Exception:
        logger.exception("monitor_vix_spike failed")
        raise
    finally:
        session.close()
