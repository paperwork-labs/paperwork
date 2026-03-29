"""ClassifyAndRoute (D20 Pattern 3) — multi-provider model router with learning loop.

Every query goes through Gemini Flash classification (no rule-based heuristics).
Circuit breaker (D38) tracks per-provider failure rates in Redis.
ChainStrategy protocol for future patterns (P3-P5).
Routing decisions stored as episodes for self-improvement.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services import llm

logger = logging.getLogger(__name__)


# -- ChainStrategy Protocol (D20) ---------------------------------------------


class ChainContext:
    """Context passed through chain strategies."""

    def __init__(
        self,
        message: str,
        system_prompt: str,
        messages: list[dict[str, str]],
        channel_id: str | None = None,
        organization_id: str | None = None,
    ):
        self.message = message
        self.system_prompt = system_prompt
        self.messages = messages
        self.channel_id = channel_id
        self.organization_id = organization_id


@dataclass
class ChainResult:
    content: str
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    classification: dict = field(default_factory=dict)
    cost: float = 0.0


class ChainStrategy(Protocol):
    async def execute(self, context: ChainContext) -> ChainResult: ...


# -- Circuit Breaker (D38) -----------------------------------------------------


class CircuitBreaker:
    """Per-provider circuit breaker using Redis sliding window."""

    WINDOW_SECONDS = 300
    FAILURE_THRESHOLD_PCT = 50
    MIN_REQUESTS_FOR_RATE = 5
    COOLDOWN_SECONDS = 60

    def __init__(self, redis_client: Any | None = None):
        self._redis = redis_client
        self._local_events: dict[str, list[tuple[float, bool]]] = {}

    async def is_open(self, provider: str) -> bool:
        """Check if circuit is open (provider should be skipped)."""
        if self._redis:
            try:
                cooldown_key = f"circuit:{provider}:cooldown"
                val = await self._redis.get(cooldown_key)
                return val is not None
            except Exception:
                logger.debug("Circuit breaker Redis op failed", exc_info=True)

        events = self._local_events.get(provider, [])
        now = time.time()
        recent = [(t, ok) for t, ok in events if now - t < self.WINDOW_SECONDS]
        if len(recent) < self.MIN_REQUESTS_FOR_RATE:
            return False
        failures = sum(1 for _, ok in recent if not ok)
        return (failures / len(recent) * 100) >= self.FAILURE_THRESHOLD_PCT

    async def record_success(self, provider: str) -> None:
        now = time.time()
        self._local_events.setdefault(provider, []).append((now, True))
        self._prune_local(provider, now)
        if self._redis:
            try:
                await self._redis.delete(f"circuit:{provider}:cooldown")
            except Exception:
                logger.debug("Circuit breaker Redis op failed", exc_info=True)

    async def record_failure(self, provider: str) -> None:
        now = time.time()
        self._local_events.setdefault(provider, []).append((now, False))
        self._prune_local(provider, now)

        if self._redis:
            try:
                key = f"circuit:{provider}:failures"
                await self._redis.zadd(key, {str(now): now})
                await self._redis.zremrangebyscore(key, 0, now - self.WINDOW_SECONDS)
                total_key = f"circuit:{provider}:total"
                await self._redis.zadd(total_key, {str(now): now})
                await self._redis.zremrangebyscore(total_key, 0, now - self.WINDOW_SECONDS)
                fail_count = await self._redis.zcard(key)
                total_count = await self._redis.zcard(total_key)
                if total_count >= self.MIN_REQUESTS_FOR_RATE:
                    rate = (fail_count / total_count) * 100
                    if rate >= self.FAILURE_THRESHOLD_PCT:
                        cooldown_key = f"circuit:{provider}:cooldown"
                        await self._redis.setex(cooldown_key, self.COOLDOWN_SECONDS, "1")
                        logger.warning(
                            "Circuit OPEN for provider=%s (rate=%.0f%%, %d/%d)",
                            provider, rate, fail_count, total_count,
                        )
            except Exception:
                logger.debug("Circuit breaker Redis op failed", exc_info=True)

    def _prune_local(self, provider: str, now: float) -> None:
        self._local_events[provider] = [
            (t, ok) for t, ok in self._local_events.get(provider, [])
            if now - t < self.WINDOW_SECONDS
        ]


# -- Cost Calculator -----------------------------------------------------------


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate request cost from model registry."""
    info = llm.get_model_info(model)
    if not info:
        return 0.0
    cost_in = (tokens_in / 1_000_000) * info.get("cost_per_1m_input", 0)
    cost_out = (tokens_out / 1_000_000) * info.get("cost_per_1m_output", 0)
    return round(cost_in + cost_out, 6)


# -- Fallback Map --------------------------------------------------------------

FALLBACK_MAP = {
    "anthropic": {"provider": "openai", "model_map": {
        "claude-sonnet-4-20250514": "gpt-4o",
        "claude-opus-4-20250618": "gpt-4o",
    }},
    "openai": {"provider": "anthropic", "model_map": {
        "gpt-4o": "claude-sonnet-4-20250514",
        "gpt-4o-mini": "claude-sonnet-4-20250514",
        "o4-mini": "claude-sonnet-4-20250514",
    }},
    "google": {"provider": "openai", "model_map": {
        "gemini-2.5-flash": "gpt-4o-mini",
    }},
}


# -- ClassifyAndRoute Strategy -------------------------------------------------


class ClassifyAndRoute:
    """D20 Pattern 3 — Gemini Flash classifies, then routes to optimal model."""

    def __init__(self, circuit_breaker: CircuitBreaker):
        self.cb = circuit_breaker

    async def execute(self, context: ChainContext) -> ChainResult:
        classification = await llm.classify_query(
            context.message, context.channel_id
        )
        logger.info(
            "Classification: model=%s provider=%s tools=%s domain=%s conf=%.2f",
            classification.get("model"),
            classification.get("provider"),
            classification.get("tools_needed"),
            classification.get("domain"),
            classification.get("confidence", 0),
        )

        model = classification["model"]
        provider = classification["provider"]
        tools_needed = classification.get("tools_needed", False)

        if await self.cb.is_open(provider):
            fallback = FALLBACK_MAP.get(provider, {})
            new_provider = fallback.get("provider", "anthropic")
            model_map = fallback.get("model_map", {})
            model = model_map.get(model, "claude-sonnet-4-20250514")
            provider = new_provider
            logger.warning(
                "Circuit open for %s, falling back to %s/%s",
                classification["provider"], provider, model,
            )

        try:
            if tools_needed:
                if provider == "anthropic":
                    result = await llm.complete_with_mcp(
                        system_prompt=context.system_prompt,
                        messages=context.messages,
                        model=model,
                    )
                elif provider == "openai":
                    result = await llm.complete_openai_with_mcp(
                        system_prompt=context.system_prompt,
                        messages=context.messages,
                        model=model,
                    )
                else:
                    result = await llm.complete_with_mcp(
                        system_prompt=context.system_prompt,
                        messages=context.messages,
                    )
            else:
                result = await llm.complete_text(
                    system_prompt=context.system_prompt,
                    messages=context.messages,
                    model=model,
                    provider=provider,
                )

            await self.cb.record_success(provider)

        except Exception:
            logger.error("LLM call failed for %s/%s", provider, model, exc_info=True)
            await self.cb.record_failure(provider)
            result = llm._mock_response(context.messages)

        cost = calculate_cost(
            result.get("model", model),
            result.get("tokens_in", 0),
            result.get("tokens_out", 0),
        )

        return ChainResult(
            content=result.get("content", ""),
            model=result.get("model", model),
            provider=result.get("provider", provider),
            tokens_in=result.get("tokens_in", 0),
            tokens_out=result.get("tokens_out", 0),
            tool_calls=result.get("tool_calls", []),
            classification=classification,
            cost=cost,
        )


# -- Future chain strategies (stubs for P3-P5) ---------------------------------


class SearchAndSynthesize:
    """D20 Pattern 1 — Gemini Flash + Google Search -> Sonnet synthesis. (P3)"""

    async def execute(self, context: ChainContext) -> ChainResult:
        raise NotImplementedError("SearchAndSynthesize is Phase 3")


class ExtractAndReason:
    """D20 Pattern 2 — Flash extracts, Sonnet reasons. (P3)"""

    async def execute(self, context: ChainContext) -> ChainResult:
        raise NotImplementedError("ExtractAndReason is Phase 3")


class AdversarialReview:
    """D20 Pattern 4 — Sonnet generates, GPT-4o critiques, Sonnet revises. (P4)"""

    async def execute(self, context: ChainContext) -> ChainResult:
        raise NotImplementedError("AdversarialReview is Phase 4")


class Consensus:
    """D20 Pattern 5 — Parallel Claude + GPT-4o + Gemini -> synthesize. (P5)"""

    async def execute(self, context: ChainContext) -> ChainResult:
        raise NotImplementedError("Consensus is Phase 5")
