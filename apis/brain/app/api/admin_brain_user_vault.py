"""Admin HTTP surface for ``brain_user_vault`` (founder-only ``X-Brain-Secret``)."""

from __future__ import annotations

import hmac
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, HTTPException
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.repositories import brain_user_vault as vault_repo
from app.schemas.base import success_response
from app.schemas.brain_user_vault import AdminBrainVaultSetBody

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/brain-vault", tags=["admin", "brain-vault"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


@router.post("/{user_id}/{key}")
async def admin_brain_vault_set(
    user_id: str,
    key: str,
    body: AdminBrainVaultSetBody,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Upsert one encrypted secret for the given user + org."""
    try:
        await vault_repo.set_secret_for_organization(
            user_id,
            key,
            body.value,
            db=db,
            organization_id=body.organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        logger.warning("admin_brain_vault_set crypto config error: %s", type(e).__name__)
        raise HTTPException(status_code=503, detail="vault_encryption_not_configured") from e

    await db.commit()
    logger.info("admin_brain_vault_set committed user=%s… key=%s", user_id[:8], key)
    return success_response({"ok": True})


@router.get("/{user_id}")
async def admin_brain_vault_list(
    user_id: str,
    organization_id: str = "paperwork-labs",
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Keys-only listing for a user."""
    try:
        entries = await vault_repo.list_secrets_for_organization(
            user_id,
            db=db,
            organization_id=organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    payload = [e.model_dump(mode="json") for e in entries]
    return success_response(payload)


@router.delete("/{user_id}/{key}")
async def admin_brain_vault_delete(
    user_id: str,
    key: str,
    organization_id: str = "paperwork-labs",
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Delete one vault row."""
    try:
        deleted = await vault_repo.delete_secret_for_organization(
            user_id,
            key,
            db=db,
            organization_id=organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await db.commit()
    return success_response({"deleted": deleted})
