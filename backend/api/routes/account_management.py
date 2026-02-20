"""
Account Management API Routes
============================

API endpoints for managing broker accounts before syncing.

Flow:
1. User adds broker account credentials via UI
2. Backend stores account in broker_accounts table 
3. Backend can then sync that account's data
4. Subsequent syncs update existing data
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from backend.database import get_db
from backend.models import BrokerAccount, BrokerType, AccountType, AccountStatus, SyncStatus
from backend.models.position import Position
from backend.models.tax_lot import TaxLot
from backend.services.portfolio.broker_sync_service import broker_sync_service
from backend.tasks.celery_app import celery_app
from celery.result import AsyncResult
from fastapi import Query
from typing import Dict, Any
from backend.api.routes.auth import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


# Pydantic models for API
class AddBrokerAccountRequest(BaseModel):
    broker: str  # 'IBKR', 'TASTYTRADE', etc.
    account_number: str
    account_name: Optional[str] = None
    account_type: str  # 'TAXABLE', 'TRADITIONAL_IRA', etc.
    api_credentials: Optional[dict] = None  # Store encrypted credentials
    is_paper_trading: bool = False


class BrokerAccountResponse(BaseModel):
    id: int
    broker: str
    account_number: str
    account_name: Optional[str]
    account_type: str
    status: str
    is_enabled: bool
    last_successful_sync: Optional[datetime]
    sync_status: Optional[str]
    created_at: datetime
    sync_task_id: Optional[str] = None  # Set when auto-sync is queued after add


class SyncAccountRequest(BaseModel):
    sync_type: str = (
        "comprehensive"  # 'comprehensive', 'positions_only', 'transactions_only'
    )


@router.post("/add", response_model=BrokerAccountResponse)
async def add_broker_account(
    request: AddBrokerAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a new broker account for syncing.

    This must be done before syncing - users add their account credentials
    and then we can sync data from that account.
    """
    try:
        # Validate broker type
        try:
            broker_enum = BrokerType[request.broker.upper()]
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported broker: {request.broker}. Supported: IBKR, TASTYTRADE",
            )

        # Validate account type
        try:
            account_type_enum = AccountType[request.account_type.upper()]
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Invalid account type: {request.account_type}"
            )

        # Check if account already exists
        existing = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == current_user.id,
                BrokerAccount.account_number == request.account_number,
                BrokerAccount.broker == broker_enum,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Account {request.account_number} for {request.broker} already exists",
            )

        # Create new broker account
        broker_account = BrokerAccount(
            user_id=current_user.id,
            broker=broker_enum,
            account_number=request.account_number,
            account_name=request.account_name
            or f"{request.broker} {request.account_number}",
            account_type=account_type_enum,
            status=AccountStatus.ACTIVE,
            is_enabled=True,
            api_credentials_stored=request.api_credentials is not None,
            sync_status=SyncStatus.NEVER_SYNCED,
            currency="USD",  # Default, will be updated during sync
            margin_enabled=False,  # Will be updated during sync
            options_enabled=False,  # Will be updated during sync
            futures_enabled=False,  # Will be updated during sync
            created_at=datetime.now(),
        )

        db.add(broker_account)
        db.commit()
        db.refresh(broker_account)

        sync_task_id: Optional[str] = None
        try:
            from backend.tasks.account_sync import sync_account_task

            sync_task = sync_account_task.delay(broker_account.id)
            sync_task_id = sync_task.id
        except Exception:
            pass

        return BrokerAccountResponse(
            id=broker_account.id,
            broker=broker_account.broker.value,
            account_number=broker_account.account_number,
            account_name=broker_account.account_name,
            account_type=broker_account.account_type.value,
            status=broker_account.status.value,
            is_enabled=broker_account.is_enabled,
            last_successful_sync=broker_account.last_successful_sync,
            sync_status=(
                broker_account.sync_status.value if broker_account.sync_status else None
            ),
            created_at=broker_account.created_at,
            sync_task_id=sync_task_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding account: {str(e)}")


@router.get("", response_model=List[BrokerAccountResponse])
async def list_broker_accounts(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List all broker accounts for the user."""
    accounts = db.query(BrokerAccount).filter(BrokerAccount.user_id == current_user.id).all()

    return [
        BrokerAccountResponse(
            id=account.id,
            broker=account.broker.value,
            account_number=account.account_number,
            account_name=account.account_name,
            account_type=account.account_type.value,
            status=account.status.value,
            is_enabled=account.is_enabled,
            last_successful_sync=account.last_successful_sync,
            sync_status=account.sync_status.value if account.sync_status else None,
            created_at=account.created_at,
        )
        for account in accounts
    ]


@router.post("/{account_id}/sync")
async def sync_broker_account(
    account_id: int,
    request: SyncAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sync a specific broker account.

    This populates all database tables with data from the broker.
    Account must be added first via /add endpoint.
    """
    try:
        # Verify account belongs to user
        account = (
            db.query(BrokerAccount)
            .filter(BrokerAccount.id == account_id, BrokerAccount.user_id == current_user.id)
            .first()
        )

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if not account.is_enabled:
            raise HTTPException(status_code=400, detail="Account is disabled")

        # Update sync status
        account.sync_status = SyncStatus.RUNNING
        account.last_sync_attempt = datetime.now()
        db.commit()

        # Enqueue Celery task and return 202 with task id
        task = celery_app.send_task(
            "backend.tasks.account_sync.sync_account_task",
            args=[account_id, request.sync_type],
        )
        account.sync_status = SyncStatus.QUEUED
        account.sync_error_message = None
        db.commit()
        return {"status": "queued", "task_id": task.id}

    except HTTPException:
        raise
    except Exception as e:
        account.sync_status = SyncStatus.FAILED
        account.sync_error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/sync-all")
async def sync_all_accounts(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Sync all enabled broker accounts for the user. Returns task IDs for polling."""
    try:
        from backend.tasks.account_sync import sync_account_task

        accounts = (
            db.query(BrokerAccount)
            .filter(BrokerAccount.user_id == current_user.id, BrokerAccount.is_enabled == True)
            .all()
        )
        task_ids: Dict[str, str] = {}
        for account in accounts:
            key = f"{account.broker.value}_{account.account_number}"
            task = sync_account_task.delay(account.id)
            task_ids[key] = task.id
        return {"status": "queued", "task_ids": task_ids}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing accounts: {str(e)}")


@router.delete("/{account_id}")
async def delete_broker_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a broker account (soft delete - disable it)."""
    try:
        account = (
            db.query(BrokerAccount)
            .filter(BrokerAccount.id == account_id, BrokerAccount.user_id == current_user.id)
            .first()
        )

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Soft delete - just disable the account
        account.is_enabled = False
        account.status = AccountStatus.INACTIVE
        account.updated_at = datetime.now()

        db.commit()
        return {"message": f"Account {account.account_number} disabled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting account: {str(e)}")


@router.get("/{account_id}/sync-status")
async def get_account_sync_status(
    account_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Return current sync status for an account from DB."""
    account = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.id == account_id, BrokerAccount.user_id == current_user.id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return {
        "account_id": account.id,
        "account_number": account.account_number,
        "broker": account.broker.value,
        "sync_status": account.sync_status.value if account.sync_status else None,
        "last_sync_attempt": account.last_sync_attempt,
        "last_successful_sync": account.last_successful_sync,
        "sync_error_message": account.sync_error_message,
    }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Return Celery task status and (if finished) result metadata."""
    res = AsyncResult(task_id, app=celery_app)
    state = res.state
    response = {"task_id": task_id, "state": state}
    if state in ("SUCCESS", "FAILURE", "REVOKED"):
        try:
            response["result"] = (
                res.result if isinstance(res.result, dict) else str(res.result)
            )
        except Exception:
            response["result"] = None
    return response


# Inline price refresh relocated from market_data routes for better cohesion
@router.post("/prices/refresh")
async def refresh_prices(
    account_id: Optional[int] = Query(
        default=None, description="Broker account ID to scope refresh"
    ),
    symbols: Optional[List[str]] = Query(
        default=None, description="Optional subset of symbols to refresh"
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    from backend.services.market.market_data_service import MarketDataService

    try:
        market_service = MarketDataService()

        # Load target positions
        q = db.query(BrokerAccount, Position).join(
            Position, Position.account_id == BrokerAccount.id
        )
        if account_id is not None:
            q = q.filter(BrokerAccount.id == account_id)
        positions = [p for _, p in q.all() if p.quantity != 0 and p.symbol]
        if not positions:
            return {"updated_positions": 0, "updated_tax_lots": 0, "symbols": []}

        unique_symbols = sorted({p.symbol for p in positions if p.symbol})

        # Fetch prices concurrently
        import asyncio as _asyncio

        price_tasks = [market_service.get_current_price(sym) for sym in unique_symbols]
        prices = await _asyncio.gather(*price_tasks, return_exceptions=True)
        symbol_to_price = {}
        for sym, price in zip(unique_symbols, prices):
            try:
                if isinstance(price, (int, float)) and price > 0:
                    symbol_to_price[sym] = float(price)
            except Exception:
                continue

        # Update positions
        updated_positions = 0
        for p in positions:
            price = symbol_to_price.get(p.symbol)
            if price is None:
                continue
            try:
                quantity_abs = float(abs(p.quantity or 0))
                total_cost = float(p.total_cost_basis or 0)
                market_value = quantity_abs * price
                unrealized = market_value - total_cost
                unrealized_pct = (
                    (unrealized / total_cost * 100) if total_cost > 0 else 0.0
                )
                p.current_price = price
                p.market_value = market_value
                p.unrealized_pnl = unrealized
                p.unrealized_pnl_pct = unrealized_pct
                updated_positions += 1
            except Exception:
                continue

        # Update tax lots for same scope
        tq = db.query(TaxLot)
        if account_id is not None:
            tq = tq.filter(TaxLot.account_id == account_id)
        if symbols:
            tq = tq.filter(TaxLot.symbol.in_(symbols))
        lots: List[TaxLot] = tq.all()

        updated_lots = 0
        for lot in lots:
            price = symbol_to_price.get(lot.symbol)
            if price is None:
                continue
            try:
                qty_abs = float(abs(lot.quantity or 0))
                cost_basis = float(lot.cost_basis or 0)
                market_value = qty_abs * price
                unrealized = market_value - cost_basis
                unrealized_pct = (
                    (unrealized / cost_basis * 100) if cost_basis > 0 else 0.0
                )
                lot.current_price = price
                lot.market_value = market_value
                lot.unrealized_pnl = unrealized
                lot.unrealized_pnl_pct = unrealized_pct
                updated_lots += 1
            except Exception:
                continue

        db.flush()
        db.commit()
        return {
            "updated_positions": updated_positions,
            "updated_tax_lots": updated_lots,
            "symbols": list(symbol_to_price.keys()),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Price refresh failed: {e}")
