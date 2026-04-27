from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_csrf
from app.models.filing import FilingStatus
from app.models.tax_calculation import TaxCalculation
from app.models.user import User
from app.rate_limit import get_user_rate_limit_key, limiter
from app.repositories.filing import FilingRepository
from app.schemas.base import success_response
from app.services import tax_calculator
from app.utils.exceptions import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/tax", tags=["tax"])


def _parse_uuid(filing_id: str) -> UUID:
    try:
        return UUID(filing_id)
    except ValueError as err:
        raise ValidationError("Invalid filing ID format") from err


@router.post("/calculate/{filing_id}")
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def calculate(
    request: Request,
    filing_id: str,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    fid = _parse_uuid(filing_id)
    repo = FilingRepository(db)
    filing = await repo.get_by_id_with_relations(fid)

    if not filing or filing.user_id != user.id:
        raise NotFoundError("Filing not found")

    if not filing.filing_status_type:
        raise ConflictError("Filing status type must be set before calculating")

    total_wages = 0
    total_fed_withheld = 0
    total_state_withheld = 0

    if filing.documents:
        for doc in filing.documents:
            if doc.extraction_data:
                total_wages += doc.extraction_data.get("wages", 0)
                total_fed_withheld += doc.extraction_data.get("federal_tax_withheld", 0)
                total_state_withheld += doc.extraction_data.get("state_tax_withheld", 0)

    if filing.tax_profile:
        total_wages = filing.tax_profile.total_wages or total_wages
        total_fed_withheld = filing.tax_profile.total_federal_withheld or total_fed_withheld
        total_state_withheld = filing.tax_profile.total_state_withheld or total_state_withheld

    result = tax_calculator.calculate_return(
        total_wages_cents=total_wages,
        total_federal_withheld_cents=total_fed_withheld,
        total_state_withheld_cents=total_state_withheld,
        filing_status=filing.filing_status_type.value,
        year=filing.tax_year,
    )

    existing_calc = filing.tax_calculation
    if existing_calc:
        for key, value in result.items():
            setattr(existing_calc, key, value)
        existing_calc.calculated_at = datetime.now(UTC)
        calc = existing_calc
    else:
        calc = TaxCalculation(filing_id=fid, **result)
        db.add(calc)

    filing.status = FilingStatus.CALCULATED
    await db.flush()
    await db.refresh(calc)

    return success_response(
        {
            "adjusted_gross_income": calc.adjusted_gross_income,
            "standard_deduction": calc.standard_deduction,
            "taxable_income": calc.taxable_income,
            "federal_tax": calc.federal_tax,
            "state_tax": calc.state_tax,
            "total_withheld": calc.total_withheld,
            "refund_amount": calc.refund_amount,
            "owed_amount": calc.owed_amount,
            "calculated_at": calc.calculated_at.isoformat(),
        }
    )


@router.get("/calculation/{filing_id}")
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def get_calculation(
    request: Request,
    filing_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    fid = _parse_uuid(filing_id)
    repo = FilingRepository(db)
    filing = await repo.get_by_id_with_relations(fid)

    if not filing or filing.user_id != user.id:
        raise NotFoundError("Filing not found")

    calc = filing.tax_calculation
    if not calc:
        raise NotFoundError("No calculation found for this filing")

    return success_response(
        {
            "adjusted_gross_income": calc.adjusted_gross_income,
            "standard_deduction": calc.standard_deduction,
            "taxable_income": calc.taxable_income,
            "federal_tax": calc.federal_tax,
            "state_tax": calc.state_tax,
            "total_withheld": calc.total_withheld,
            "refund_amount": calc.refund_amount,
            "owed_amount": calc.owed_amount,
            "ai_insights": calc.ai_insights,
            "calculated_at": calc.calculated_at.isoformat(),
        }
    )
