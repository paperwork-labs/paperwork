"""Admin CRUD for the products table (WS-82).

medallion: ops
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

from app.config import settings
from app.database import get_db
from app.models.product import Product
from app.schemas.base import error_response, success_response
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

router = APIRouter(prefix="/admin/products", tags=["products"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


def _product_to_response(row: Product) -> dict[str, Any]:
    return ProductResponse(
        id=row.id,
        name=row.name,
        tagline=row.tagline,
        status=row.status,
        domain=row.domain,
        repo_path=row.repo_path,
        vercel_project=row.vercel_project,
        render_services=list(row.render_services or []),
        tech_stack=list(row.tech_stack or []),
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=dict(row.metadata_ or {}),
    ).model_dump(mode="json")


@router.get("")
async def list_products(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    result = await db.execute(select(Product).order_by(Product.name))
    rows = result.scalars().all()
    return success_response({"products": [_product_to_response(r) for r in rows]})


@router.get("/{slug}")
async def get_product(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    row = await db.get(Product, slug)
    if row is None:
        return error_response(f"Product '{slug}' not found", status_code=404)
    return success_response({"product": _product_to_response(row)})


@router.post("")
async def create_product(
    body: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    existing = await db.get(Product, body.id)
    if existing is not None:
        return error_response(f"Product '{body.id}' already exists", status_code=409)

    row = Product(
        id=body.id,
        name=body.name,
        tagline=body.tagline,
        status=body.status,
        domain=body.domain,
        repo_path=body.repo_path,
        vercel_project=body.vercel_project,
        render_services=body.render_services,
        tech_stack=body.tech_stack,
        metadata_=body.metadata,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return success_response({"product": _product_to_response(row)}, status_code=201)


@router.put("/{slug}")
async def update_product(
    slug: str,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    row = await db.get(Product, slug)
    if row is None:
        return error_response(f"Product '{slug}' not found", status_code=404)

    update_data = body.model_dump(exclude_unset=True)
    if "metadata" in update_data:
        update_data["metadata_"] = update_data.pop("metadata")

    for field, value in update_data.items():
        setattr(row, field, value)

    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return success_response({"product": _product_to_response(row)})
