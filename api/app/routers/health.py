from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.base import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):  # noqa: B008
    db_connected = False
    try:
        await db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        pass

    status = "healthy" if db_connected else "degraded"
    return success_response({
        "status": status,
        "db_connected": db_connected,
        "version": settings.APP_VERSION,
    })
