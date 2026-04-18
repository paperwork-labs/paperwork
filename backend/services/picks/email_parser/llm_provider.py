"""LLM provider abstraction for the email parser.

The parser orchestrator is provider-agnostic. Production deploys wire an
OpenAI / Anthropic backend; tests use ``StubLLMParseProvider`` (pure Python,
deterministic).

The provider sees:

    - System prompt (mode-selected by the parser based on source_format)
    - Normalized email body (text)
    - Candidate ticker hints (str list)
    - Optional PDF text
    - Optional image data URLs (vision-capable providers only)

It returns:

    - A single JSON document conforming to ``schemas.PARSE_OUTPUT_SCHEMA``
      (validated by the parser; invalid output is treated as a parse_error,
      not a crash).
    - Token + latency telemetry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Tuple, runtime_checkable


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str
    image_data_urls: Tuple[str, ...] = field(default_factory=tuple)
    json_schema: Mapping[str, Any] = field(default_factory=dict)
    max_tokens: int = 2000
    temperature: float = 0.0  # determinism preferred for parsing
    request_id: str = ""


@dataclass(frozen=True)
class LLMResponse:
    raw_text: str  # JSON serialized; the parser validates against the schema
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    provider: str = "unknown"
    model: str = "unknown"


@runtime_checkable
class LLMParseProvider(Protocol):
    """Single-call LLM contract the parser depends on."""

    def parse(self, request: LLMRequest) -> LLMResponse: ...  # pragma: no cover


# --------------------------------------------------------------------------- #
# Stub provider (testing)                                                     #
# --------------------------------------------------------------------------- #


class StubLLMParseProvider:
    """Returns a pre-baked response. Useful for testing the orchestrator
    without touching the network.

    Construct with `responses` as a list of strings; `parse()` pops them in
    order. If the list is exhausted, raises RuntimeError so tests fail loudly
    rather than reusing stale data.
    """

    def __init__(self, responses: list[str], provider_name: str = "stub") -> None:
        self._responses = list(responses)
        self._provider_name = provider_name
        self.calls: list[LLMRequest] = []

    def parse(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if not self._responses:
            raise RuntimeError(
                "StubLLMParseProvider exhausted: parse() called with no remaining responses"
            )
        text = self._responses.pop(0)
        return LLMResponse(
            raw_text=text,
            prompt_tokens=max(1, len(request.user_prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
            latency_ms=0,
            provider=self._provider_name,
            model="stub-model",
        )
