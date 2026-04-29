"""Expense tracking router — /admin/expenses (WS-69 PR N).

medallion: ops
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

import app.services.expenses as expenses_svc
from app.schemas.expenses import ExpenseCreate, ExpenseRoutingRules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/expenses", tags=["admin-expenses"])
rules_router = APIRouter(prefix="/admin/expense-routing-rules", tags=["admin-expenses"])


# ---------------------------------------------------------------------------
# Expense listing & detail
# ---------------------------------------------------------------------------


@router.get("")
def list_expenses(
    filter: str = Query("pending", description="pending|approved|rejected|reimbursed|flagged|all"),  # noqa: A002
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    return expenses_svc.list_expenses(
        filter_status=filter,
        cursor=cursor,
        limit=limit,
    )


@router.get("/pending-count")
def pending_count() -> dict:
    """Sidebar badge endpoint — returns count of pending+flagged expenses."""
    return {"count": expenses_svc.pending_count()}


@router.get("/rollup")
def expense_rollup(
    period: str = Query("month", description="month|quarter"),
    year: int = Query(...),
    month: int | None = Query(None, description="1-12; required for month; used for quarter start"),
) -> dict:
    if period not in ("month", "quarter"):
        raise HTTPException(status_code=400, detail="period must be 'month' or 'quarter'")
    if month is None and period in ("month", "quarter"):
        raise HTTPException(status_code=400, detail="month is required")
    rollup = expenses_svc.compute_rollup(period=period, year=year, month=month)
    return rollup.model_dump(mode="json")


@router.get("/export")
def export_expenses(
    format: str = Query("csv"),  # noqa: A002
    period: str = Query("month", description="month|quarter"),
    year: int = Query(...),
    month: int | None = Query(None),
) -> Response:
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only format=csv is supported")
    if month is None:
        raise HTTPException(status_code=400, detail="month is required")
    csv_data = expenses_svc.export_csv(period=period, year=year, month=month)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="expenses-{year}-{month:02d}.csv"'},
    )


@router.get("/attachments/{sha256}")
def get_attachment(sha256: str) -> Response:
    path = expenses_svc.get_attachment_path(sha256)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Attachment not found")
    with open(path, "rb") as f:
        content = f.read()
    ext = path.rsplit(".", 1)[-1] if "." in path else "bin"
    mime = f"application/{ext}" if ext != "pdf" else "application/pdf"
    return Response(content=content, media_type=mime)


@router.get("/{expense_id}")
def get_expense(expense_id: str) -> dict:
    expense = expenses_svc.get_expense(expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Expense creation (multipart: receipt + metadata)
# ---------------------------------------------------------------------------


@router.post("")
async def create_expense(
    vendor: str = Query(...),
    amount_cents: int = Query(...),
    currency: str = Query("USD"),
    category: str = Query(...),
    submitted_by: str = Query(...),
    notes: str = Query(""),
    tags: str = Query("", description="Comma-separated tags"),
    tax_deductible_pct: float | None = Query(None),
    tax_category_note: str | None = Query(None),
    receipt: UploadFile | None = None,
) -> dict:
    from app.schemas.expenses import ExpenseCategory

    valid_cats = list(ExpenseCategory.__args__)  # type: ignore[attr-defined]
    if category not in valid_cats:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category '{category}'. Must be one of: {valid_cats}",
        )

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    data = ExpenseCreate(
        amount_cents=amount_cents,
        currency=currency,
        vendor=vendor,
        category=category,  # type: ignore[arg-type]
        tags=tag_list,
        notes=notes,
        submitted_by=submitted_by,
        tax_deductible_pct=tax_deductible_pct,
        tax_category_note=tax_category_note,
    )

    attachments = []
    if receipt is not None:
        content = await receipt.read()
        if content:
            mime = receipt.content_type or "application/octet-stream"
            attachment = expenses_svc.store_attachment(content, mime)
            attachments.append(attachment)

    expense = expenses_svc.create_expense(data, attachments=attachments)
    return expense.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


class ActionRequest(BaseModel):
    actor: str = "system"
    reason: str = ""


@router.post("/{expense_id}/approve")
def approve_expense(expense_id: str, body: ActionRequest = ActionRequest()) -> dict:
    expense = expenses_svc.approve_expense(expense_id, approved_by=body.actor)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense.model_dump(mode="json")


@router.post("/{expense_id}/reject")
def reject_expense(expense_id: str, body: ActionRequest = ActionRequest()) -> dict:
    expense = expenses_svc.reject_expense(expense_id, rejected_by=body.actor, reason=body.reason)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense.model_dump(mode="json")


@router.post("/{expense_id}/reimburse")
def mark_reimbursed(expense_id: str, body: ActionRequest = ActionRequest()) -> dict:
    expense = expenses_svc.mark_reimbursed(expense_id, reimbursed_by=body.actor)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------


@rules_router.get("")
def get_routing_rules() -> dict:
    return expenses_svc.load_routing_rules().model_dump(mode="json")


class UpdateRulesRequest(BaseModel):
    rules: ExpenseRoutingRules
    changed_by: str = "system"
    note: str = ""


@rules_router.put("")
def update_routing_rules(body: UpdateRulesRequest) -> dict:
    updated = expenses_svc.update_routing_rules(
        body.rules,
        changed_by=body.changed_by,
        note=body.note,
    )
    return updated.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Backfill trigger (admin only, idempotent)
# ---------------------------------------------------------------------------


backfill_router = APIRouter(prefix="/admin/expenses-backfill", tags=["admin-expenses"])


@backfill_router.post("")
def run_backfill() -> dict:
    n = expenses_svc.backfill_from_financials()
    return {"created": n, "message": f"Backfill complete: {n} rows created"}
