"""Narrative provider unit tests."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.services.narrative.builder import build_narrative_prompt, render_narrative
from app.services.narrative.provider import NarrativeProviderError, NarrativeResult
from app.services.narrative.providers.fallback_template import render_from_summary
from app.services.narrative.providers.openai_chat import OpenAIChatProvider
from app.services.narrative.providers.stub import StubNarrativeProvider


def test_stub_narrative_provider_deterministic():
    p = StubNarrativeProvider()
    prompt = "hello narrative"
    r1 = p.generate(prompt, max_tokens=400)
    r2 = p.generate(prompt, max_tokens=400)
    assert r1.text == r2.text
    assert r1.provider == "stub"
    assert r1.prompt_hash == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert "digest=" in r1.text


def test_fallback_template_from_summary():
    summary = {
        "top_movers": [{"symbol": "AAPL", "day_pnl_pct": 2.5}],
        "n_movers_over_threshold": 2,
        "regime": "R2 (Bull Extended)",
        "portfolio_return_pct": 1.8,
        "spy_return_pct": 1.2,
    }
    res = render_from_summary(summary)
    assert res.is_fallback is True
    assert res.provider == "fallback_template"
    assert "AAPL" in res.text
    assert "Macro regime" in res.text
    assert (
        res.prompt_hash
        == hashlib.sha256(
            json.dumps(dict(summary), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
    )


class _RaisingNarrativeProvider:
    def generate(self, prompt: str, *, max_tokens: int = 400) -> NarrativeResult:
        raise NarrativeProviderError("synthetic openai failure")


def test_render_narrative_falls_back_when_provider_raises():
    summary = {
        "top_movers": [{"symbol": "NVDA", "day_pnl_pct": 3.0}],
        "n_movers_over_threshold": 1,
        "regime_state": "R3",
        "regime": "R3 (Chop)",
    }
    out = render_narrative(summary, _RaisingNarrativeProvider())
    assert out.is_fallback is True
    assert out.provider == "fallback_template"
    assert "NVDA" in out.text
    prompt = build_narrative_prompt(summary)
    assert out.prompt_hash == hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def test_openai_provider_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = OpenAIChatProvider(api_key=None)
    with pytest.raises(NarrativeProviderError, match="OPENAI_API_KEY"):
        p.generate("x", max_tokens=10)
