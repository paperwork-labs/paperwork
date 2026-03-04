"""Portfolio order execution routes."""

from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.services.order_service import order_service

router = APIRouter(prefix="/portfolio/orders", tags=["orders"])


class OrderPreviewRequest(BaseModel):
    symbol: str
    side: str = Field(description="buy or sell")
    order_type: str = Field(default="market", description="market, limit, stop, stop_limit")
    quantity: float
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None


class OrderSubmitRequest(BaseModel):
    order_id: int


@router.post("/preview")
async def preview_order(
    req: OrderPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await order_service.preview_order(
        db,
        symbol=req.symbol,
        side=req.side,
        order_type=req.order_type,
        quantity=req.quantity,
        limit_price=req.limit_price,
        stop_price=req.stop_price,
        created_by=user.email,
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"data": result}


@router.post("/submit")
async def submit_order(
    req: OrderSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await order_service.submit_order(db, order_id=req.order_id, created_by=user.email)
    err = result.get("error")
    if err:
        raise HTTPException(
            status_code=403 if err == "Forbidden" else 400, detail=err
        )
    return {"data": result}


@router.get("")
def list_orders(
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    orders = order_service.list_orders(
        db, status=status, symbol=symbol, limit=limit, created_by=user.email
    )
    return {"data": orders}


@router.get("/{order_id}/status")
async def poll_order_status(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await order_service.poll_order_status(
        db, order_id=order_id, created_by=user.email
    )
    err = result.get("error")
    if err:
        raise HTTPException(
            status_code=403 if err == "Forbidden" else 400, detail=err
        )
    return {"data": result}


@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = order_service.get_order(db, order_id, created_by=user.email)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"data": order}


@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await order_service.cancel_order(
        db, order_id=order_id, created_by=user.email
    )
    err = result.get("error")
    if err:
        raise HTTPException(
            status_code=403 if err == "Forbidden" else 400, detail=err
        )
    return {"data": result}
