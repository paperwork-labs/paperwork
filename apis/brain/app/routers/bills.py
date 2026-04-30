"""Bills (invoices) router — WS-76 PR-26.

Endpoints under /api/v1/admin/bills (X-Brain-Secret + Brain user context).

medallion: ops
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.config import settings
from app.dependencies.auth import get_brain_user_context
from app.schemas.base import error_response, success_response
from app.schemas.bill import (  # noqa: TC001
    BillCreate,
    BillStatus,
    BillUpdate,
)
from app.schemas.brain_user_context import BrainUserContext  # noqa: TC001
from app.services import bills as bill_svc

router = APIRouter(prefix="/admin/bills", tags=["bills"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


@router.get("")
async def list_bills(
    status: BillStatus | None = Query(default=None),
    _ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    page = bill_svc.list_bills(status=status)
    return success_response(page.model_dump(mode="json"))


@router.post("", status_code=201)
async def create_bill(
    body: BillCreate,
    _ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    bill = bill_svc.create_bill(body)
    return success_response(bill.model_dump(mode="json"), status_code=201)


@router.post("/{bill_id}/approve")
async def approve_bill(
    bill_id: str,
    _ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    try:
        updated = bill_svc.approve_bill(bill_id)
    except ValueError as exc:
        return error_response(str(exc), 422)
    if updated is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return success_response(updated.model_dump(mode="json"))


@router.post("/{bill_id}/pay")
async def pay_bill(
    bill_id: str,
    _ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    try:
        updated = bill_svc.pay_bill(bill_id)
    except ValueError as exc:
        return error_response(str(exc), 422)
    if updated is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return success_response(updated.model_dump(mode="json"))


@router.post("/{bill_id}/reject")
async def reject_bill(
    bill_id: str,
    _ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    try:
        updated = bill_svc.reject_bill(bill_id)
    except ValueError as exc:
        return error_response(str(exc), 422)
    if updated is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return success_response(updated.model_dump(mode="json"))


@router.get("/{bill_id}")
async def get_bill(
    bill_id: str,
    _ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    bill = bill_svc.get_bill(bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return success_response(bill.model_dump(mode="json"))


@router.patch("/{bill_id}")
async def patch_bill(
    bill_id: str,
    body: BillUpdate,
    _ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    updated = bill_svc.update_bill(bill_id, body)
    if updated is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return success_response(updated.model_dump(mode="json"))


@router.delete("/{bill_id}", status_code=200)
async def remove_bill(
    bill_id: str,
    _ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    if not bill_svc.delete_bill(bill_id):
        raise HTTPException(status_code=404, detail="Bill not found")
    return success_response({"deleted": True})
