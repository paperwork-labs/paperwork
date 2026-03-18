from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_csrf
from app.models.user import User
from app.rate_limit import get_user_rate_limit_key, limiter
from app.schemas.base import success_response
from app.schemas.filing import (
    ConfirmDataRequest,
    CreateFilingRequest,
    UpdateFilingRequest,
)
from app.services import filing_service
from app.utils.exceptions import ValidationError

router = APIRouter(prefix="/filings", tags=["filings"])


def _parse_uuid(filing_id: str) -> UUID:
    try:
        return UUID(filing_id)
    except ValueError as err:
        raise ValidationError("Invalid filing ID format") from err


@router.post("")
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def create_filing(
    request: Request,
    data: CreateFilingRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    filing, created = await filing_service.create_filing(db, user.id, data.tax_year)
    status = 201 if created else 200
    return success_response(filing_service.filing_to_response(filing), status)


@router.get("")
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def list_filings(
    request: Request,
    tax_year: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filings = await filing_service.get_user_filings(db, user.id, tax_year)
    return success_response([filing_service.filing_to_response(f) for f in filings])


@router.get("/{filing_id}")
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def get_filing(
    request: Request,
    filing_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filing = await filing_service.get_filing(db, _parse_uuid(filing_id), user.id)
    return success_response(filing_service.filing_to_response(filing))


@router.patch("/{filing_id}")
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def update_filing(
    request: Request,
    filing_id: str,
    data: UpdateFilingRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    fid = _parse_uuid(filing_id)

    if data.filing_status_type:
        filing = await filing_service.update_filing_status_type(
            db, fid, user.id, data.filing_status_type
        )
    elif data.status:
        filing = await filing_service.advance_status(db, fid, user.id, data.status)
    else:
        filing = await filing_service.get_filing(db, fid, user.id)

    return success_response(filing_service.filing_to_response(filing))


@router.post("/{filing_id}/confirm")
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def confirm_data(
    request: Request,
    filing_id: str,
    data: ConfirmDataRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    filing = await filing_service.advance_status(
        db, _parse_uuid(filing_id), user.id, "data_confirmed"
    )
    return success_response(filing_service.filing_to_response(filing))
