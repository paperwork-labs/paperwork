"""Statements endpoint powering frontend Transactions.tsx.
Unauthenticated for dev: accepts optional user_id.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import BrokerAccount
from backend.models.user import User
from backend.models.transaction import Transaction

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/statements")
async def get_statements(
    days: int = Query(30, ge=1, le=3650),
    user_id: Optional[int] = Query(None, description="User ID (optional)"),
    account_id: Optional[str] = Query(
        None, description="Filter by account number (e.g., IBKR_ACCOUNT)"
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return unified transaction statements for last N days for the user."""
    try:
        user = (
            db.query(User).first()
            if user_id is None
            else db.query(User).filter(User.id == user_id).first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        cutoff = datetime.utcnow() - timedelta(days=days)
        # Base filter: all user's accounts
        account_ids_q = db.query(BrokerAccount.id).filter(
            BrokerAccount.user_id == user.id
        )
        # Optional filter: specific account number
        if account_id:
            account_row = (
                db.query(BrokerAccount)
                .filter(
                    BrokerAccount.account_number == account_id,
                    BrokerAccount.user_id == user.id,
                )
                .first()
            )
            if not account_row:
                return {
                    "status": "success",
                    "data": {"transactions": [], "summary": {"total_transactions": 0}},
                }
            account_ids_q = db.query(BrokerAccount.id).filter(
                BrokerAccount.id == account_row.id
            )

        q = (
            db.query(Transaction)
            .filter(
                Transaction.account_id.in_(account_ids_q),
                Transaction.transaction_date >= cutoff,
            )
            .order_by(Transaction.transaction_date.desc())
        )
        rows = q.all()

        def to_row(t: Transaction) -> Dict[str, Any]:
            ttype = (t.transaction_type.name if t.transaction_type else "OTHER").upper()
            is_buy = ttype == "BUY"
            is_sell = ttype == "SELL"
            acc = (
                db.query(BrokerAccount).filter(BrokerAccount.id == t.account_id).first()
            )
            return {
                "id": t.id,
                "date": (
                    t.transaction_date.date().isoformat()
                    if t.transaction_date
                    else None
                ),
                "time": (
                    t.transaction_date.time().isoformat(timespec="seconds")
                    if t.transaction_date
                    else None
                ),
                "symbol": t.symbol,
                "description": t.description,
                "type": "BUY" if is_buy else "SELL" if is_sell else ttype,
                "action": t.action,
                "quantity": float(t.quantity or 0),
                "price": float(t.trade_price or 0),
                "amount": float(t.amount or 0),
                "commission": float(t.commission or 0),
                "fees": float(
                    (t.other_fees or 0)
                    + (t.third_party_commission or 0)
                    + (t.clearing_commission or 0)
                ),
                "net_amount": float(t.net_amount or 0),
                "currency": t.currency,
                "exchange": t.listing_exchange,
                "order_id": t.order_id,
                "execution_id": t.execution_id,
                "contract_type": t.asset_category,
                "account": acc.account_number if acc else None,
                "settlement_date": (
                    t.settlement_date.isoformat() if t.settlement_date else None
                ),
                "source": t.source,
            }

        txs = [to_row(t) for t in rows]
        buys = [x for x in txs if x["type"] == "BUY"]
        sells = [x for x in txs if x["type"] == "SELL"]
        summary = {
            "total_transactions": len(txs),
            "total_value": sum(abs(x["amount"]) for x in txs),
            "total_commission": sum(x["commission"] for x in txs),
            "total_fees": sum(x["fees"] for x in txs),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "date_range": days,
            "net_buy_value": sum(abs(x["amount"]) for x in buys),
            "net_sell_value": sum(abs(x["amount"]) for x in sells),
        }

        return {"status": "success", "data": {"transactions": txs, "summary": summary}}
    except Exception as e:
        logger.error(f"❌ Statements error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
