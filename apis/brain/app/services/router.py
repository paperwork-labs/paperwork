"""ClassifyAndRoute (D20 Pattern 3) — multi-provider model router with learning loop.

Every query goes through Gemini Flash classification (no rule-based heuristics).
Circuit breaker (D38) tracks per-provider failure rates in Redis.
ChainStrategy protocol for future patterns (P3-P5).
Routing decisions stored as episodes for self-improvement.

medallion: ops
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services import llm
from app.services.errors import LLMUnavailableError

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


def _provider_for_model(model: str) -> str:
    """Infer provider from a model slug. Keep in sync with FALLBACK_MAP."""
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("gemini-"):
        return "google"
    return "openai"


class PersonaPinnedRoute:
    """Route a request using a PersonaSpec's pinned model contract.

    No Gemini classifier call (the spec already declares the model). No
    keyword heuristics for "does this need tools" (the spec declares
    `requires_tools`). Escalation is driven by three deterministic
    signals: compliance, exact token count (via tiktoken), and mention
    keywords.

    On every-provider failure this raises `LLMUnavailableError` so the
    agent layer can return an honest error response rather than silently
    handing the user mock content.
    """

    def __init__(
        self,
        circuit_breaker: CircuitBreaker,
        *,
        model: str,
        escalation_model: str | None,
        escalate_on_compliance: bool,
        escalate_on_tokens_over: int | None,
        escalate_on_mentions: list[str],
        input_tokens: int,
        requires_tools: bool,
        max_output_tokens: int | None = None,
    ):
        self.cb = circuit_breaker
        self.model = model
        self.escalation_model = escalation_model
        self.escalate_on_compliance = escalate_on_compliance
        self.escalate_on_tokens_over = escalate_on_tokens_over
        self.escalate_on_mentions = [m.lower() for m in escalate_on_mentions]
        self.input_tokens = input_tokens
        self.requires_tools = requires_tools
        self.max_output_tokens = max_output_tokens

    async def execute(self, context: ChainContext) -> ChainResult:
        model = self.model
        escalated = False
        escalation_reason: str | None = None
        if self.escalation_model:
            if self.escalate_on_compliance:
                model, escalated, escalation_reason = (
                    self.escalation_model, True, "compliance",
                )
            elif any(m in context.message.lower() for m in self.escalate_on_mentions):
                model, escalated, escalation_reason = (
                    self.escalation_model, True, "mention",
                )
            elif (
                self.escalate_on_tokens_over is not None
                and self.input_tokens > self.escalate_on_tokens_over
            ):
                model, escalated, escalation_reason = (
                    self.escalation_model, True, "tokens",
                )

        provider = _provider_for_model(model)

        if await self.cb.is_open(provider):
            fallback = FALLBACK_MAP.get(provider, {})
            new_provider = fallback.get("provider", "anthropic")
            model_map = fallback.get("model_map", {})
            model = model_map.get(model, "claude-sonnet-4-20250514")
            provider = new_provider
            logger.warning(
                "Circuit open for pinned persona route, falling back to %s/%s",
                provider, model,
            )

        # Track I: persona-specified max_output_tokens caps the response size
        # so a chatty persona can't stream 8k tokens of hedging. Passes
        # through to each provider's max_tokens / max_output_tokens param.
        llm_kwargs: dict[str, Any] = {}
        if self.max_output_tokens is not None:
            llm_kwargs["max_tokens"] = self.max_output_tokens

        try:
            if self.requires_tools and provider == "anthropic":
                result = await llm.complete_with_mcp(
                    system_prompt=context.system_prompt,
                    messages=context.messages,
                    model=model,
                    **llm_kwargs,
                )
            elif self.requires_tools and provider == "openai":
                result = await llm.complete_openai_with_mcp(
                    system_prompt=context.system_prompt,
                    messages=context.messages,
                    model=model,
                    **llm_kwargs,
                )
            else:
                result = await llm.complete_text(
                    system_prompt=context.system_prompt,
                    messages=context.messages,
                    model=model,
                    provider=provider,
                    **llm_kwargs,
                )
            await self.cb.record_success(provider)
        except Exception as exc:
            logger.error(
                "PersonaPinnedRoute LLM call failed for %s/%s",
                provider, model, exc_info=True,
            )
            await self.cb.record_failure(provider)
            raise LLMUnavailableError(
                provider=provider, model=model, reason=str(exc),
            ) from exc

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
            classification={
                "strategy": "persona_pinned",
                "escalated": escalated,
                "escalation_reason": escalation_reason,
                "requires_tools": self.requires_tools,
                "input_tokens_measured": self.input_tokens,
            },
            cost=cost,
        )


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

        except Exception as exc:
            logger.error("LLM call failed for %s/%s", provider, model, exc_info=True)
            await self.cb.record_failure(provider)
            raise LLMUnavailableError(
                provider=provider, model=model, reason=str(exc),
            ) from exc

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
    """D20 Pattern 2 — Flash extracts, Sonnet reasons. (P3 — Buffer Week 4)

    Two-hop: (1) Gemini Flash reads the raw message and emits a compact
    structured digest (facts, entities, ambiguities, ask). (2) Claude
    Sonnet receives that digest plus the original message and produces the
    user-facing response. For heavy domain calls (CPA tax memo, QA incident
    triage) this routinely halves Sonnet token cost because the big model
    doesn't have to re-parse context every turn — and it lets the cheap
    model catch "this message is actually three questions, ask back" cases
    before Sonnet commits to a single answer.

    Failures fall back to ClassifyAndRoute so a Flash outage never dead-ends
    a persona call.
    """

    EXTRACTION_MODEL = "gemini-2.0-flash-exp"
    EXTRACTION_PROVIDER = "google"
    REASONING_MODEL = "claude-sonnet-4-20250514"
    REASONING_PROVIDER = "anthropic"

    EXTRACTION_SYSTEM = (
        "You are a fast context extractor. Given the user's message and a "
        "short system brief, emit a JSON object with these keys: "
        "'facts' (list[str] — concrete, load-bearing facts from the "
        "message), 'entities' (list[str] — names, tickers, dollar amounts, "
        "dates), 'ambiguities' (list[str] — what would change the answer "
        "if clarified), 'ask' (str — the specific thing the user wants). "
        "Keep every list <= 5 items. Respond with JSON only, no prose."
    )

    def __init__(self, circuit_breaker: CircuitBreaker):
        self.cb = circuit_breaker

    async def execute(self, context: ChainContext) -> ChainResult:
        import json

        extraction_text = ""
        try:
            if not await self.cb.is_open(self.EXTRACTION_PROVIDER):
                ext_result = await llm.complete_text(
                    system_prompt=self.EXTRACTION_SYSTEM,
                    messages=[{"role": "user", "content": context.message}],
                    model=self.EXTRACTION_MODEL,
                    provider=self.EXTRACTION_PROVIDER,
                    max_tokens=400,
                    temperature=0.0,
                )
                extraction_text = ext_result.get("content", "").strip()
                await self.cb.record_success(self.EXTRACTION_PROVIDER)
        except Exception:
            logger.warning(
                "ExtractAndReason: extraction step failed, continuing "
                "without digest",
                exc_info=True,
            )
            await self.cb.record_failure(self.EXTRACTION_PROVIDER)

        augmented_system = context.system_prompt
        if extraction_text:
            digest_block = extraction_text
            try:
                parsed = json.loads(extraction_text)
                digest_block = json.dumps(parsed, indent=2)
            except (ValueError, TypeError):
                pass
            augmented_system = (
                f"{context.system_prompt}\n\n"
                "--- Pre-extracted context (Flash digest, treat as hints "
                "not facts) ---\n"
                f"{digest_block}\n"
                "--- End digest ---"
            )

        provider = self.REASONING_PROVIDER
        model = self.REASONING_MODEL
        if await self.cb.is_open(provider):
            fallback = FALLBACK_MAP.get(provider, {})
            provider = fallback.get("provider", "openai")
            model = fallback.get("model_map", {}).get(model, "gpt-4o")
            logger.warning(
                "ExtractAndReason: Sonnet circuit open, fallback to %s/%s",
                provider, model,
            )

        try:
            reason_result = await llm.complete_text(
                system_prompt=augmented_system,
                messages=context.messages,
                model=model,
                provider=provider,
                max_tokens=2048,
            )
            await self.cb.record_success(provider)
        except Exception as exc:
            await self.cb.record_failure(provider)
            raise LLMUnavailableError(
                provider=provider, model=model, reason=str(exc),
            ) from exc

        total_tokens_in = reason_result.get("tokens_in", 0)
        total_tokens_out = reason_result.get("tokens_out", 0)
        cost = calculate_cost(
            reason_result.get("model", model),
            total_tokens_in,
            total_tokens_out,
        )

        return ChainResult(
            content=reason_result.get("content", ""),
            model=reason_result.get("model", model),
            provider=reason_result.get("provider", provider),
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            tool_calls=reason_result.get("tool_calls", []),
            classification={
                "strategy": "extract_and_reason",
                "extraction_model": self.EXTRACTION_MODEL,
                "extraction_succeeded": bool(extraction_text),
                "reasoning_model": reason_result.get("model", model),
            },
            cost=cost,
        )


class AdversarialReview:
    """D20 Pattern 4 — Sonnet generates, GPT-4o critiques, Sonnet revises. (P4)"""

    async def execute(self, context: ChainContext) -> ChainResult:
        raise NotImplementedError("AdversarialReview is Phase 4")


class Consensus:
    """D20 Pattern 5 — Parallel Claude + GPT-4o + Gemini -> synthesize. (P5)"""

    async def execute(self, context: ChainContext) -> ChainResult:
        raise NotImplementedError("Consensus is Phase 5")
