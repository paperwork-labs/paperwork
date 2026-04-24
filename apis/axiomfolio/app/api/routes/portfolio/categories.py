"""Portfolio categories CRUD and position assignment.

All endpoints require authentication via JWT.
Categories are scoped to the authenticated user.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.broker_account import BrokerAccount
from app.models.portfolio import Category, PositionCategory
from app.models.position import Position
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class CategoryCreate(BaseModel):
    name: str
    target_allocation_pct: float | None = None
    description: str | None = None
    color: str | None = None
    category_type: str | None = "custom"


class CategoryUpdate(BaseModel):
    name: str | None = None
    target_allocation_pct: float | None = None
    description: str | None = None
    color: str | None = None


class AssignPositionsRequest(BaseModel):
    position_ids: list[int]


@router.get("/categories/views")
async def list_category_views(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return available category view types for the user."""
    types = db.query(Category.category_type).filter(Category.user_id == user.id).distinct().all()
    existing = [t[0] for t in types if t[0]]
    if "custom" not in existing:
        existing.insert(0, "custom")

    VIEW_LABELS = {
        "custom": "Personalized",
        "sector": "By Sector",
        "market_cap": "By Market Cap",
        "stage": "By Stage",
        "rs_quartile": "By RS Percentile",
    }
    views = [{"key": k, "label": VIEW_LABELS.get(k, k.replace("_", " ").title())} for k in existing]
    return {"status": "success", "data": {"views": views}}


@router.get("/categories", response_model=dict[str, Any])
async def list_categories(
    category_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List categories with position counts and actual allocation %. Optionally filter by category_type."""
    q = db.query(Category).filter(Category.user_id == user.id)
    if category_type:
        q = q.filter(Category.category_type == category_type)
    categories = q.order_by(Category.display_order, Category.name).all()
    total_value = (
        db.query(func.coalesce(func.sum(Position.market_value), 0))
        .filter(Position.user_id == user.id)
        .scalar()
        or 0
    )
    result = []
    for cat in categories:
        assigned_value = (
            db.query(func.coalesce(func.sum(Position.market_value), 0))
            .join(PositionCategory, PositionCategory.position_id == Position.id)
            .filter(PositionCategory.category_id == cat.id)
            .filter(Position.user_id == user.id)
            .scalar()
        ) or 0
        actual_pct = (assigned_value / total_value * 100) if total_value else 0
        result.append(
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "color": cat.color,
                "category_type": cat.category_type or "custom",
                "target_allocation_pct": cat.target_allocation_pct,
                "actual_allocation_pct": round(actual_pct, 2),
                "display_order": cat.display_order or 0,
                "positions_count": db.query(PositionCategory)
                .filter(PositionCategory.category_id == cat.id)
                .count(),
                "total_value": assigned_value,
            }
        )

    # Compute uncategorized positions within this view
    cat_ids = [c.id for c in categories]
    categorized_position_ids = set()
    if cat_ids:
        categorized_position_ids = {
            r[0]
            for r in db.query(PositionCategory.position_id)
            .filter(PositionCategory.category_id.in_(cat_ids))
            .all()
        }

    all_positions = (
        db.query(Position).filter(Position.user_id == user.id, Position.quantity != 0).all()
    )
    uncategorized = [p for p in all_positions if p.id not in categorized_position_ids]
    uncat_value = sum(float(p.market_value or 0) for p in uncategorized)
    total_value_f = float(total_value)
    uncat_pct = (uncat_value / total_value_f * 100) if total_value_f else 0

    return {
        "status": "success",
        "data": {
            "categories": result,
            "uncategorized": {
                "positions_count": len(uncategorized),
                "total_value": uncat_value,
                "actual_allocation_pct": round(uncat_pct, 2),
                "position_ids": [p.id for p in uncategorized],
            },
        },
    }


@router.post("/categories", response_model=dict[str, Any])
async def create_category(
    body: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a category."""
    cat_type = body.category_type or "custom"
    existing = (
        db.query(Category)
        .filter(
            Category.user_id == user.id,
            Category.name == body.name,
            Category.category_type == cat_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Category name already exists")
    cat = Category(
        name=body.name,
        user_id=user.id,
        description=body.description,
        color=body.color,
        target_allocation_pct=body.target_allocation_pct,
        category_type=body.category_type or "custom",
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"status": "success", "data": {"id": cat.id, "name": cat.name}}


class ReorderRequest(BaseModel):
    ordered_ids: list[int]


@router.put("/categories/reorder", response_model=dict[str, Any])
async def reorder_categories(
    body: ReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Persist display order for categories. ordered_ids is the full list in desired order."""
    for idx, cat_id in enumerate(body.ordered_ids):
        db.query(Category).filter(
            Category.id == cat_id,
            Category.user_id == user.id,
        ).update({"display_order": idx})
    db.commit()
    return {"status": "success"}


@router.get("/categories/rebalance-suggestions", response_model=dict[str, Any])
async def get_rebalance_suggestions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compute rebalancing suggestions based on target vs actual allocations."""
    try:
        acct_ids = [
            a.id for a in db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user.id).all()
        ]
        if not acct_ids:
            return {"status": "success", "data": {"suggestions": [], "total_value": 0}}

        categories = db.query(Category).filter(Category.user_id == user.id).all()
        positions = (
            db.query(Position)
            .filter(Position.account_id.in_(acct_ids), Position.quantity != 0)
            .all()
        )
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
            cat_positions = [
                pos_map[lnk.position_id] for lnk in links if lnk.position_id in pos_map
            ]
            cat_mv = sum(float(p.market_value or 0) for p in cat_positions)
            actual_pct = (cat_mv / total_mv * 100) if total_mv > 0 else 0
            drift = actual_pct - target_pct
            threshold = (
                float(cat.rebalance_threshold_pct or 5)
                if hasattr(cat, "rebalance_threshold_pct")
                else 5.0
            )

            if abs(drift) > threshold:
                dollar_adj = round(drift / 100 * total_mv, 2)
                direction = "SELL" if drift > 0 else "BUY"

                pos_details = []
                for p in cat_positions:
                    w = (
                        float(p.market_value or 0) / cat_mv
                        if cat_mv > 0
                        else 1 / max(len(cat_positions), 1)
                    )
                    est = round(abs(dollar_adj) * w, 2)
                    pos_details.append(
                        {
                            "symbol": p.symbol,
                            "est_value": est,
                            "shares": round(est / float(p.current_price or 1), 2)
                            if p.current_price
                            else 0,
                        }
                    )

                suggestions.append(
                    {
                        "category": cat.name,
                        "target_pct": round(target_pct, 1),
                        "actual_pct": round(actual_pct, 1),
                        "drift_pct": round(drift, 1),
                        "direction": direction,
                        "amount": abs(dollar_adj),
                        "positions": pos_details,
                    }
                )

        return {
            "status": "success",
            "data": {"suggestions": suggestions, "total_value": round(total_mv, 2)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"rebalance-suggestions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _market_cap_label(mc_value) -> str:
    """Convert raw market cap to a human-readable label."""
    try:
        mc = float(mc_value)
    except (TypeError, ValueError):
        return "Unknown Cap"
    if mc >= 200_000_000_000:
        return "Mega Cap"
    if mc >= 10_000_000_000:
        return "Large Cap"
    if mc >= 2_000_000_000:
        return "Mid Cap"
    if mc >= 300_000_000:
        return "Small Cap"
    return "Micro Cap"


@router.post("/categories/apply-preset")
async def apply_preset(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Auto-create categories from a preset (sector, market_cap, stage, rs_quartile)."""
    from app.models.market_data import MarketSnapshot

    preset = body.get("preset")
    if preset not in ("sector", "market_cap", "stage", "rs_quartile"):
        raise HTTPException(400, f"Unknown preset: {preset}")

    account_ids = [a.id for a in user.accounts] if hasattr(user, "accounts") else []
    if not account_ids:
        account_ids_query = db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user.id)
        account_ids = [r[0] for r in account_ids_query.all()]

    positions = (
        db.query(Position)
        .filter(Position.account_id.in_(account_ids), Position.quantity != 0)
        .all()
    )

    if not positions:
        return {"status": "ok", "categories_created": 0, "positions_assigned": 0}

    symbols = list({p.symbol for p in positions})
    snapshots = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol.in_(symbols),
            MarketSnapshot.analysis_type == "technical_snapshot",
        )
        .all()
    )
    snap_map = {s.symbol: s for s in snapshots}

    def get_bucket(pos):
        snap = snap_map.get(pos.symbol)
        if not snap:
            return "Uncategorized"
        if preset == "sector":
            return snap.sector or "Unknown Sector"
        elif preset == "market_cap":
            mc = getattr(snap, "market_cap", None)
            if mc is not None:
                return _market_cap_label(mc)
            return "Unknown Cap"
        elif preset == "stage":
            return f"Stage {snap.stage_label}" if snap.stage_label else "Unknown Stage"
        elif preset == "rs_quartile":
            rs = getattr(snap, "rs_mansfield_pct", None)
            if rs is None:
                return "Unknown RS"
            if rs >= 75:
                return "RS Top Quartile"
            elif rs >= 50:
                return "RS 2nd Quartile"
            elif rs >= 25:
                return "RS 3rd Quartile"
            else:
                return "RS Bottom Quartile"
        return "Uncategorized"

    buckets: dict[str, list] = {}
    for pos in positions:
        bucket = get_bucket(pos)
        buckets.setdefault(bucket, []).append(pos)

    old_cats = (
        db.query(Category)
        .filter(Category.user_id == user.id, Category.category_type == preset)
        .all()
    )
    for old_cat in old_cats:
        db.query(PositionCategory).filter(PositionCategory.category_id == old_cat.id).delete(
            synchronize_session=False
        )
        db.delete(old_cat)
    db.flush()

    categories_created = 0
    positions_assigned = 0

    for bucket_name, bucket_positions in buckets.items():
        cat = Category(name=bucket_name, user_id=user.id, category_type=preset)
        db.add(cat)
        db.flush()
        categories_created += 1

        for pos in bucket_positions:
            db.add(PositionCategory(category_id=cat.id, position_id=pos.id))
            positions_assigned += 1

    db.commit()
    return {
        "status": "ok",
        "categories_created": categories_created,
        "positions_assigned": positions_assigned,
    }


@router.get("/categories/{category_id}", response_model=dict[str, Any])
async def get_category(
    category_id: int = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get one category with positions."""
    cat = (
        db.query(Category)
        .filter(
            Category.id == category_id,
            Category.user_id == user.id,
        )
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    position_ids = [
        r[0]
        for r in db.query(PositionCategory.position_id)
        .filter(PositionCategory.category_id == category_id)
        .all()
    ]
    positions = (
        db.query(Position).filter(Position.id.in_(position_ids)).all() if position_ids else []
    )
    cat_total = sum(float(p.market_value or 0) for p in positions)

    from app.models.market_data import MarketSnapshot

    symbols = [p.symbol for p in positions]
    snap_map: dict = {}
    if symbols:
        snaps = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol.in_(symbols),
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .all()
        )
        snap_map = {s.symbol: s for s in snaps}

    pos_list = []
    for p in positions:
        mv = float(p.market_value or 0)
        snap = snap_map.get(p.symbol)
        pos_list.append(
            {
                "id": p.id,
                "symbol": p.symbol,
                "shares": float(p.quantity or 0),
                "market_value": mv,
                "weight_pct": round(mv / cat_total * 100, 2) if cat_total else 0,
                "stage_label": getattr(snap, "stage_label", None) if snap else None,
                "unrealized_pnl": float(p.unrealized_pnl or 0),
                "unrealized_pnl_pct": float(p.unrealized_pnl_pct or 0),
            }
        )

    return {
        "status": "success",
        "data": {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "color": cat.color,
            "category_type": cat.category_type or "custom",
            "target_allocation_pct": cat.target_allocation_pct,
            "position_ids": position_ids,
            "positions": pos_list,
        },
    }


@router.put("/categories/{category_id}", response_model=dict[str, Any])
async def update_category(
    category_id: int = Path(...),
    body: CategoryUpdate | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a category."""
    cat = (
        db.query(Category)
        .filter(
            Category.id == category_id,
            Category.user_id == user.id,
        )
        .first()
    )
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


@router.delete("/categories/{category_id}", response_model=dict[str, Any])
async def delete_category(
    category_id: int = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a category and its position assignments."""
    cat = (
        db.query(Category)
        .filter(
            Category.id == category_id,
            Category.user_id == user.id,
        )
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.query(PositionCategory).filter(PositionCategory.category_id == category_id).delete()
    db.delete(cat)
    db.commit()
    return {"status": "success"}


@router.post("/categories/{category_id}/positions", response_model=dict[str, Any])
async def assign_positions(
    category_id: int = Path(...),
    body: AssignPositionsRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Assign positions to a category (adds to existing)."""
    cat = (
        db.query(Category)
        .filter(
            Category.id == category_id,
            Category.user_id == user.id,
        )
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    position_ids = body.position_ids if body else []
    added = 0
    for pid in position_ids:
        position = (
            db.query(Position)
            .filter(
                Position.id == pid,
                Position.user_id == user.id,
            )
            .first()
        )
        if not position:
            continue
        existing = (
            db.query(PositionCategory)
            .filter(
                PositionCategory.category_id == category_id,
                PositionCategory.position_id == pid,
            )
            .first()
        )
        if not existing:
            db.add(PositionCategory(category_id=category_id, position_id=pid))
            added += 1
    db.commit()
    return {"status": "success", "data": {"added": added}}


@router.delete("/categories/{category_id}/positions/{position_id}", response_model=dict[str, Any])
async def unassign_position(
    category_id: int = Path(...),
    position_id: int = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove a position from a category."""
    cat = (
        db.query(Category)
        .filter(
            Category.id == category_id,
            Category.user_id == user.id,
        )
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    link = (
        db.query(PositionCategory)
        .filter(
            PositionCategory.category_id == category_id,
            PositionCategory.position_id == position_id,
        )
        .first()
    )
    if link:
        db.delete(link)
        db.commit()
    return {"status": "success"}
