"""Tests for persona voice scaffolding (WS-76 PR-32).

medallion: ops
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app as fastapi_app
from app.personas.pattern_classifier import (
    classify_pattern_compliance,
    pattern_contains_regulated_claims,
)
from app.personas.voice_system import (
    VoicePersona,
    can_pull_pattern,
    get_voice_persona,
    synthesize_post_stub,
)


def test_can_pull_pattern_blocks_promotional_for_compliance_gated_persona() -> None:
    brand = get_voice_persona("brand_axiomfolio")
    assert brand is not None
    ok, reason = can_pull_pattern(
        "founder_sankalp",
        brand,
        "regulated_promotional",
    )
    assert ok is False
    assert "below required" in reason


def test_can_pull_pattern_respects_cross_genre_source_allowlist() -> None:
    viral = get_voice_persona("viral_trader_humor")
    assert viral is not None
    ok, _reason = can_pull_pattern("founder_sankalp", viral, "regulated_safe")
    assert ok is True

    blocked, reason = can_pull_pattern("other_meme_pg", viral, "regulated_safe")
    assert blocked is False
    assert "not in cross_genre" in reason


def test_synthesize_post_stub_structure_and_routes() -> None:
    shadow = VoicePersona.model_validate(
        {
            "slug": "u_shadow",
            "voice": {"mode": "shadow"},
        }
    )
    out = synthesize_post_stub(shadow, {"topic": "alpha"})
    assert out["persona"] == "u_shadow"
    assert out["voice_mode"] == "shadow"
    assert out["route"] == "conversation"
    assert out["brief_echo"] == {"topic": "alpha"}
    assert out["draft"]["status"] == "stub"
    assert "body" in out["draft"]

    active = VoicePersona.model_validate(
        {
            "slug": "u_active",
            "voice": {"mode": "active"},
        }
    )
    out_a = synthesize_post_stub(active, {})
    assert out_a["route"] == "queue"


@pytest.mark.asyncio
async def test_voice_http_list_personas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "voice-test-secret")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(
            "/api/v1/voice/personas",
            headers={"X-Brain-Secret": "voice-test-secret"},
        )
    assert r.status_code == 200
    payload = r.json()
    assert payload["success"] is True
    slugs = {p["slug"] for p in payload["data"]}
    assert {"founder_sankalp", "viral_trader_humor", "brand_axiomfolio"}.issubset(slugs)


@pytest.mark.asyncio
async def test_voice_http_synthesize_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "voice-test-secret")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/voice/synthesize-stub",
            json={"persona_slug": "founder_sankalp", "brief": {"hook": "lesson"}},
            headers={"X-Brain-Secret": "voice-test-secret"},
        )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["route"] == "conversation"
    assert data["draft"]["status"] == "stub"


def test_pattern_classifier_forbidden_ticker_list() -> None:
    hit, reason = pattern_contains_regulated_claims(
        "Watching NVDA closely today.",
        forbidden_tickers=["NVDA"],
    )
    assert hit is True
    assert "NVDA" in reason


def test_pattern_classifier_flags_financial_promo_claims() -> None:
    flagged, reason = pattern_contains_regulated_claims(
        "This is risk-free and has guaranteed return.",
    )
    assert flagged is True
    assert "forbidden_claim" in reason

    level = classify_pattern_compliance("Clean thought on process.")
    assert level == "regulated_safe"
