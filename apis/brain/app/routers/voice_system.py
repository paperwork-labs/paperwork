"""HTTP API for persona voice specs and stub synthesis.

medallion: ops
"""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.personas.voice_system import get_voice_persona, list_voice_personas, synthesize_post_stub
from app.schemas.base import success_response

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

router = APIRouter(prefix="/voice", tags=["voice"])


def _require_brain_secret(
    x_brain_secret: str | None = Header(None, alias="X-Brain-Secret"),
) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        if settings.ENVIRONMENT == "development":
            return
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Brain-Secret")


class SynthesizeStubRequest(BaseModel):
    persona_slug: str
    brief: dict[str, Any] = Field(default_factory=dict)


@router.get("/personas")
async def list_voice_enabled_personas(
    _auth: None = Depends(_require_brain_secret),
) -> JSONResponse:
    personas = list_voice_personas()
    return success_response({"personas": [p.model_dump() for p in personas]})


@router.post("/synthesize-stub")
async def voice_synthesize_stub(
    body: SynthesizeStubRequest,
    _auth: None = Depends(_require_brain_secret),
) -> JSONResponse:
    persona = get_voice_persona(body.persona_slug)
    if persona is None:
        raise HTTPException(status_code=404, detail="Unknown voice persona slug")
    payload = synthesize_post_stub(persona, body.brief)
    return success_response({"synthesis": payload})
