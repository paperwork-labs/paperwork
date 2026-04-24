"""
LLM provider abstraction for the AnomalyExplainer.

Why a Protocol instead of just calling :class:`AgentBrain` directly?

* The existing ``AgentBrain`` mixes chat, tool use, autonomy gating, and
  OpenAI-specific knobs. We need a small, single-purpose interface for
  one-shot "explain this anomaly" calls.
* Tests need a deterministic stub. Making the explainer accept an
  ``LLMProvider`` lets us inject a ``StubLLMProvider`` that returns
  canned strings, so the explainer can be unit-tested without network,
  API keys, or rate-limit jitter.
* When we add Anthropic / a local model later, we add a new
  implementation here -- the explainer never changes.

Implementations live next to this file so the explainer module stays
provider-agnostic.

medallion: ops
"""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot fulfill a request.

    The explainer treats this as a *recoverable* error -- it falls back
    to a deterministic rule-based explanation and marks ``is_fallback=True``.
    """


class LLMProviderRateLimitedError(LLMProviderError):
    """OpenAI (or other API) still returning 429 after the retry budget.

    Callers that must avoid burning fallbacks (e.g. cost caps) can catch
    this and skip a single request instead of treating it as generic LLM
    failure.
    """


@runtime_checkable
class LLMProvider(Protocol):
    """One-shot text completion contract.

    The explainer calls ``complete_json(system_prompt, user_prompt)`` and
    expects a JSON-decodable string back. It is the provider's job to
    ask the underlying model for JSON output (e.g. via
    ``response_format={"type": "json_object"}`` for OpenAI).

    Providers MUST raise :class:`LLMProviderError` (not bare exceptions)
    on any kind of failure so the explainer's ``except`` block stays
    narrow.
    """

    name: str  # short slug, e.g. "openai:gpt-4o-mini"

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        """Return the model's raw JSON-shaped string. May raise :class:`LLMProviderError`."""
        ...


class StubLLMProvider:
    """Deterministic test double.

    Pop-from-the-front returns let tests script multi-call sequences and
    assert the explainer behaves correctly across retries / batch calls.
    """

    name = "stub"

    def __init__(self, responses: List[str]) -> None:
        if not isinstance(responses, list):
            raise TypeError("responses must be a list[str]")
        self._responses: List[str] = list(responses)
        self.calls: List[tuple] = []  # for assertions in tests

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        self.calls.append((system_prompt, user_prompt, max_tokens, temperature))
        if not self._responses:
            raise LLMProviderError("StubLLMProvider exhausted: no scripted responses left")
        return self._responses.pop(0)


class AlwaysFailingProvider:
    """Provider that always raises -- exercises the explainer's fallback path."""

    name = "always_failing"

    def __init__(self, message: str = "synthetic failure") -> None:
        self._message = message

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        raise LLMProviderError(self._message)
