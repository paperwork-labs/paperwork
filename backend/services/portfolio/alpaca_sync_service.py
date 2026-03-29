"""Alpaca portfolio sync service.

Syncs positions, orders, and account balances from Alpaca Markets API
into broker-agnostic portfolio models.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.broker_account import BrokerAccount, BrokerType, AccountSync, SyncStatus
from backend.models.position import Position, PositionType, PositionStatus
from backend.models.trade import Trade
from backend.services.execution.alpaca_executor import AlpacaExecutor

logger = logging.getLogger(__name__)


class AlpacaSyncService:
    """Portfolio sync service for Alpaca Markets.
    
    Alpaca provides real-time positions and activity via REST API.
    This service syncs:
    - Positions (open positions with cost basis and market value)
    - Account balances (cash, buying power, equity)
    - Recent orders/trades
    """

    def __init__(self):
        self._executor = AlpacaExecutor()

    async def sync_account(
        self, db: Session, account: BrokerAccount, sync_type: str = "comprehensive"
    ) -> Dict:
        """Sync an Alpaca account.
        
        Args:
            db: Database session
            account: BrokerAccount instance for Alpaca
            sync_type: 'comprehensive', 'positions_only', 'balances_only'
        
        Returns:
            Dict with sync results
        """
        if account.broker != BrokerType.ALPACA:
            return {"status": "error", "error": "Account is not an Alpaca account"}

        # Create sync record
        sync_record = AccountSync(
            broker_account_id=account.id,
            sync_type=sync_type,
            status=SyncStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(sync_record)
        db.commit()

        try:
            results = {
                "positions": 0,
                "trades": 0,
                "account_updated": False,
            }

            # Sync positions
            if sync_type in ("comprehensive", "positions_only"):
                pos_result = await self._sync_positions(db, account)
                results["positions"] = pos_result.get("synced", 0)

            # Sync account balances
            if sync_type in ("comprehensive", "balances_only"):
                bal_result = await self._sync_balances(db, account)
                results["account_updated"] = bal_result.get("updated", False)

            # Sync recent activity/trades
            if sync_type == "comprehensive":
                trade_result = await self._sync_trades(db, account)
                results["trades"] = trade_result.get("synced", 0)

            # Update sync record
            sync_record.status = SyncStatus.COMPLETED
            sync_record.completed_at = datetime.now(timezone.utc)
            sync_record.records_synced = results["positions"] + results["trades"]
            db.commit()

            logger.info(
                "Alpaca sync complete for %s: %d positions, %d trades",
                account.account_number,
                results["positions"],
                results["trades"],
            )
            return {"status": "ok", **results}

        except Exception as e:
            sync_record.status = SyncStatus.FAILED
            sync_record.error_message = str(e)
            sync_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.exception("Alpaca sync failed for %s", account.account_number)
            return {"status": "error", "error": str(e)}

    async def _sync_positions(self, db: Session, account: BrokerAccount) -> Dict:
        """Sync positions from Alpaca."""
        alpaca_positions = await self._executor.get_positions()
        
        if not alpaca_positions:
            return {"synced": 0}

        # Get existing positions for this account
        existing = {
            p.symbol: p
            for p in db.query(Position).filter(
                Position.account_id == account.id,
                Position.status == PositionStatus.OPEN,
            ).all()
        }

        synced = 0
        alpaca_symbols = set()

        for ap in alpaca_positions:
            alpaca_symbols.add(ap.symbol)
            qty = Decimal(ap.qty)
            avg_cost = Decimal(ap.avg_entry_price)
            market_value = Decimal(ap.market_value)
            current_price = market_value / qty if qty != 0 else Decimal("0")

            if ap.symbol in existing:
                # Update existing position
                pos = existing[ap.symbol]
                pos.quantity = qty
                pos.average_cost = avg_cost
                pos.current_price = current_price
                pos.market_value = market_value
                pos.total_cost_basis = avg_cost * abs(qty)
                pos.unrealized_pnl = market_value - (avg_cost * abs(qty))
                pos.unrealized_pnl_pct = (
                    (pos.unrealized_pnl / pos.total_cost_basis * 100)
                    if pos.total_cost_basis else Decimal("0")
                )
                pos.position_updated_at = datetime.now(timezone.utc)
            else:
                # Create new position
                pos = Position(
                    user_id=account.user_id,
                    account_id=account.id,
                    symbol=ap.symbol,
                    quantity=qty,
                    position_type=PositionType.LONG if qty > 0 else PositionType.SHORT,
                    status=PositionStatus.OPEN,
                    average_cost=avg_cost,
                    total_cost_basis=avg_cost * abs(qty),
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=market_value - (avg_cost * abs(qty)),
                    broker_position_id=f"alpaca:{ap.symbol}",
                    position_updated_at=datetime.now(timezone.utc),
                )
                db.add(pos)

            synced += 1

        # Mark positions not in Alpaca as closed
        for symbol, pos in existing.items():
            if symbol not in alpaca_symbols:
                pos.status = PositionStatus.CLOSED
                pos.quantity = Decimal("0")
                pos.position_updated_at = datetime.now(timezone.utc)

        db.commit()
        return {"synced": synced}

    async def _sync_balances(self, db: Session, account: BrokerAccount) -> Dict:
        """Sync account balances from Alpaca."""
        acct_info = await self._executor.get_account()
        
        if "error" in acct_info:
            logger.warning("Failed to get Alpaca account: %s", acct_info["error"])
            return {"updated": False}

        # Update broker account with balance info
        account.cash_balance = Decimal(acct_info.get("cash", "0"))
        account.buying_power = Decimal(acct_info.get("buying_power", "0"))
        account.equity = Decimal(acct_info.get("equity", "0"))
        account.portfolio_value = Decimal(acct_info.get("portfolio_value", "0"))
        account.last_sync_at = datetime.now(timezone.utc)
        
        db.commit()
        return {"updated": True}

    async def _sync_trades(self, db: Session, account: BrokerAccount) -> Dict:
        """Sync recent trades/activities from Alpaca.
        
        Fetches FILL activities from Alpaca and upserts them as Trade records.
        Uses execution_id (Alpaca activity id) for deduplication.
        """
        from dateutil.parser import isoparse

        # Fetch last 30 days of fills
        after_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        activities = await self._executor.get_account_activities(
            activity_types="FILL",
            after=after_date,
        )

        if not activities:
            logger.info("Alpaca: no fill activities to sync for %s", account.account_number)
            return {"synced": 0}

        synced = 0
        skipped = 0
        is_paper = (
            getattr(settings, "ALPACA_TRADING_MODE", "paper").lower() == "paper"
        )

        for activity in activities:
            execution_id = activity.get("id")
            if not execution_id:
                skipped += 1
                continue

            # Check if trade already exists
            existing = (
                db.query(Trade)
                .filter(
                    Trade.account_id == account.id,
                    Trade.execution_id == execution_id,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            # Parse execution time
            exec_time_str = activity.get("transaction_time")
            exec_time = None
            if exec_time_str:
                try:
                    exec_time = isoparse(exec_time_str)
                except Exception:
                    exec_time = datetime.now(timezone.utc)

            # Map side
            side_raw = activity.get("side", "").upper()
            side = "BUY" if side_raw in ("BUY", "LONG") else "SELL"

            # Parse numeric fields
            qty = Decimal(str(activity.get("qty", 0)))
            price = Decimal(str(activity.get("price", 0)))
            total_value = qty * price

            trade = Trade(
                account_id=account.id,
                symbol=activity.get("symbol", ""),
                side=side,
                quantity=qty,
                price=price,
                total_value=total_value,
                order_id=activity.get("order_id"),
                execution_id=execution_id,
                execution_time=exec_time,
                status="FILLED",
                is_paper_trade=is_paper,
                commission=Decimal("0"),
                fees=Decimal("0"),
                trade_metadata=activity,
            )
            db.add(trade)
            synced += 1

        if synced > 0:
            db.flush()
            logger.info(
                "Alpaca: synced %d trades for %s (skipped %d existing)",
                synced,
                account.account_number,
                skipped,
            )

        return {"synced": synced, "skipped": skipped}

    def sync_account_sync(
        self, db: Session, account: BrokerAccount, sync_type: str = "comprehensive"
    ) -> Dict:
        """Synchronous wrapper for sync_account."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.sync_account(db, account, sync_type)
            )
        finally:
            loop.close()

    async def sync_account_comprehensive(
        self, account_number: str, db: Session
    ) -> Dict:
        """Unified contract method for BrokerSyncService compatibility.
        
        Args:
            account_number: The Alpaca account number/ID
            db: Database session
            
        Returns:
            Dict with sync results
        """
        account = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.account_number == account_number,
                BrokerAccount.broker == BrokerType.ALPACA,
            )
            .first()
        )
        if not account:
            return {"status": "error", "error": f"Alpaca account {account_number} not found"}
        
        return await self.sync_account(db, account, "comprehensive")


# Singleton for import convenience
alpaca_sync_service = AlpacaSyncService()
