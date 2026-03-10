from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_csrf
from app.models.user import User
from app.schemas.base import success_response
from app.schemas.filing import (
    ConfirmDataRequest,
    CreateFilingRequest,
    UpdateFilingRequest,
)
from app.services import filing_service

router = APIRouter(prefix="/filings", tags=["filings"])


@router.post("")
async def create_filing(
    data: CreateFilingRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    filing = await filing_service.create_filing(db, user.id, data.tax_year)
    return success_response(filing_service.filing_to_response(filing), 201)


@router.get("")
async def list_filings(
    tax_year: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filings = await filing_service.get_user_filings(db, user.id, tax_year)
    return success_response(
        [filing_service.filing_to_response(f) for f in filings]
    )


@router.get("/{filing_id}")
async def get_filing(
    filing_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID

    filing = await filing_service.get_filing(db, UUID(filing_id), user.id)
    return success_response(filing_service.filing_to_response(filing))


@router.patch("/{filing_id}")
async def update_filing(
    filing_id: str,
    data: UpdateFilingRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID

    filing_uuid = UUID(filing_id)

    if data.filing_status_type:
        filing = await filing_service.update_filing_status_type(
            db, filing_uuid, user.id, data.filing_status_type
        )
    elif data.status:
        filing = await filing_service.advance_status(
            db, filing_uuid, user.id, data.status
        )
    else:
        filing = await filing_service.get_filing(db, filing_uuid, user.id)

    return success_response(filing_service.filing_to_response(filing))


@router.post("/{filing_id}/confirm")
async def confirm_data(
    filing_id: str,
    data: ConfirmDataRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID

    filing = await filing_service.advance_status(
        db, UUID(filing_id), user.id, "data_confirmed"
    )
    return success_response(filing_service.filing_to_response(filing))
