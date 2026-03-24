import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.redis import get_redis
from app.schemas.base import success_response
from app.schemas.brain import ProcessRequest
from app.services import agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brain", tags=["brain"])

ORG_NAME_CACHE: dict[str, str] = {
    "paperwork-labs": "Paperwork Labs",
    "platform": "Platform Brain",
}


def _verify_api_secret(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        if settings.ENVIRONMENT == "development":
            return
        raise HTTPException(status_code=503, detail="Brain API secret not configured")
    if not x_brain_secret or x_brain_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Brain-Secret")


@router.post("/process")
async def process_message(
    body: ProcessRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_verify_api_secret),
):
    redis_client = None
    try:
        redis_client = get_redis()
    except RuntimeError:
        logger.warning("Redis unavailable — idempotency and fatigue disabled")

    org_name = ORG_NAME_CACHE.get(body.organization_id, body.organization_id)

    result = await agent.process(
        db,
        redis_client,
        organization_id=body.organization_id,
        org_name=org_name,
        user_id=body.user_id,
        message=body.message,
        channel=body.channel,
        channel_id=body.channel_id,
        request_id=body.request_id,
        thread_context=body.thread_context,
    )

    return success_response(result)
