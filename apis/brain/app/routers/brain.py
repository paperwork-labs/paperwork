import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_brain_user_context
from app.redis import get_redis
from app.schemas.base import success_response
from app.schemas.brain import ProcessRequest
from app.schemas.brain_user_context import BrainUserContext
from app.services import agent
from app.tools import memory_tools

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
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Brain-Secret")


@router.post("/process")
async def process_message(
    body: ProcessRequest,
    db: AsyncSession = Depends(get_db),
    ctx: BrainUserContext = Depends(get_brain_user_context),
    _auth: None = Depends(_verify_api_secret),
):
    redis_client = None
    try:
        redis_client = get_redis()
    except RuntimeError:
        logger.warning("Redis unavailable — idempotency and fatigue disabled")

    if ctx.organization_id is not None and body.organization_id != ctx.organization_id:
        raise HTTPException(
            status_code=403,
            detail="organization_id does not match authenticated tenant",
        )

    org_name = ORG_NAME_CACHE.get(body.organization_id, body.organization_id)

    effective_user_id = (
        ctx.brain_user_id if ctx.auth_source == "clerk_jwt" else (body.user_id or ctx.brain_user_id)
    )

    mem_tok = memory_tools.set_organization_id(body.organization_id)
    try:
        result = await agent.process(
            db,
            redis_client,
            organization_id=body.organization_id,
            org_name=org_name,
            user_id=effective_user_id,
            message=body.message,
            channel=body.channel,
            channel_id=body.channel_id,
            request_id=body.request_id,
            thread_context=body.thread_context,
            thread_id=body.thread_id,
            persona_pin=body.persona_pin,
            strategy=body.strategy,
        )
    finally:
        memory_tools.reset_organization_id(mem_tok)

    return success_response(result)
