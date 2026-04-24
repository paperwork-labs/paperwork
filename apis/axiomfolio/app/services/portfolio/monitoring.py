"""
Portfolio Monitoring Service
============================

Tracks portfolio health metrics including drawdown monitoring and alerts.

medallion: silver
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


def calculate_portfolio_drawdown(
    db: Session,
    lookback_days: int = 252,
) -> Dict:
    """Calculate current portfolio drawdown from peak.

    Args:
        db: SQLAlchemy session
        lookback_days: Days of history to consider for peak

    Returns:
        Dict with:
        - current_value: Current portfolio value
        - peak_value: Highest portfolio value in lookback period
        - drawdown_pct: Percentage drawdown from peak
        - drawdown_dollars: Dollar drawdown from peak
        - peak_date: Date of peak value
        - days_since_peak: Trading days since peak
    """
    from app.models.portfolio import PortfolioSnapshot

    cutoff = date.today() - timedelta(days=lookback_days)

    # Get portfolio value history
    snapshots = (
        db.query(PortfolioSnapshot.date, PortfolioSnapshot.total_value)
        .filter(PortfolioSnapshot.date >= cutoff)
        .order_by(PortfolioSnapshot.date)
        .all()
    )

    if not snapshots:
        return {
            "current_value": None,
            "peak_value": None,
            "drawdown_pct": 0.0,
            "drawdown_dollars": 0.0,
            "peak_date": None,
            "days_since_peak": 0,
        }

    current_value = float(snapshots[-1].total_value) if snapshots[-1].total_value else 0.0
    peak_value = current_value
    peak_date = snapshots[-1].date

    for snap in snapshots:
        val = float(snap.total_value) if snap.total_value else 0.0
        if val > peak_value:
            peak_value = val
            peak_date = snap.date

    drawdown_dollars = peak_value - current_value
    drawdown_pct = (drawdown_dollars / peak_value * 100) if peak_value > 0 else 0.0

    days_since_peak = (date.today() - peak_date).days if peak_date else 0

    return {
        "current_value": current_value,
        "peak_value": peak_value,
        "drawdown_pct": round(drawdown_pct, 2),
        "drawdown_dollars": round(drawdown_dollars, 2),
        "peak_date": peak_date.isoformat() if peak_date else None,
        "days_since_peak": days_since_peak,
    }


def check_drawdown_alerts(
    db: Session,
    thresholds: Optional[List[float]] = None,
) -> List[Dict]:
    """Check if portfolio drawdown has exceeded alert thresholds.

    Args:
        db: SQLAlchemy session
        thresholds: List of drawdown percentages to alert on (default: 5%, 10%, 15%, 20%)

    Returns:
        List of triggered alert dicts
    """
    if thresholds is None:
        thresholds = [5.0, 10.0, 15.0, 20.0]

    drawdown = calculate_portfolio_drawdown(db)
    dd_pct = drawdown.get("drawdown_pct", 0.0)

    alerts = []
    for threshold in sorted(thresholds):
        if dd_pct >= threshold:
            alerts.append({
                "type": "drawdown_exceeded",
                "threshold_pct": threshold,
                "actual_pct": dd_pct,
                "drawdown_dollars": drawdown.get("drawdown_dollars"),
                "peak_value": drawdown.get("peak_value"),
                "current_value": drawdown.get("current_value"),
                "peak_date": drawdown.get("peak_date"),
                "severity": "critical" if threshold >= 20 else "warning" if threshold >= 10 else "info",
            })

    return alerts


def send_drawdown_alert(alert: Dict) -> bool:
    """Send a drawdown alert to Brain webhook.

    Args:
        alert: Alert dict from check_drawdown_alerts

    Returns:
        True if sent successfully
    """
    try:
        from app.services.notifications.notification_service import notification_service

        if not notification_service.is_brain_configured():
            logger.warning("Brain webhook not configured, skipping drawdown alert")
            return False

        severity = alert.get("severity", "info")
        title = "Portfolio drawdown alert"
        message = (
            f"Drawdown: {alert.get('actual_pct', 0):.1f}% (threshold: {alert.get('threshold_pct', 0):.0f}%). "
            f"Peak: ${alert.get('peak_value', 0):,.0f} on {alert.get('peak_date', 'N/A')}. "
            f"Current: ${alert.get('current_value', 0):,.0f}. "
            f"Loss from peak: ${alert.get('drawdown_dollars', 0):,.0f}."
        )

        return notification_service.notify_system_sync(
            title,
            message,
            brain_event="portfolio_drawdown",
            extra_data={"severity": severity, "alert": alert},
        )

    except Exception as e:
        logger.warning("Failed to send drawdown alert: %s", e)
        return False


def get_portfolio_health_metrics(db: Session) -> Dict:
    """Get comprehensive portfolio health metrics.

    Returns:
        Dict with drawdown, concentration risk, and other health metrics
    """
    from app.models.position import Position, PositionStatus

    # Calculate drawdown
    drawdown = calculate_portfolio_drawdown(db)

    # Get position concentration
    positions = db.query(Position).filter(Position.status == PositionStatus.OPEN).all()
    total_value = sum(float(p.market_value or 0) for p in positions)

    concentration = {}
    if total_value > 0:
        for p in positions:
            pct = float(p.market_value or 0) / total_value * 100
            if pct >= 10:  # Track positions > 10% of portfolio
                concentration[p.symbol] = round(pct, 2)

    # Identify largest position
    max_concentration = max(concentration.values()) if concentration else 0.0
    largest_position = max(concentration, key=concentration.get) if concentration else None

    return {
        "drawdown": drawdown,
        "total_positions": len(positions),
        "total_value": round(total_value, 2),
        "max_concentration_pct": max_concentration,
        "largest_position": largest_position,
        "positions_over_10pct": list(concentration.keys()),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
