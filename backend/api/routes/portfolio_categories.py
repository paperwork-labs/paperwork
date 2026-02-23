"""Portfolio categories CRUD and position assignment."""

from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.portfolio import Category, PositionCategory
from backend.models.position import Position
from backend.models.broker_account import BrokerAccount
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_user(db: Session, user_id: Optional[int] = None) -> User:
    if user_id is None:
        user = db.query(User).first()
    else:
        user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


class CategoryCreate(BaseModel):
    name: str
    target_allocation_pct: Optional[float] = None
    description: Optional[str] = None
    color: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    target_allocation_pct: Optional[float] = None
    description: Optional[str] = None
    color: Optional[str] = None


class AssignPositionsRequest(BaseModel):
    position_ids: List[int]


@router.get("/categories", response_model=Dict[str, Any])
async def list_categories(
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """List all categories with position counts and actual allocation %."""
    user = _get_user(db, user_id)
    categories = db.query(Category).order_by(Category.name).all()
    total_value = db.query(func.coalesce(func.sum(Position.market_value), 0)).filter(
        Position.user_id == user.id
    ).scalar() or 0
    result = []
    for cat in categories:
        # Sum of position values in this category (via position_categories)
        assigned_value = (
            db.query(func.coalesce(func.sum(Position.market_value), 0))
            .join(PositionCategory, PositionCategory.position_id == Position.id)
            .filter(PositionCategory.category_id == cat.id)
            .filter(Position.user_id == user.id)
            .scalar()
        ) or 0
        actual_pct = (assigned_value / total_value * 100) if total_value else 0
        result.append({
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "color": cat.color,
            "target_allocation_pct": cat.target_allocation_pct,
            "actual_allocation_pct": round(actual_pct, 2),
            "positions_count": db.query(PositionCategory).filter(PositionCategory.category_id == cat.id).count(),
            "total_value": assigned_value,
        })
    return {"status": "success", "data": {"categories": result}}


@router.post("/categories", response_model=Dict[str, Any])
async def create_category(
    body: CategoryCreate,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Create a category."""
    _get_user(db, user_id)
    existing = db.query(Category).filter(Category.name == body.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category name already exists")
    cat = Category(
        name=body.name,
        description=body.description,
        color=body.color,
        target_allocation_pct=body.target_allocation_pct,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"status": "success", "data": {"id": cat.id, "name": cat.name}}


@router.get("/categories/{category_id}", response_model=Dict[str, Any])
async def get_category(
    category_id: int = Path(...),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get one category with positions."""
    _get_user(db, user_id)
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    position_ids = [
        r[0]
        for r in db.query(PositionCategory.position_id).filter(PositionCategory.category_id == category_id).all()
    ]
    positions = db.query(Position).filter(Position.id.in_(position_ids)).all() if position_ids else []
    return {
        "status": "success",
        "data": {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "color": cat.color,
            "target_allocation_pct": cat.target_allocation_pct,
            "position_ids": position_ids,
            "positions": [
                {"id": p.id, "symbol": p.symbol, "market_value": float(p.market_value or 0)}
                for p in positions
            ],
        },
    }


@router.put("/categories/{category_id}", response_model=Dict[str, Any])
async def update_category(
    category_id: int = Path(...),
    body: Optional[CategoryUpdate] = None,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Update a category."""
    _get_user(db, user_id)
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if body:
        if body.name is not None:
            cat.name = body.name
        if body.target_allocation_pct is not None:
            cat.target_allocation_pct = body.target_allocation_pct
        if body.description is not None:
            cat.description = body.description
        if body.color is not None:
            cat.color = body.color
    db.commit()
    db.refresh(cat)
    return {"status": "success", "data": {"id": cat.id}}


@router.delete("/categories/{category_id}", response_model=Dict[str, Any])
async def delete_category(
    category_id: int = Path(...),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Delete a category and its position assignments."""
    _get_user(db, user_id)
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.query(PositionCategory).filter(PositionCategory.category_id == category_id).delete()
    db.delete(cat)
    db.commit()
    return {"status": "success"}


@router.post("/categories/{category_id}/positions", response_model=Dict[str, Any])
async def assign_positions(
    category_id: int = Path(...),
    body: Optional[AssignPositionsRequest] = None,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Assign positions to a category (adds to existing)."""
    user = _get_user(db, user_id)
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    position_ids = body.position_ids if body else []
    added = 0
    for pid in position_ids:
        position = db.query(Position).filter(
            Position.id == pid,
            Position.user_id == user.id,
        ).first()
        if not position:
            continue
        existing = db.query(PositionCategory).filter(
            PositionCategory.category_id == category_id,
            PositionCategory.position_id == pid,
        ).first()
        if not existing:
            db.add(PositionCategory(category_id=category_id, position_id=pid))
            added += 1
    db.commit()
    return {"status": "success", "data": {"added": added}}


@router.delete("/categories/{category_id}/positions/{position_id}", response_model=Dict[str, Any])
async def unassign_position(
    category_id: int = Path(...),
    position_id: int = Path(...),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Remove a position from a category."""
    _get_user(db, user_id)
    link = db.query(PositionCategory).filter(
        PositionCategory.category_id == category_id,
        PositionCategory.position_id == position_id,
    ).first()
    if link:
        db.delete(link)
        db.commit()
    return {"status": "success"}


@router.get("/categories/rebalance-suggestions", response_model=Dict[str, Any])
async def get_rebalance_suggestions(
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Compute rebalancing suggestions based on target vs actual allocations."""
    try:
        user = _get_user(db, user_id)
        acct_ids = [a.id for a in db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user.id).all()]
        if not acct_ids:
            return {"status": "success", "data": {"suggestions": [], "total_value": 0}}

        categories = db.query(Category).filter(Category.user_id == user.id).all()
        positions = db.query(Position).filter(Position.broker_account_id.in_(acct_ids), Position.quantity != 0).all()
        total_mv = sum(float(p.market_value or 0) for p in positions)

        if total_mv <= 0 or not categories:
            return {"status": "success", "data": {"suggestions": [], "total_value": total_mv}}

        pos_map = {p.id: p for p in positions}

        suggestions = []
        for cat in categories:
            target_pct = float(cat.target_allocation_pct or 0)
            if target_pct <= 0:
                continue

            links = db.query(PositionCategory).filter(PositionCategory.category_id == cat.id).all()
            cat_positions = [pos_map[lnk.position_id] for lnk in links if lnk.position_id in pos_map]
            cat_mv = sum(float(p.market_value or 0) for p in cat_positions)
            actual_pct = (cat_mv / total_mv * 100) if total_mv > 0 else 0
            drift = actual_pct - target_pct
            threshold = float(cat.rebalance_threshold_pct or 5) if hasattr(cat, "rebalance_threshold_pct") else 5.0

            if abs(drift) > threshold:
                dollar_adj = round(drift / 100 * total_mv, 2)
                direction = "SELL" if drift > 0 else "BUY"

                pos_details = []
                for p in cat_positions:
                    w = float(p.market_value or 0) / cat_mv if cat_mv > 0 else 1 / max(len(cat_positions), 1)
                    est = round(abs(dollar_adj) * w, 2)
                    pos_details.append({"symbol": p.symbol, "est_value": est, "shares": round(est / float(p.current_price or 1), 2) if p.current_price else 0})

                suggestions.append({
                    "category": cat.name,
                    "target_pct": round(target_pct, 1),
                    "actual_pct": round(actual_pct, 1),
                    "drift_pct": round(drift, 1),
                    "direction": direction,
                    "amount": abs(dollar_adj),
                    "positions": pos_details,
                })

        return {"status": "success", "data": {"suggestions": suggestions, "total_value": round(total_mv, 2)}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"rebalance-suggestions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
