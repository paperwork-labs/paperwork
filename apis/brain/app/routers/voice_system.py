"""HTTP surface for persona voice specs and synthesis stub.

medallion: ops
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.personas.voice_system import (
    VoicePersona,
    get_voice_persona,
    list_voice_personas,
    synthesize_post_stub,
)
from app.schemas.base import success_response

router = APIRouter(prefix="/voice", tags=["voice"])


def _verify_api_secret(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        if settings.ENVIRONMENT == "development":
            return
        raise HTTPException(status_code=503, detail="Brain API secret not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Brain-Secret")


class SynthesizeStubBody(BaseModel):
    persona_slug: str = Field(..., min_length=1, max_length=200)
    brief: dict[str, object] = Field(default_factory=dict)


@router.get("/personas")
async def voice_personas(
    _auth: None = Depends(_verify_api_secret),
) -> JSONResponse:
    """List voice-enabled personas loaded from ``app/personas/voice_specs``."""
    personas = list_voice_personas()
    return success_response([p.model_dump(mode="json") for p in personas])


@router.post("/synthesize-stub")
async def voice_synthesize_stub(
    body: SynthesizeStubBody,
    _auth: None = Depends(_verify_api_secret),
) -> JSONResponse:
    """Exercise :func:`synthesize_post_stub` without LLM."""
    persona: VoicePersona | None = get_voice_persona(body.persona_slug)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"unknown voice persona: {body.persona_slug!r}")
    result = synthesize_post_stub(persona, body.brief)
    return success_response(result)
