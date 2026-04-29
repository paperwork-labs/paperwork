"""Expense reporting router — WS-69 PR N.

Endpoints (all under /api/v1/admin/expenses, protected by X-Brain-Secret):

  GET    /admin/expenses                  — list with filters + pagination
  GET    /admin/expenses/rollup           — monthly or quarterly rollup
  GET    /admin/expenses/export.csv       — CSV download
  GET    /admin/expenses/rules            — read routing rules (PR O adds writer)
  POST   /admin/expenses                  — submit (multipart: json body + optional receipt)
  GET    /admin/expenses/{id}             — detail
  PATCH  /admin/expenses/{id}             — edit fields
  POST   /admin/expenses/{id}/status      — update status

medallion: ops
"""

from __future__ import annotations

import hmac
import json
import logging

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response

import app.services.expense_receipts as receipt_svc
import app.services.expenses as expense_svc
from app.config import settings
from app.schemas.base import error_response, success_response
from app.schemas.expenses import (
    ExpenseCategory,
    ExpenseCreate,
    ExpenseEdit,
    ExpenseSource,
    ExpenseStatus,
    ExpenseStatusUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/expenses", tags=["expenses"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


# ---------------------------------------------------------------------------
# Fixed routes (must come before /{id})
# ---------------------------------------------------------------------------


@router.get("/rollup")
async def get_rollup(
    year: int = Query(...),
    month: int | None = Query(default=None),
    quarter: int | None = Query(default=None),
    _auth: None = Depends(_require_admin),
):
    """Monthly or quarterly rollup. Provide year+month or year+quarter."""
    if month is not None:
        if not 1 <= month <= 12:
            return error_response("month must be 1-12", 422)
        rollup = expense_svc.compute_monthly_rollup(year, month)
        return success_response(rollup.model_dump(mode="json"))
    if quarter is not None:
        if not 1 <= quarter <= 4:
            return error_response("quarter must be 1-4", 422)
        rollup = expense_svc.compute_quarterly_rollup(year, quarter)
        return success_response(rollup.model_dump(mode="json"))
    return error_response("Provide month or quarter", 422)


@router.get("/export.csv")
async def export_csv(
    status: ExpenseStatus | None = Query(default=None),
    category: ExpenseCategory | None = Query(default=None),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    _auth: None = Depends(_require_admin),
):
    csv_str = expense_svc.export_csv(status=status, category=category, year=year, month=month)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@router.get("/rules")
async def get_routing_rules(_auth: None = Depends(_require_admin)):
    """Read current routing rules. PR O adds the writer (PUT /admin/expenses/rules)."""
    rules = expense_svc.load_routing_rules()
    return success_response(rules.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


@router.get("")
async def list_expenses(
    status: ExpenseStatus | None = Query(default=None),
    category: ExpenseCategory | None = Query(default=None),
    source: ExpenseSource | None = Query(default=None),
    search: str | None = Query(default=None),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    count_only: bool = Query(default=False),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _auth: None = Depends(_require_admin),
):
    page = expense_svc.list_expenses(
        status=status,
        category=category,
        source=source,
        search=search,
        year=year,
        month=month,
        count_only=count_only,
        cursor=cursor,
        limit=limit,
    )
    return success_response(page.model_dump(mode="json"))


@router.post("", status_code=201)
async def submit_expense(
    body: str = Form(..., description="JSON-encoded ExpenseCreate"),
    receipt: UploadFile | None = File(default=None),
    _auth: None = Depends(_require_admin),
):
    """Submit a new expense (multipart). body is JSON-encoded ExpenseCreate."""
    try:
        payload_dict = json.loads(body)
        payload = ExpenseCreate.model_validate(payload_dict)
    except Exception as exc:
        return error_response(f"Invalid expense payload: {exc}", 422)

    expense = expense_svc.submit_expense(payload)

    # Attach receipt if provided
    if receipt is not None:
        content = await receipt.read()
        mime = receipt.content_type or "application/octet-stream"
        try:
            receipt_svc.validate_receipt(receipt.filename or "upload", mime, len(content))
            stored_path = receipt_svc.store_receipt(
                expense.id, receipt.filename or "receipt", content, mime
            )
            from app.schemas.expenses import ReceiptAttachment

            receipt_data = ReceiptAttachment(
                filename=receipt.filename or "receipt",
                mime_type=mime,
                size_bytes=len(content),
                stored_path=stored_path,
            )
            expense = expense_svc.attach_receipt(expense.id, receipt_data.model_dump(mode="json"))
        except ValueError as exc:
            logger.warning("Receipt upload rejected for expense %s: %s", expense.id, exc)
            return error_response(f"Receipt rejected: {exc}", 422)

    return success_response(expense.model_dump(mode="json"), status_code=201)


# ---------------------------------------------------------------------------
# Item routes
# ---------------------------------------------------------------------------


@router.get("/{expense_id}")
async def get_expense(expense_id: str, _auth: None = Depends(_require_admin)):
    expense = expense_svc.get_expense(expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return success_response(expense.model_dump(mode="json"))


@router.patch("/{expense_id}")
async def edit_expense(
    expense_id: str,
    edit: ExpenseEdit,
    _auth: None = Depends(_require_admin),
):
    updated = expense_svc.edit_expense(expense_id, edit)
    if updated is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return success_response(updated.model_dump(mode="json"))


@router.post("/{expense_id}/status")
async def update_expense_status(
    expense_id: str,
    body: ExpenseStatusUpdate,
    _auth: None = Depends(_require_admin),
):
    try:
        updated = expense_svc.update_expense_status(expense_id, body)
    except ValueError as exc:
        return error_response(str(exc), 422)
    if updated is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return success_response(updated.model_dump(mode="json"))
