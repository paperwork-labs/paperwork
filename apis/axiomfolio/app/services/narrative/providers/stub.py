"""Deterministic narrative provider for tests.

medallion: gold
"""

from __future__ import annotations

import hashlib

from app.services.narrative.provider import NarrativeResult


class StubNarrativeProvider:
    """Returns stable text derived from the prompt (no network)."""

    def generate(self, prompt: str, *, max_tokens: int = 400) -> NarrativeResult:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        body = (
            f"[stub narrative] digest={digest} max_tokens={max_tokens} "
            f"chars={len(prompt)}"
        )
        ph = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return NarrativeResult(
            text=body,
            provider="stub",
            model="stub",
            tokens_used=0,
            cost_usd=None,
            is_fallback=False,
            prompt_hash=ph,
        )
