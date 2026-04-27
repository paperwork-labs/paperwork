from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.rate_limit import limiter
from app.schemas.base import success_response
from app.schemas.waitlist import WaitlistCreate
from app.services.waitlist import WaitlistService

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.post("")
@limiter.limit("5/minute")
async def join_waitlist(
    request: Request,
    data: WaitlistCreate,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    service = WaitlistService(db)
    entry = await service.join_waitlist(data)
    return success_response(
        {
            "id": str(entry.id),
            "email": entry.email,
            "source": entry.source,
            "created_at": entry.created_at.isoformat(),
        },
        status_code=201,
    )
