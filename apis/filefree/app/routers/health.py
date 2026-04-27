import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.base import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_connected = False
    db_error = None
    try:
        await db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as exc:
        db_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Health check DB connection failed: %s", db_error)

    status = "healthy" if db_connected else "degraded"
    data: dict[str, Any] = {
        "status": status,
        "db_connected": db_connected,
        "version": settings.APP_VERSION,
    }
    if db_error and settings.DEBUG:
        data["db_error"] = db_error
    return success_response(data)
