#!/usr/bin/env python3
"""TastyTrade Sync Service
Pulls positions, transactions, balances, dividends from Tastytrade API and
persists to AxiomFolio broker-agnostic tables.
"""

from __future__ import annotations

import logging
from typing import Dict

from sqlalchemy.orm import Session
from datetime import datetime as dt
import re
from backend.services.clients.tastytrade_client import TastyTradeClient
from backend.models import (
    BrokerAccount,
    Position,
    Option,
    Trade,
    Transaction,
    Dividend,
    AccountBalance,
)
from backend.models.position import PositionType
from backend.models.transaction import TransactionType
from backend.models.account_balance import AccountBalanceType

logger = logging.getLogger(__name__)


class TastyTradeSyncService:
    """High-level orchestrator for Tastytrade data → DB."""

    def __init__(self):
        self.client = TastyTradeClient()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    async def sync_account(
        self, db: Session, broker_account: BrokerAccount
    ) -> Dict[str, int]:
        """Sync ALL objects for the given broker account. Returns row counts."""
        counts: Dict[str, int] = {}
        # Ensure connection prior to any fetches
        try:
            await self.client.connect_with_retry()
        except Exception:
            pass

        # Ensure the requested account number exists in the connected TT session
        try:
            if getattr(self.client, "accounts", None):
                tt_numbers = [
                    getattr(a, "account_number", None) for a in self.client.accounts
                ]
                if broker_account.account_number not in tt_numbers and tt_numbers:
                    logger.warning(
                        "Account %s not found in TastyTrade session; updating to %s",
                        broker_account.account_number,
                        tt_numbers[0],
                    )
                    broker_account.account_number = tt_numbers[0]
                    db.add(broker_account)
                    db.commit()
        except Exception:
            pass

        counts.update(await self._sync_positions(db, broker_account))
        counts.update(await self._sync_trades(db, broker_account))
        counts.update(await self._sync_transactions(db, broker_account))
        counts.update(await self._sync_dividends(db, broker_account))
        counts.update(await self._sync_account_balances(db, broker_account))

        logger.info("TastyTrade sync complete → %s", counts)
        return counts

    async def sync_account_comprehensive(
        self, account_number: str, db_session=None
    ) -> Dict[str, int]:
        """Adapter to align with broker-agnostic sync interface used by BrokerSyncService."""
        db = db_session or self._get_db_session()
        try:
            # Resolve BrokerAccount by account_number
            ba = (
                db.query(BrokerAccount)
                .filter(BrokerAccount.account_number == account_number)
                .first()
            )
            if not ba:
                return {"status": "error", "error": "Broker account not found"}
            return await self.sync_account(db, ba)
        finally:
            if db_session is None:
                try:
                    db.close()
                except Exception:
                    pass

    def _get_db_session(self) -> Session:
        # Lazy import to avoid circulars
        from backend.database import SessionLocal

        return SessionLocal()

    # ------------------------------------------------------------------
    # Internal helpers (1 per table)
    # ------------------------------------------------------------------

    async def _sync_positions(self, db: Session, ba: BrokerAccount) -> Dict[str, int]:
        data = await self.client.get_current_positions(ba.account_number)
        db.query(Position).filter_by(account_id=ba.id).delete()
        db.query(Option).filter_by(account_id=ba.id).delete()

        count = 0
        seen_option_keys = set()
        for pos in data:
            try:
                qty = float(pos.get("quantity", 0) or 0)
                if qty == 0:
                    continue

                instr_type = (pos.get("instrument_type") or "").lower()
                if "option" in instr_type:
                    kwargs = self._option_position_kwargs(pos, ba)
                    if kwargs:
                        # dedupe by (account_id, underlying, strike, expiry, type)
                        key = (
                            ba.id,
                            kwargs.get("underlying_symbol"),
                            float(kwargs.get("strike_price")),
                            kwargs.get("expiry_date"),
                            kwargs.get("option_type"),
                        )
                        if key in seen_option_keys:
                            continue
                        seen_option_keys.add(key)
                        db.add(Option(**kwargs))
                        count += 1
                else:
                    kwargs = self._equity_position_kwargs(pos, ba)
                    if kwargs:
                        db.add(Position(**kwargs))
                        count += 1
            except Exception:
                continue

        db.flush()
        return {"positions": count}

    async def _sync_trades(self, db: Session, ba: BrokerAccount) -> Dict[str, int]:
        trades = await self.client.get_trade_history(ba.account_number, days=365)
        db.query(Trade).filter_by(account_id=ba.id).delete()
        seen_execs = set()
        for t in trades:
            kwargs = self._trade_to_kwargs(t, ba)
            exec_id = kwargs.get("execution_id") or kwargs.get("order_id")
            if exec_id and exec_id in seen_execs:
                continue
            if exec_id:
                seen_execs.add(exec_id)
            db.add(Trade(**kwargs))
        db.flush()
        return {"trades": len(trades)}

    async def _sync_transactions(
        self, db: Session, ba: BrokerAccount
    ) -> Dict[str, int]:
        txns = await self.client.get_transactions(ba.account_number, days=365)
        db.query(Transaction).filter_by(account_id=ba.id).delete()
        count = 0
        seen_txn_ids = set()
        for txn in txns:
            try:
                kwargs = self._txn_to_kwargs(txn, ba)
                ext_id = (
                    kwargs.get("external_id")
                    or kwargs.get("execution_id")
                    or kwargs.get("order_id")
                )
                if ext_id and ext_id in seen_txn_ids:
                    continue
                if ext_id:
                    seen_txn_ids.add(ext_id)
                db.add(Transaction(**kwargs))
                count += 1
            except Exception:
                continue
        db.flush()
        return {"transactions": count}

    async def _sync_dividends(self, db: Session, ba: BrokerAccount) -> Dict[str, int]:
        divs = await self.client.get_dividends(ba.account_number, days=365)
        db.query(Dividend).filter_by(account_id=ba.id).delete()
        count = 0
        for d in divs:
            try:
                db.add(Dividend(**self._div_to_kwargs(d, ba)))
                count += 1
            except Exception:
                continue
        db.flush()
        return {"dividends": count}

    async def _sync_account_balances(
        self, db: Session, ba: BrokerAccount
    ) -> Dict[str, int]:
        bal = await self.client.get_account_balances(ba.account_number)
        if not bal:
            return {"account_balances": 0}
        db.query(AccountBalance).filter_by(broker_account_id=ba.id).delete()
        # Map fields to our model
        mapped = dict(
            user_id=ba.user_id,
            broker_account_id=ba.id,
            balance_type=AccountBalanceType.REALTIME,
            cash_balance=bal.get("cash_balance"),
            net_liquidation=bal.get("net_liquidating_value"),
            gross_position_value=(bal.get("long_margin_value", 0) or 0)
            + (bal.get("short_margin_value", 0) or 0),
            buying_power=bal.get("net_liquidating_value"),
            data_source="TASTYTRADE",
        )
        db.add(AccountBalance(**mapped))
        db.flush()
        return {"account_balances": 1}

    # ------------------------------------------------------------------
    # Converters
    # ------------------------------------------------------------------

    def _equity_position_kwargs(self, p: Dict, ba: BrokerAccount) -> Dict:
        quantity = float(p.get("quantity", 0) or 0)
        avg_cost = p.get("average_open_price") or 0
        total_cost_basis = abs(quantity) * float(avg_cost)
        current_price = p.get("mark")
        market_value = p.get("mark_value") or (
            abs(quantity) * float(current_price or 0)
        )
        unrealized = None
        try:
            unrealized = float(market_value) - float(total_cost_basis)
        except Exception:
            pass
        position_type = PositionType.LONG if quantity >= 0 else PositionType.SHORT
        return dict(
            user_id=ba.user_id,
            account_id=ba.id,
            symbol=p.get("symbol"),
            quantity=abs(quantity),
            average_cost=avg_cost,
            total_cost_basis=total_cost_basis,
            market_value=market_value,
            instrument_type="STOCK",
            position_type=position_type,
            current_price=current_price,
            unrealized_pnl=unrealized,
        )

    def _trade_to_kwargs(self, t: Dict, ba: BrokerAccount) -> Dict:
        return dict(
            account_id=ba.id,
            symbol=t["symbol"],
            side=t["side"],
            quantity=t["quantity"],
            price=t["price"],
            order_id=t.get("order_id"),
            execution_id=t.get("execution_id"),
            created_at=dt.fromisoformat(t["executed_at"]),
        )

    def _txn_to_kwargs(self, tx: Dict, ba: BrokerAccount) -> Dict:
        # Compose datetime from separate date/time fields
        dt_str = f"{tx.get('date')}T{tx.get('time')}"
        try:
            txn_dt = dt.fromisoformat(dt_str)
        except Exception:
            txn_dt = dt.utcnow()

        action = (tx.get("action") or "").upper()
        if action == "BUY":
            ttype = TransactionType.BUY
        elif action == "SELL":
            ttype = TransactionType.SELL
        else:
            ttype = TransactionType.OTHER

        return dict(
            account_id=ba.id,
            symbol=tx.get("symbol", "CASH"),
            transaction_type=ttype,
            action=action,
            quantity=tx.get("quantity"),
            trade_price=tx.get("price"),
            amount=tx.get("amount"),
            commission=tx.get("commission"),
            net_amount=tx.get("net_amount"),
            currency=tx.get("currency", "USD"),
            transaction_date=txn_dt,
            external_id=tx.get("id"),
            order_id=tx.get("order_id"),
            execution_id=tx.get("execution_id"),
            source="tastytrade_enhanced",
            asset_category=(
                "OPT" if "option" in (tx.get("contract_type", "").lower()) else "STK"
            ),
        )

    def _div_to_kwargs(self, d: Dict, ba: BrokerAccount) -> Dict:
        # d is shaped by _transform_tastytrade_transaction
        ex_date = (
            dt.fromisoformat(d.get("date") + "T" + d.get("time"))
            if d.get("date") and d.get("time")
            else dt.utcnow()
        )
        total = abs(float(d.get("amount", 0) or 0))
        shares = abs(float(d.get("quantity", 0) or 0))
        per_share = (total / shares) if shares > 0 else None
        return dict(
            account_id=ba.id,
            symbol=d.get("symbol", ""),
            ex_date=ex_date,
            pay_date=ex_date,
            total_dividend=total,
            dividend_per_share=per_share if per_share is not None else total,
            shares_held=shares,
        )

    def _option_position_kwargs(self, p: Dict, ba: BrokerAccount) -> Dict:
        quantity = int(abs(float(p.get("quantity", 0) or 0)))
        if quantity == 0:
            return {}
        # Try read directly from payload
        symbol = p.get("symbol") or ""
        underlying_symbol = p.get("underlying_symbol")
        strike_price = p.get("strike_price")
        option_type = (p.get("option_type") or "").upper()
        exp = p.get("expiration_date")
        exp_date = None
        if isinstance(exp, str):
            try:
                exp_date = dt.strptime(exp, "%Y-%m-%d").date()
            except Exception:
                exp_date = None
        elif exp and hasattr(exp, "strftime"):
            try:
                exp_date = exp
            except Exception:
                exp_date = None

        # Fallback: parse OCC-like option symbol, e.g. "SOUN  250815C00013000"
        if not (strike_price and exp_date and option_type and underlying_symbol):
            m = re.match(
                r"^([A-Z\.]{1,6})\s+(\d{6})([CP])(\d{8})$", symbol.strip().upper()
            )
            if m:
                underlying_symbol = underlying_symbol or m.group(1)
                yymmdd = m.group(2)
                yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
                exp_date = (
                    exp_date
                    or dt.strptime(f"20{yy:02d}-{mm:02d}-{dd:02d}", "%Y-%m-%d").date()
                )
                option_type = option_type or ("CALL" if m.group(3) == "C" else "PUT")
                # strike encoded with 3 decimals in 8 digits
                strike_enc = m.group(4)
                strike_price = strike_price or (int(strike_enc) / 1000.0)

        # Required fields guard
        if strike_price is None or exp_date is None or not option_type:
            return {}

        avg_cost = p.get("average_open_price") or 0
        mark_val = p.get("mark_value") or 0
        mult = p.get("multiplier", 100) or 100
        total_cost = abs(float(quantity)) * float(avg_cost) * float(mult)
        unrealized = (
            (float(mark_val) - float(total_cost)) if (mark_val is not None) else None
        )

        return dict(
            user_id=ba.user_id,
            account_id=ba.id,
            symbol=symbol,
            underlying_symbol=underlying_symbol,
            strike_price=float(strike_price),
            expiry_date=exp_date,
            option_type=option_type,
            multiplier=mult,
            open_quantity=quantity,
            current_price=p.get("mark"),
            unrealized_pnl=unrealized,
            currency="USD",
            data_source="TASTYTRADE",
        )
