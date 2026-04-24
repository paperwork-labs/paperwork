"""Provider protocol for daily portfolio narrative (mirrors AnomalyExplainer LLMProvider pattern).

medallion: gold
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


class NarrativeProviderError(RuntimeError):
    """Recoverable provider failure; orchestrator falls back to template text."""


@dataclass(frozen=True)
class NarrativeResult:
    text: str
    provider: str
    model: str | None
    tokens_used: int | None
    cost_usd: Decimal | None
    is_fallback: bool
    prompt_hash: str


@runtime_checkable
class NarrativeProvider(Protocol):
    """One-shot narrative generation contract."""

    def generate(self, prompt: str, *, max_tokens: int = 400) -> NarrativeResult:
        """Return narrative text and usage metadata. May raise :class:`NarrativeProviderError`."""
        ...
