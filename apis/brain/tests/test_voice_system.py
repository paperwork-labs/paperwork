"""Tests for persona voice policy, pattern classifier stub, and voice HTTP routes.

medallion: ops
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app as fastapi_app
from app.personas.pattern_classifier import pattern_contains_regulated_content
from app.personas.voice_system import (
    VoiceConfig,
    VoicePersona,
    can_pull_pattern,
    synthesize_post_stub,
)


def _sample_shadow() -> VoicePersona:
    return VoicePersona(slug="shadow_test", voice=VoiceConfig(mode="shadow"))


def _sample_active() -> VoicePersona:
    return VoicePersona(slug="active_test", voice=VoiceConfig(mode="active"))


def test_can_pull_pattern_blocks_scanned_regulated_content() -> None:
    target = VoicePersona(
        slug="brand_axiomfolio",
        voice=VoiceConfig(
            cross_genre_pull_allowed={
                "sources": ["founder_sankalp"],
                "min_compliance_level": "regulated_safe",
            },
        ),
    )
    ok, reason = can_pull_pattern(
        "founder_sankalp",
        target,
        "regulated_safe",
        pattern_text="This offer is completely risk-free!",
    )
    assert ok is False
    assert reason.startswith("regulated_content:")


def test_can_pull_pattern_blocks_noncompliant_level() -> None:
    target = _sample_shadow()
    ok, reason = can_pull_pattern("shadow_test", target, "regulated_claim")
    assert ok is False
    assert reason == "pattern_marked_noncompliant"


def test_can_pull_pattern_cross_genre_requires_allowlist() -> None:
    target = VoicePersona(
        slug="brand_axiomfolio",
        voice=VoiceConfig(
            cross_genre_pull_allowed={"sources": [], "min_compliance_level": "regulated_safe"},
        ),
    )
    ok, reason = can_pull_pattern("founder_sankalp", target, "regulated_safe")
    assert ok is False
    assert reason == "cross_genre_pull_disabled"


def test_synthesize_post_stub_structure_and_shadow_routing() -> None:
    persona = _sample_shadow()
    out = synthesize_post_stub(persona, {"topic": "shipping cadence"})
    assert out["stub"] is True
    assert out["voice_mode"] == "shadow"
    assert out["destination"] == "conversation"
    assert out["persona_slug"] == "shadow_test"
    assert out["brief"]["topic"] == "shipping cadence"


def test_synthesize_post_stub_active_routes_to_queue() -> None:
    persona = _sample_active()
    out = synthesize_post_stub(persona, {})
    assert out["destination"] == "queue"
    assert out["voice_mode"] == "active"


def test_pattern_classifier_tickers_and_claims() -> None:
    blocked, r = pattern_contains_regulated_content("guaranteed return tomorrow")
    assert blocked and "forbidden_claim" in r
    blocked_t, _ = pattern_contains_regulated_content("YOLO into $GME")
    assert blocked_t


@pytest.mark.asyncio
async def test_voice_personas_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "voice-secret")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/voice/personas")
        assert res.status_code == 401
        ok = await ac.get("/api/v1/voice/personas", headers={"X-Brain-Secret": "voice-secret"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["success"] is True
    slugs = {p["slug"] for p in body["data"]["personas"]}
    assert slugs >= {"founder_sankalp", "viral_trader_humor", "brand_axiomfolio"}


@pytest.mark.asyncio
async def test_voice_synthesize_stub_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "voice-secret")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/voice/synthesize-stub",
            headers={"X-Brain-Secret": "voice-secret"},
            json={"persona_slug": "founder_sankalp", "brief": {"hook": "idea"}},
        )
    assert res.status_code == 200
    syn = res.json()["data"]["synthesis"]
    assert syn["destination"] == "conversation"
    assert syn["stub"] is True
