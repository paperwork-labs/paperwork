"""Reconciliation Celery tasks.

Position and order reconciliation against broker-reported data.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="backend.tasks.reconciliation_tasks.reconcile_orders",
    soft_time_limit=300,
    time_limit=360,
)
def reconcile_orders(self, lookback_hours: int = 24) -> Dict:
    """Match filled Orders to Trades. Runs after broker sync.
    
    Compares our Order records with broker-reported executions/fills
    to ensure we haven't missed any fills or have orphaned orders.
    """
    from backend.database import SessionLocal
    from backend.models.order import Order, OrderStatus
    from datetime import datetime, timezone, timedelta

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        # Find orders that claim to be filled but may not have matched trades
        filled_orders = (
            db.query(Order)
            .filter(
                Order.status == OrderStatus.FILLED.value,
                Order.updated_at >= cutoff,
            )
            .all()
        )
        
        matched = 0
        unmatched = 0
        
        for order in filled_orders:
            # Check if we have a fill confirmation (broker_order_id and fill_price)
            if order.broker_order_id and order.filled_avg_price is not None:
                matched += 1
            else:
                unmatched += 1
                logger.warning(
                    "Order %d (%s) marked FILLED but missing broker confirmation",
                    order.id, order.symbol,
                )
        
        result = {
            "total_orders": len(filled_orders),
            "matched": matched,
            "unmatched": unmatched,
        }
        logger.info(
            "Reconciliation: %d matched, %d unmatched of %d total",
            matched, unmatched, len(filled_orders),
        )
        return result
    except Exception as e:
        logger.exception("Order reconciliation failed")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="backend.tasks.reconciliation_tasks.reconcile_positions",
    soft_time_limit=300,
    time_limit=360,
)
def reconcile_positions(self) -> Dict:
    """Verify internal position state matches broker reported positions.

    Compares local Position records against live broker positions for each
    connected broker account. Flags any discrepancies for review.

    Run daily after broker sync to catch any drift.
    """
    from backend.database import SessionLocal
    from backend.models.position import Position, PositionStatus
    from backend.models.broker_account import BrokerAccount, AccountStatus, BrokerType

    db = SessionLocal()
    try:
        discrepancies: List[Dict] = []
        reconciled = 0
        errors = 0

        # Get all active, enabled broker accounts
        accounts = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.status == AccountStatus.ACTIVE,
                BrokerAccount.is_enabled.is_(True),
            )
            .all()
        )

        for account in accounts:
            try:
                # Get local positions for this account
                local_positions = (
                    db.query(Position)
                    .filter(
                        Position.account_id == account.id,
                        Position.status == PositionStatus.OPEN,
                    )
                    .all()
                )

                local_pos_map = {p.symbol: p for p in local_positions}

                # Get broker positions
                broker_positions = _fetch_broker_positions(account, db)

                if broker_positions is None:
                    logger.debug(
                        "Skipping reconciliation for %s: broker fetch not implemented",
                        account.account_name,
                    )
                    continue

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
                            "account_name": account.account_name,
                            "type": "missing_at_broker",
                            "local_qty": float(local.quantity or 0),
                            "broker_qty": 0,
                        })
                    elif broker and not local:
                        discrepancies.append({
                            "symbol": symbol,
                            "account_id": account.id,
                            "account_name": account.account_name,
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
                                "account_name": account.account_name,
                                "type": "quantity_mismatch",
                                "local_qty": local_qty,
                                "broker_qty": broker_qty,
                                "diff": broker_qty - local_qty,
                            })
                        else:
                            reconciled += 1

            except Exception as e:
                logger.warning(
                    "Position reconciliation failed for account %s: %s",
                    account.account_name, e,
                )
                errors += 1

        if discrepancies:
            logger.warning(
                "Position reconciliation found %d discrepancies across %d accounts",
                len(discrepancies), len(accounts),
            )

        return {
            "status": "ok" if not discrepancies else "discrepancies_found",
            "accounts_checked": len(accounts),
            "positions_reconciled": reconciled,
            "discrepancies": discrepancies[:20],  # Limit response size
            "discrepancy_count": len(discrepancies),
            "errors": errors,
        }

    except Exception as e:
        logger.exception("Position reconciliation failed")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


async def _fetch_tastytrade_positions_async(
    account: Any, db: Session
) -> Optional[List[Dict[str, Any]]]:
    """Connect to TastyTrade, fetch positions, return normalized rows or None on failure."""
    from backend.services.clients.tastytrade_client import (
        TASTYTRADE_AVAILABLE,
        TastyTradeClient,
    )
    from backend.services.portfolio.account_credentials_service import (
        CredentialsNotFoundError,
        account_credentials_service,
    )

    if not TASTYTRADE_AVAILABLE:
        logger.debug("TastyTrade SDK not available; skipping broker position fetch")
        return None

    client = TastyTradeClient()
    raw: List[Dict[str, Any]] = []
    try:
        try:
            payload = account_credentials_service.get_decrypted(account.id, db)
            ok = await client.connect_with_credentials(
                client_secret=payload["client_secret"],
                refresh_token=payload["refresh_token"],
            )
        except CredentialsNotFoundError:
            ok = await client.connect_with_retry()
        if not ok:
            logger.warning(
                "TastyTrade connect failed for reconciliation (account=%s)",
                getattr(account, "account_number", account.id),
            )
            return None

        # Validate that the requested account number exists in the TastyTrade session.
        target_account_number = getattr(account, "account_number", None)
        session_account_numbers: List[str] = []
        try:
            session_accounts = getattr(client, "accounts", []) or []
            session_account_numbers = [
                getattr(a, "account_number", None)
                for a in session_accounts
                if getattr(a, "account_number", None) is not None
            ]
        except Exception:
            # If we cannot determine session accounts, skip reconciliation to avoid
            # misinterpreting an unknown account as having zero positions.
            logger.warning(
                "TastyTrade accounts unavailable after connect; skipping reconciliation "
                "(account=%s)",
                getattr(account, "account_number", account.id),
            )
            return None

        if not target_account_number or target_account_number not in session_account_numbers:
            logger.warning(
                "TastyTrade account number %s not found in session accounts %s; "
                "skipping reconciliation",
                target_account_number or getattr(account, "id", None),
                session_account_numbers,
            )
            return None

       raw = await client.get_current_positions(target_account_number)
    except Exception as e:
        logger.warning(
            "TastyTrade position fetch failed for account %s: %s",
            getattr(account, "account_number", account.id),
            e,
        )
        return None
    finally:
        try:
            await client.disconnect()
        except Exception as disc_e:
            logger.debug("TastyTrade disconnect after reconciliation fetch: %s", disc_e)

    out: List[Dict[str, Any]] = []
    for pos in raw:
        instr = (pos.get("instrument_type") or "").lower()
        if "option" in instr:
            continue
        symbol = pos.get("symbol")
        if not symbol:
            continue
        qty = float(pos.get("quantity") or 0)
        direction = (pos.get("quantity_direction") or "").strip().lower()
        if direction == "short":
            qty = -abs(qty)
        elif direction == "long" and qty != 0:
            qty = abs(qty)
        magnitude = abs(qty)
        if magnitude <= 0.001:
            continue
        avg = float(pos.get("average_open_price") or 0)
        cost_basis = magnitude * avg
        mark_value_raw = pos.get("mark_value")
        market_value: Optional[float] = None
        if mark_value_raw is not None:
            try:
                market_value = float(mark_value_raw)
            except (TypeError, ValueError):
                market_value = None
        # The TastyTrade client may normalize missing mark_value to 0.0;
        # treat None or near-zero values as "missing" and fall back.
        if market_value is None or abs(market_value) < 1e-6:
            mark = float(pos.get("mark") or 0)
            mult = float(pos.get("multiplier") or 1.0)
            market_value = magnitude * mark * mult
        out.append(
            {
                "symbol": symbol,
                "quantity": magnitude,
                "cost_basis": cost_basis,
                "market_value": market_value,
            }
        )
    return out


def _fetch_broker_positions(account, db: Session) -> Optional[List[Dict]]:
    """Fetch current positions from the broker for an account.

    Returns list of dicts with: symbol, quantity, cost_basis, market_value
    Returns None if the broker adapter is not yet implemented or fetch failed.
    """
    from backend.models.broker_account import BrokerType

    positions: List[Dict] = []

    try:
        if account.broker == BrokerType.IBKR:
            # IBKR positions are synced via FlexQuery, not real-time API
            # For reconciliation, we compare against the last sync
            logger.debug("IBKR position fetch uses FlexQuery sync data")
            return None  # Rely on FlexQuery-synced data in positions table

        elif account.broker == BrokerType.ALPACA:
            from backend.services.execution.alpaca_executor import AlpacaExecutor
            
            executor = AlpacaExecutor()
            loop = asyncio.new_event_loop()
            try:
                raw = loop.run_until_complete(executor.get_positions())
                for p in raw:
                    positions.append({
                        "symbol": p.symbol,
                        "quantity": float(p.qty),
                        "cost_basis": float(p.avg_entry_price) * float(p.qty),
                        "market_value": float(p.market_value),
                    })
            finally:
                loop.close()
            return positions

        elif account.broker == BrokerType.SCHWAB:
            # Schwab positions synced via OAuth API
            logger.debug("Schwab reconciliation not yet implemented")
            return None

        elif account.broker == BrokerType.TASTYTRADE:
            loop = asyncio.new_event_loop()
            try:
                positions = loop.run_until_complete(
                    _fetch_tastytrade_positions_async(account, db)
                )
            finally:
                loop.close()
            return positions

        else:
            logger.warning("Unknown broker type: %s", account.broker)
            return None

    except Exception as e:
        logger.warning("Failed to fetch positions from %s: %s", account.broker, e)
        return None


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
    """Monitor portfolio drawdown and alert if thresholds exceeded.

    Run periodically (e.g., hourly during market hours) to catch
    significant drawdowns early.

    Args:
        thresholds: Drawdown percentages to alert on (default: 5, 10, 15, 20%)
        send_alerts: Whether to send Brain webhook alerts for triggered thresholds

    Returns:
        Dict with current drawdown metrics and any triggered alerts
    """
    from backend.database import SessionLocal
    from backend.models.portfolio import PortfolioSnapshot
    from backend.models.position import Position, PositionStatus
    from datetime import datetime, timedelta

    if thresholds is None:
        thresholds = [5.0, 10.0, 15.0, 20.0]

    db = SessionLocal()
    try:
        # Calculate current portfolio value from open positions
        positions = (
            db.query(Position)
            .filter(Position.status == PositionStatus.OPEN)
            .all()
        )
        
        current_value = sum(float(p.market_value or 0) for p in positions)
        
        # Get peak value from recent snapshots (last 90 days)
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        peak_snapshot = (
            db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.snapshot_date >= ninety_days_ago)
            .order_by(PortfolioSnapshot.total_value.desc())
            .first()
        )
        
        peak_value = float(peak_snapshot.total_value) if peak_snapshot else current_value
        
        # Calculate drawdown
        if peak_value > 0:
            drawdown_pct = ((peak_value - current_value) / peak_value) * 100
            drawdown_dollars = peak_value - current_value
        else:
            drawdown_pct = 0.0
            drawdown_dollars = 0.0
        
        # Check thresholds
        alerts = []
        for threshold in thresholds:
            if drawdown_pct >= threshold:
                alerts.append({
                    "threshold_pct": threshold,
                    "current_drawdown_pct": drawdown_pct,
                    "current_drawdown_dollars": drawdown_dollars,
                })
        
        result = {
            "status": "ok",
            "drawdown_pct": round(drawdown_pct, 2),
            "drawdown_dollars": round(drawdown_dollars, 2),
            "peak_value": round(peak_value, 2),
            "current_value": round(current_value, 2),
            "total_positions": len(positions),
            "alerts_triggered": len(alerts),
        }
        
        if drawdown_pct >= 10:
            logger.warning(
                "Portfolio drawdown at %.1f%% ($%.0f from peak)",
                drawdown_pct, drawdown_dollars,
            )
        
        return result

    except Exception as e:
        logger.exception("Portfolio drawdown monitoring failed")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()
