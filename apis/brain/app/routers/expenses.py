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

import asyncio
import hmac
import json
import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import Response
from pydantic import ValidationError

import app.services.expense_receipts as receipt_svc
import app.services.expenses as expense_svc
from app.config import settings
from app.dependencies.auth import get_brain_user_context
from app.schemas.base import error_response, success_response
from app.schemas.brain_user_context import BrainUserContext  # noqa: TC001
from app.schemas.expenses import (
    ExpenseCategory,
    ExpenseConversationResolveBody,
    ExpenseCreate,
    ExpenseEdit,
    ExpenseRoutingRulesUpdate,
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
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Monthly or quarterly rollup. Provide year+month or year+quarter."""
    if month is not None:
        if not 1 <= month <= 12:
            return error_response("month must be 1-12", 422)
        monthly = expense_svc.compute_monthly_rollup(
            year, month, organization_id=ctx.organization_id
        )
        return success_response(monthly.model_dump(mode="json"))
    if quarter is not None:
        if not 1 <= quarter <= 4:
            return error_response("quarter must be 1-4", 422)
        quarterly = expense_svc.compute_quarterly_rollup(
            year, quarter, organization_id=ctx.organization_id
        )
        return success_response(quarterly.model_dump(mode="json"))
    return error_response("Provide month or quarter", 422)


@router.get("/export.csv")
async def export_csv(
    status: ExpenseStatus | None = Query(default=None),
    category: ExpenseCategory | None = Query(default=None),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Response:
    csv_str = expense_svc.export_csv(
        status=status,
        category=category,
        year=year,
        month=month,
        organization_id=ctx.organization_id,
    )
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@router.get("/rules")
async def get_routing_rules(_auth: None = Depends(_require_admin)) -> Any:
    """Read current routing rules. PR O adds the writer (PUT /admin/expenses/rules)."""
    rules = expense_svc.load_routing_rules()
    return success_response(rules.model_dump(mode="json"))


@router.put("/rules")
async def put_routing_rules(
    body: ExpenseRoutingRulesUpdate,
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Replace routing rules with validation + optional audit Conversation on threshold raise."""
    from app.schemas.conversation import ConversationCreate
    from app.services import conversations as conv_svc
    from app.services import expense_rules as erules

    current = expense_svc.load_routing_rules()
    old_threshold = current.auto_approve_threshold_cents
    try:
        merged = erules.merge_update(current, body)
        saved = erules.save_rules(merged, updated_by=body.updated_by)
    except ValueError as exc:
        return error_response(str(exc), 422)

    if body.auto_approve_threshold_cents > old_threshold:

        def _audit() -> None:
            diff_md = (
                f"**Expense routing threshold raised**\n\n"
                f"- **From:** ${old_threshold / 100:,.2f}\n"
                f"- **To:** ${body.auto_approve_threshold_cents / 100:,.2f}\n"
                f"- **By:** {body.updated_by}\n"
            )
            create = ConversationCreate(
                title="Expense rules: auto-approve threshold raised",
                body_md=diff_md,
                tags=["expense-rule-change"],
                urgency="info",
                persona="cfo",
                needs_founder_action=False,
            )
            conv_svc.create_conversation(
                create,
                organization_id=ctx.organization_id,
                push_user_id=ctx.brain_user_id,
            )

        derived = expense_svc.derived_repo_root_from_expense_store()
        if derived is not None:
            import os

            old_root = os.environ.get("REPO_ROOT")
            os.environ["REPO_ROOT"] = derived
            try:
                _audit()
            finally:
                if old_root is None:
                    os.environ.pop("REPO_ROOT", None)
                else:
                    os.environ["REPO_ROOT"] = old_root

    return success_response(saved.model_dump(mode="json"))


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
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
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
        organization_id=ctx.organization_id,
    )
    return success_response(page.model_dump(mode="json"))


@router.post("", status_code=201)
async def submit_expense(
    body: str = Form(..., description="JSON-encoded ExpenseCreate"),
    receipt: UploadFile | None = File(default=None),
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Submit a new expense (multipart). body is JSON-encoded ExpenseCreate."""
    try:
        payload_dict = json.loads(body)
        payload = ExpenseCreate.model_validate(payload_dict)
    except Exception as exc:
        return error_response(f"Invalid expense payload: {exc}", 422)

    expense = await asyncio.to_thread(
        lambda: expense_svc.submit_expense(
            payload,
            organization_id=ctx.organization_id,
            push_user_id=ctx.brain_user_id,
        )
    )

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
            updated = expense_svc.attach_receipt(
                expense.id,
                receipt_data.model_dump(mode="json"),
                organization_id=ctx.organization_id,
            )
            if updated is not None:
                expense = updated
        except ValueError as exc:
            logger.warning("Receipt upload rejected for expense %s: %s", expense.id, exc)
            return error_response(f"Receipt rejected: {exc}", 422)

    return success_response(expense.model_dump(mode="json"), status_code=201)


# ---------------------------------------------------------------------------
# Item routes
# ---------------------------------------------------------------------------


@router.get("/{expense_id}")
async def get_expense(
    expense_id: str,
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    expense = expense_svc.get_expense(expense_id, organization_id=ctx.organization_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return success_response(expense.model_dump(mode="json"))


@router.patch("/{expense_id}")
async def edit_expense(
    expense_id: str,
    edit: ExpenseEdit,
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    updated = expense_svc.edit_expense(expense_id, edit, organization_id=ctx.organization_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return success_response(updated.model_dump(mode="json"))


@router.post("/{expense_id}/status")
async def update_expense_status(
    expense_id: str,
    request: Request,
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_require_admin),
) -> Any:
    try:
        raw = await request.json()
    except Exception:
        return error_response("Invalid JSON body", 422)

    if isinstance(raw, dict) and "expense_action" in raw:
        try:
            resolve_body = ExpenseConversationResolveBody.model_validate(raw)
        except ValidationError as exc:
            return error_response(str(exc), 422)
        exp = expense_svc.get_expense(expense_id, organization_id=ctx.organization_id)
        if exp is None:
            raise HTTPException(status_code=404, detail="Expense not found")
        if not exp.conversation_id:
            return error_response("Expense has no linked approval conversation", 422)
        try:
            updated_exp, conv = expense_svc.resolve_expense_linked_conversation(
                exp.conversation_id,
                resolve_body.expense_action,
                resolve_body.new_category,
                organization_id=ctx.organization_id,
            )
        except ValueError as exc:
            return error_response(str(exc), 422)
        return success_response(
            {
                "expense": updated_exp.model_dump(mode="json"),
                "conversation": conv.model_dump(mode="json"),
            }
        )

    try:
        body = ExpenseStatusUpdate.model_validate(raw)
    except Exception as exc:
        return error_response(f"Invalid status payload: {exc}", 422)
    try:
        updated = expense_svc.update_expense_status(
            expense_id, body, organization_id=ctx.organization_id
        )
    except ValueError as exc:
        return error_response(str(exc), 422)
    if updated is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return success_response(updated.model_dump(mode="json"))
