import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.redis import get_redis
from app.schemas.base import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return success_response(
        {
            "status": "ok",
            "service": "brain",
            "version": settings.APP_VERSION,
        }
    )


@router.get("/health/deep")
async def deep_health_check(db: AsyncSession = Depends(get_db)):
    db_connected = False
    db_error = None
    try:
        await db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as exc:
        db_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Deep health check DB failed: %s", db_error)

    redis_connected = False
    redis_error = None
    try:
        redis_client = get_redis()
        await redis_client.ping()
        redis_connected = True
    except Exception as exc:
        redis_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Deep health check Redis failed: %s", redis_error)

    all_healthy = db_connected and redis_connected
    status = "healthy" if all_healthy else "degraded"
    data: dict = {
        "status": status,
        "service": "brain",
        "version": settings.APP_VERSION,
        "db_connected": db_connected,
        "redis_connected": redis_connected,
    }
    if settings.DEBUG:
        if db_error:
            data["db_error"] = db_error
        if redis_error:
            data["redis_error"] = redis_error

    status_code = 200 if all_healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": data},
    )
