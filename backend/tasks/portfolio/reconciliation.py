"""Reconciliation Celery tasks."""

import logging
from typing import Dict, List
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="backend.tasks.reconciliation_tasks.reconcile_orders", soft_time_limit=300, time_limit=360)
def reconcile_orders(self, lookback_hours: int = 24):
    """Match filled Orders to Trades. Runs after broker sync."""
    from backend.database import SessionLocal
    from backend.services.portfolio.reconciliation import reconciliation_service

    db = SessionLocal()
    try:
        result = reconciliation_service.reconcile_fills(db, lookback_hours=lookback_hours)
        logger.info(
            "Reconciliation: %d matched, %d unmatched of %d total",
            result["matched"],
            result["unmatched"],
            result["total_orders"],
        )
        return result
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="backend.tasks.reconciliation_tasks.reconcile_positions",
    soft_time_limit=300,
    time_limit=360,
)
def reconcile_positions(self) -> Dict:
    """Verify algorithm position state matches broker reported positions.

    Compares local Position records against live broker positions for each
    connected broker. Flags any discrepancies for review.

    Run daily after broker sync to catch any drift.
    """
    from backend.database import SessionLocal
    from backend.models.position import Position
    from backend.models.broker import BrokerAccount

    db = SessionLocal()
    try:
        discrepancies: List[Dict] = []
        reconciled = 0
        errors = 0

        # Get all active broker accounts
        accounts = db.query(BrokerAccount).filter(
            BrokerAccount.is_active.is_(True)
        ).all()

        for account in accounts:
            try:
                # Get local positions for this account
                local_positions = db.query(Position).filter(
                    Position.broker_account_id == account.id,
                    Position.status == "open",
                ).all()

                local_pos_map = {p.symbol: p for p in local_positions}

                # Get broker positions
                broker_positions = _fetch_broker_positions(account)

                broker_pos_map = {bp["symbol"]: bp for bp in broker_positions}

                # Check for discrepancies
                all_symbols = set(local_pos_map.keys()) | set(broker_pos_map.keys())

                for symbol in all_symbols:
                    local = local_pos_map.get(symbol)
                    broker = broker_pos_map.get(symbol)

                    if local and not broker:
                        discrepancies.append({
                            "symbol": symbol,
                            "account_id": account.id,
                            "account_name": account.name,
                            "type": "missing_at_broker",
                            "local_qty": local.quantity,
                            "broker_qty": 0,
                        })
                    elif broker and not local:
                        discrepancies.append({
                            "symbol": symbol,
                            "account_id": account.id,
                            "account_name": account.name,
                            "type": "missing_locally",
                            "local_qty": 0,
                            "broker_qty": broker.get("quantity"),
                        })
                    elif local and broker:
                        local_qty = float(local.quantity or 0)
                        broker_qty = float(broker.get("quantity") or 0)
                        if abs(local_qty - broker_qty) > 0.001:
                            discrepancies.append({
                                "symbol": symbol,
                                "account_id": account.id,
                                "account_name": account.name,
                                "type": "quantity_mismatch",
                                "local_qty": local_qty,
                                "broker_qty": broker_qty,
                                "diff": broker_qty - local_qty,
                            })
                        else:
                            reconciled += 1

            except Exception as e:
                logger.warning("Position reconciliation failed for account %s: %s", account.name, e)
                errors += 1

        if discrepancies:
            logger.warning(
                "Position reconciliation found %d discrepancies across %d accounts",
                len(discrepancies),
                len(accounts),
            )

        return {
            "status": "ok" if not discrepancies else "discrepancies_found",
            "accounts_checked": len(accounts),
            "positions_reconciled": reconciled,
            "discrepancies": discrepancies[:20],  # Limit to 20 for response size
            "discrepancy_count": len(discrepancies),
            "errors": errors,
        }

    except Exception as e:
        logger.exception("Position reconciliation failed")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


def _fetch_broker_positions(account) -> List[Dict]:
    """Fetch current positions from the broker for an account.

    Returns list of dicts with: symbol, quantity, cost_basis, market_value
    """
    positions = []

    try:
        if account.broker_type == "ibkr":
            from backend.services.clients.ibkr_client import ibkr_client
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                raw = loop.run_until_complete(ibkr_client.get_positions())
                for p in raw:
                    positions.append({
                        "symbol": p.get("symbol"),
                        "quantity": p.get("quantity") or p.get("position"),
                        "cost_basis": p.get("avg_cost"),
                        "market_value": p.get("market_value"),
                    })
            finally:
                loop.close()

        elif account.broker_type == "schwab":
            from backend.services.clients.schwab_client import schwab_service
            raw = schwab_service.get_positions(account.account_number)
            for p in raw:
                positions.append({
                    "symbol": p.get("symbol"),
                    "quantity": p.get("quantity"),
                    "cost_basis": p.get("costBasis"),
                    "market_value": p.get("marketValue"),
                })

        elif account.broker_type == "tastytrade":
            from backend.services.clients.tastytrade_client import tastytrade_service
            raw = tastytrade_service.get_positions(account.account_number)
            for p in raw:
                positions.append({
                    "symbol": p.get("symbol"),
                    "quantity": p.get("quantity"),
                    "cost_basis": p.get("average_open_price"),
                    "market_value": p.get("market_value"),
                })

    except Exception as e:
        logger.warning("Failed to fetch positions from %s: %s", account.broker_type, e)

    return positions


@celery_app.task(
    bind=True,
    name="backend.tasks.reconciliation_tasks.monitor_portfolio_drawdown",
    soft_time_limit=120,
    time_limit=180,
)
def monitor_portfolio_drawdown(
    self,
    thresholds: List[float] = None,
    send_alerts: bool = True,
) -> Dict:
    """Monitor portfolio drawdown and send alerts if thresholds exceeded.

    Run this task periodically (e.g., hourly during market hours) to
    catch significant drawdowns early.

    Args:
        thresholds: Drawdown percentages to alert on (default: 5, 10, 15, 20%)
        send_alerts: Whether to send Discord alerts for triggered thresholds

    Returns:
        Dict with current drawdown metrics and any triggered alerts
    """
    from backend.database import SessionLocal
    from backend.services.portfolio.monitoring import (
        calculate_portfolio_drawdown,
        check_drawdown_alerts,
        send_drawdown_alert,
        get_portfolio_health_metrics,
    )

    db = SessionLocal()
    try:
        # Get full health metrics
        health = get_portfolio_health_metrics(db)
        drawdown = health.get("drawdown", {})

        # Check for alerts
        alerts = check_drawdown_alerts(db, thresholds)

        # Send alerts if enabled
        alerts_sent = 0
        if send_alerts and alerts:
            # Only send the highest severity alert to avoid spam
            highest_alert = max(alerts, key=lambda a: a.get("threshold_pct", 0))
            if send_drawdown_alert(highest_alert):
                alerts_sent = 1

        result = {
            "status": "ok",
            "drawdown_pct": drawdown.get("drawdown_pct", 0.0),
            "drawdown_dollars": drawdown.get("drawdown_dollars", 0.0),
            "peak_value": drawdown.get("peak_value"),
            "current_value": drawdown.get("current_value"),
            "days_since_peak": drawdown.get("days_since_peak", 0),
            "alerts_triggered": len(alerts),
            "alerts_sent": alerts_sent,
            "max_concentration_pct": health.get("max_concentration_pct", 0),
            "total_positions": health.get("total_positions", 0),
        }

        if drawdown.get("drawdown_pct", 0) >= 10:
            logger.warning(
                "Portfolio drawdown at %.1f%% ($%.0f from peak)",
                drawdown.get("drawdown_pct", 0),
                drawdown.get("drawdown_dollars", 0),
            )

        return result

    except Exception as e:
        logger.exception("Portfolio drawdown monitoring failed")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()
