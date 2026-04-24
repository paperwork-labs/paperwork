"""MCP (Model Context Protocol) API routes.

Two surfaces:

1. **Token CRUD** (``/tokens``) — JWT-authed (Settings UI). Lets a user
   list, create, and revoke their own MCP tokens. The plaintext token
   is returned exactly once on creation; subsequent reads only expose
   the metadata.
2. **JSON-RPC transport** (``/jsonrpc``) — bearer-authed with the
   issued MCP token. Dispatches ``tools/list`` and ``tools/call`` to
   :class:`backend.mcp.server.MCPServer`.

Multi-tenancy is enforced at every layer:

* Token CRUD always scopes ``user_id == current_user.id``.
* Token revoke is allowed only against rows owned by the caller.
* The transport pins ``user_id = auth.user.id`` for every tool call;
  any caller-supplied ``user_id`` argument is rejected with
  JSON-RPC ``-32602 Invalid params`` (see :class:`MCPServer`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.mcp import build_default_server
from app.mcp.auth import MCPAuthContext, generate_token, get_mcp_context
from app.models.mcp_token import MCPToken
from app.models.user import User

logger = logging.getLogger(__name__)


router = APIRouter()
_mcp_server = build_default_server()


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


class MCPTokenCreate(BaseModel):
    """Payload for ``POST /api/v1/mcp/tokens``."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Human-readable label shown in the Settings UI.",
    )
    expires_in_days: int | None = Field(
        None,
        ge=1,
        le=3650,
        description=(
            "Optional lifetime override (1..3650 days). Omit to use the default 365-day lifetime."
        ),
    )
    pii_tax_lot_consent: bool = Field(
        default=False,
        description=(
            "Explicit consent to expose tax-lot data over MCP "
            "(realized gains/losses and wash-sale history)."
        ),
    )

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class MCPTokenSummary(BaseModel):
    """Token row exposed to the user (no plaintext)."""

    id: int
    name: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    is_active: bool
    pii_consent_at: datetime | None


class MCPTokenCreateResponse(MCPTokenSummary):
    """Adds the plaintext token shown exactly once at creation."""

    token: str = Field(
        ...,
        description=(
            "Plaintext bearer token. Returned once at creation and "
            "never retrievable again. Store it immediately."
        ),
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _serialize_summary(row: MCPToken) -> MCPTokenSummary:
    """Project an ``MCPToken`` row into the public summary schema."""
    return MCPTokenSummary(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
        is_active=row.is_active(),
        pii_consent_at=row.pii_consent_at,
    )


# ----------------------------------------------------------------------
# Token CRUD (JWT-authed)
# ----------------------------------------------------------------------


@router.get("/tokens", response_model=list[MCPTokenSummary])
async def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MCPTokenSummary]:
    """List the caller's MCP tokens (newest first)."""
    rows = (
        db.query(MCPToken)
        .filter(MCPToken.user_id == current_user.id)
        .order_by(MCPToken.created_at.desc())
        .all()
    )
    return [_serialize_summary(r) for r in rows]


@router.post(
    "/tokens",
    response_model=MCPTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_token(
    payload: MCPTokenCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPTokenCreateResponse:
    """Mint a new MCP token; the plaintext value is shown exactly once."""
    plaintext, token_hash = generate_token()

    expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days or 365)

    row = MCPToken(
        user_id=current_user.id,
        name=payload.name,
        token_hash=token_hash,
        expires_at=expires_at,
        pii_consent_at=(datetime.now(UTC) if payload.pii_tax_lot_consent else None),
    )
    db.add(row)
    try:
        db.commit()
    except Exception as e:
        logger.warning("MCP token create failed for user_id=%s: %s", current_user.id, e)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create MCP token",
        )
    db.refresh(row)
    summary = _serialize_summary(row)
    logger.info(
        "MCP token created: id=%s user_id=%s name=%r",
        row.id,
        current_user.id,
        row.name,
    )
    return MCPTokenCreateResponse(**summary.model_dump(), token=plaintext)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Revoke a token owned by the caller. 404 if not found / not theirs."""
    row = (
        db.query(MCPToken)
        .filter(MCPToken.id == token_id, MCPToken.user_id == current_user.id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP token not found",
        )
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        try:
            db.commit()
        except Exception as e:
            logger.warning(
                "MCP token revoke failed for id=%s user_id=%s: %s",
                token_id,
                current_user.id,
                e,
            )
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not revoke MCP token",
            )
        logger.info("MCP token revoked: id=%s user_id=%s", row.id, current_user.id)
    return None


# ----------------------------------------------------------------------
# JSON-RPC transport (bearer-authed)
# ----------------------------------------------------------------------


@router.post("/jsonrpc")
async def mcp_jsonrpc(
    payload: Any = Body(...),
    db: Session = Depends(get_db),
    auth: MCPAuthContext = Depends(get_mcp_context),
) -> dict[str, Any]:
    """Bearer-authed JSON-RPC 2.0 endpoint for ``tools/list`` and ``tools/call``."""
    response = _mcp_server.handle(
        payload,
        db=db,
        user_id=auth.user.id,
        allowed_scopes=auth.allowed_scopes,
        daily_limit=auth.daily_limit,
    )
    return response
