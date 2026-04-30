"""Conversations router — unified Brain-canonical Conversations API (WS-69 PR E).

Endpoints:
  GET  /admin/conversations              — list (filter, search, cursor, limit)
  GET  /admin/conversations/unread-count — badge count for PWA (PR I consumer)
  GET  /admin/conversations/{id}         — single conversation
  POST /admin/conversations              — create
  POST /admin/conversations/{id}/messages — append message
  POST /admin/conversations/{id}/status  — update status
  POST /admin/conversations/{id}/snooze  — snooze
  POST /admin/conversations/{id}/messages/{msg_id}/react — add/remove reaction
  POST /admin/conversations/_search      — full-text search

All endpoints require the ``X-Brain-Secret`` admin header via ``_require_admin``.
"""

from __future__ import annotations

import hmac
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, HTTPException, Query

import app.services.conversations as conv_svc
import app.services.expenses as expense_svc
from app.schemas.base import error_response, success_response
from app.schemas.conversation import (  # noqa: TC001
    AppendMessageRequest,
    ConversationCreate,
    ReactRequest,
    SnoozeRequest,
    StatusUpdateRequest,
)
from app.schemas.expenses import ExpenseConversationResolveBody  # noqa: TC001

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    from app.config import settings

    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


# ---------------------------------------------------------------------------
# List / count
# ---------------------------------------------------------------------------


@router.get("/conversations")
def list_conversations(
    status_filter: str | None = Query(
        None,
        alias="filter",
        description="Status filter: needs-action, open, snoozed, resolved, archived, all",
    ),
    search: str | None = Query(None, description="Full-text search query"),
    cursor: str | None = Query(
        None,
        description="Cursor for pagination (last conversation id seen)",
    ),
    limit: int = Query(50, ge=1, le=200),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """List conversations with optional status filter, full-text search, and cursor pagination."""
    page = conv_svc.list_conversations(
        status_filter=status_filter,
        search=search,
        cursor=cursor,
        limit=limit,
    )
    return success_response(page.model_dump(mode="json"))


@router.get("/conversations/unread-count")
def get_unread_count(
    status_filter: str = Query(
        "needs-action",
        alias="filter",
        description="Status filter for the count",
    ),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Return conversation count matching *filter* (for PWA badge, PR I consumer)."""
    count = conv_svc.unread_count(status_filter=status_filter)
    return success_response({"count": count})


# ---------------------------------------------------------------------------
# Single conversation
# ---------------------------------------------------------------------------


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    try:
        conv = conv_svc.get_conversation(conversation_id)
    except KeyError:
        return error_response(f"Conversation {conversation_id!r} not found", status_code=404)
    return success_response(conv.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post("/conversations")
def create_conversation(
    body: ConversationCreate,
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Create a new Conversation (used by personas + Studio)."""
    conv = conv_svc.create_conversation(body)
    return success_response(conv.model_dump(mode="json"), status_code=201)


@router.post("/conversations/{conversation_id}/resolve")
def resolve_expense_conversation(
    conversation_id: str,
    body: ExpenseConversationResolveBody,
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Atomically resolve an expense-approval thread and update the linked Expense."""
    try:
        exp, conv = expense_svc.resolve_expense_linked_conversation(
            conversation_id,
            body.expense_action,
            body.new_category,
        )
    except ValueError as exc:
        return error_response(str(exc), status_code=422)
    return success_response(
        {
            "expense": exp.model_dump(mode="json"),
            "conversation": conv.model_dump(mode="json"),
        }
    )


# ---------------------------------------------------------------------------
# Append message
# ---------------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/messages")
def append_message(
    conversation_id: str,
    body: AppendMessageRequest,
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    try:
        msg = conv_svc.append_message(conversation_id, body)
    except KeyError:
        return error_response(f"Conversation {conversation_id!r} not found", status_code=404)
    return success_response(msg.model_dump(mode="json"), status_code=201)


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/status")
def update_status(
    conversation_id: str,
    body: StatusUpdateRequest,
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    try:
        conv = conv_svc.update_conversation_status(conversation_id, body.status)
    except KeyError:
        return error_response(f"Conversation {conversation_id!r} not found", status_code=404)
    return success_response(conv.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Snooze
# ---------------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/snooze")
def snooze_conversation(
    conversation_id: str,
    body: SnoozeRequest,
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    try:
        conv = conv_svc.snooze(conversation_id, body.until)
    except KeyError:
        return error_response(f"Conversation {conversation_id!r} not found", status_code=404)
    return success_response(conv.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# React
# ---------------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/messages/{message_id}/react")
def react(
    conversation_id: str,
    message_id: str,
    body: ReactRequest,
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    try:
        msg = conv_svc.react(conversation_id, message_id, body.emoji, body.participant_id)
    except KeyError as exc:
        return error_response(str(exc), status_code=404)
    return success_response(msg.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Full-text search
# ---------------------------------------------------------------------------


@router.post("/conversations/_search")
def search_conversations(
    q: str = Query(..., min_length=1, description="Full-text search query"),
    limit: int = Query(20, ge=1, le=100),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    results = conv_svc.search_conversations(q, limit=limit)
    return success_response([c.model_dump(mode="json") for c in results])


# ---------------------------------------------------------------------------
# Backfill (one-shot admin trigger)
# ---------------------------------------------------------------------------


@router.post("/conversations/_backfill-founder-actions")
def backfill_founder_actions(
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """One-shot migration: import legacy founder_actions.yaml into Conversations."""
    created = conv_svc.backfill_from_founder_actions_yaml()
    return success_response({"created": created})
