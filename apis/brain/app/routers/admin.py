import hmac
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.base import success_response
from app.services.seed import ingest_docs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


@router.post("/seed")
async def trigger_seed_ingestion(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    repo_root = os.environ.get(
        "REPO_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    count = await ingest_docs(db, repo_root)
    return success_response({"episodes_created": count})
