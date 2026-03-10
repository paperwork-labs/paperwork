import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.filing import Filing, FilingStatus, FilingStatusType
from app.repositories.filing import FilingRepository
from app.utils.exceptions import ConflictError, NotFoundError


async def create_filing(
    db: AsyncSession, user_id: uuid.UUID, tax_year: int
) -> Filing:
    repo = FilingRepository(db)
    existing = await repo.get_active_filing(user_id, tax_year)
    if existing:
        return existing

    return await repo.create(
        user_id=user_id,
        tax_year=tax_year,
        status=FilingStatus.DRAFT,
    )


async def get_filing(
    db: AsyncSession, filing_id: uuid.UUID, user_id: uuid.UUID
) -> Filing:
    repo = FilingRepository(db)
    filing = await repo.get_by_id_with_relations(filing_id)
    if not filing or filing.user_id != user_id:
        raise NotFoundError("Filing not found")
    return filing


async def get_user_filings(
    db: AsyncSession, user_id: uuid.UUID, tax_year: int | None = None
) -> list[Filing]:
    repo = FilingRepository(db)
    return await repo.get_user_filings(user_id, tax_year)


async def update_filing_status_type(
    db: AsyncSession,
    filing_id: uuid.UUID,
    user_id: uuid.UUID,
    filing_status_type: str,
) -> Filing:
    repo = FilingRepository(db)
    filing = await repo.get_by_id(filing_id)
    if not filing or filing.user_id != user_id:
        raise NotFoundError("Filing not found")

    if filing.status not in (FilingStatus.DRAFT, FilingStatus.DATA_CONFIRMED):
        raise ConflictError("Filing cannot be modified in its current state")

    try:
        filing.filing_status_type = FilingStatusType(filing_status_type)
    except ValueError:
        valid = [s.value for s in FilingStatusType]
        raise ConflictError(
            f"Invalid filing status type. Must be one of: {', '.join(valid)}"
        )

    await db.flush()
    await db.refresh(filing)
    return filing


async def advance_status(
    db: AsyncSession,
    filing_id: uuid.UUID,
    user_id: uuid.UUID,
    new_status: str,
) -> Filing:
    repo = FilingRepository(db)
    filing = await repo.get_by_id(filing_id)
    if not filing or filing.user_id != user_id:
        raise NotFoundError("Filing not found")

    try:
        filing.status = FilingStatus(new_status)
    except ValueError:
        valid = [s.value for s in FilingStatus]
        raise ConflictError(
            f"Invalid status. Must be one of: {', '.join(valid)}"
        )

    await db.flush()
    await db.refresh(filing)
    return filing


def filing_to_response(filing: Filing) -> dict:
    return {
        "id": str(filing.id),
        "user_id": str(filing.user_id),
        "tax_year": filing.tax_year,
        "filing_status_type": (
            filing.filing_status_type.value
            if filing.filing_status_type
            else None
        ),
        "status": filing.status.value,
        "created_at": filing.created_at.isoformat(),
        "updated_at": filing.updated_at.isoformat(),
        "submitted_at": (
            filing.submitted_at.isoformat() if filing.submitted_at else None
        ),
    }
