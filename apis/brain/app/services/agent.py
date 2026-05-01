"""Brain agent loop — receives a message, classifies, routes, responds, learns.

D20: ClassifyAndRoute selects model + provider via Gemini Flash classifier.
D37: Constitutional safety check on every response.
D38: Circuit breaker per provider.
MCP: Anthropic/OpenAI handle tool execution server-side (no D2 client loop).

Pipeline per request:
1. Check idempotency (D10)
2. Route persona
3. Retrieve relevant episodes (hybrid search)
4. ClassifyAndRoute -> picks model + provider + tools_needed
5. Assemble system prompt + context
6. One API call (with MCP if tools needed)
7. Constitutional safety check (D37)
8. Store episode + routing decision
9. Return response

medallion: ops
"""

import contextlib
import logging
import re
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.personas import get_spec as get_persona_spec
from app.personas.routing import route_persona
from app.services import cost_tracker, idempotency, memory, persona_rate_limit
from app.services.cost_tracker import CostCeilingExceeded
from app.services.errors import LLMUnavailableError
from app.services.observability import create_trace
from app.services.observability import flush as flush_traces
from app.services.persona_rate_limit import PersonaRateLimitExceeded
from app.services.pii import scrub_pii
from app.services.router import (
    ChainContext,
    ChainResult,
    CircuitBreaker,
    ClassifyAndRoute,
    ExtractAndReason,
    PersonaPinnedRoute,
)
from app.services.tokens import count_tokens

logger = logging.getLogger(__name__)

PERSONA_MDC_PREFIX = ".cursor/rules/"
PERSONA_CACHE_TTL = 3600

# Track F / H12: the Brain container ships with persona .mdc files copied from
# .cursor/rules/ at build time (see apis/brain/Dockerfile). Reading from disk
# beats a live GitHub fetch for cold-start latency and makes the persona a
# hermetic artifact of the image rather than a runtime network dependency.
# Set BRAIN_PERSONA_LOCAL_DIR to override in tests / dev.
_BUNDLED_PERSONA_DIR = Path(__file__).resolve().parent.parent.parent / "cursor-rules"

SYSTEM_PROMPT_TEMPLATE = """You are the Brain for {org_name} — an intelligent assistant.
You are operating as the {persona} persona.

{tone_prefix}
{persona_instructions}

## Your Memory (retrieved context)
{memory_context}

## Rules
- Be concise and actionable. Lead with the answer.
- Use your memory to provide personalized, context-aware responses.
- If you don't have enough context, use tools (read_github_file,
  search_github_code) to find answers.
- Never expose raw PII (SSNs, passwords, API keys) in your responses.
- If asked about something in your memory, cite it naturally.
- For project status, task progress, or "what to work on" questions, use
  read_github_file to read docs/TASKS.md.
- When using tools, prefer search_memory first for context before calling external tools.
"""


def _read_bundled_persona(persona: str) -> str:
    """Return the persona mdc shipped inside the image, or empty string.

    Kept sync because it's a sub-millisecond disk read; no reason to pay the
    coroutine overhead.
    """
    try:
        path = _BUNDLED_PERSONA_DIR / f"{persona}.mdc"
        if path.exists():
            return path.read_text(encoding="utf-8")[:15000]
    except Exception:
        logger.warning("Failed to read bundled persona %s", persona, exc_info=True)
    return ""


async def _load_persona_instructions(persona: str, redis_client: Any) -> str:
    """Load persona .mdc instructions with a three-tier fallback.

    Order:
      1. Redis (hot path, TTL ``PERSONA_CACHE_TTL``)
      2. Bundled in image at /app/cursor-rules/<persona>.mdc (Track F / H12)
      3. Live GitHub fetch via ``read_github_file`` (last resort — only hit
         when the persona was added after the image was built)

    Returns an empty string if all tiers miss — the caller falls back to the
    base system prompt rather than failing.
    """
    cache_key = f"persona_mdc:{persona}"

    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return cached if isinstance(cached, str) else cached.decode("utf-8")
        except Exception:
            logger.debug("Redis persona cache miss/error for %s", persona)

    bundled = _read_bundled_persona(persona)
    if bundled:
        if redis_client:
            try:
                await redis_client.setex(cache_key, PERSONA_CACHE_TTL, bundled)
            except Exception:
                logger.debug("Failed to cache persona .mdc for %s", persona)
        return bundled

    try:
        from app.tools.github import read_github_file

        mdc_path = f"{PERSONA_MDC_PREFIX}{persona}.mdc"
        content = await read_github_file(mdc_path, max_chars=15000)
        if content and "Not found:" not in content and "error:" not in content.lower():
            if redis_client:
                try:
                    await redis_client.setex(cache_key, PERSONA_CACHE_TTL, content)
                except Exception:
                    logger.debug("Failed to cache persona .mdc for %s", persona)
            return content
    except Exception:
        logger.warning("Failed to load persona .mdc for %s", persona, exc_info=True)

    return ""


_constitution: list[dict] | None = None
_circuit_breaker: CircuitBreaker | None = None


def _load_constitution() -> list[dict]:
    global _constitution
    if _constitution is None:
        path = Path(__file__).resolve().parent.parent.parent / "constitution.yaml"
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                _constitution = data.get("principles", [])
                logger.info("Loaded %d constitutional principles", len(_constitution))
        else:
            logger.warning("constitution.yaml not found at %s", path)
            _constitution = []
    return _constitution


def _check_constitution(response_text: str) -> list[dict]:
    """P1 rule-based constitutional check. Returns list of violations."""
    principles = _load_constitution()
    violations = []

    checks: dict[str, Any] = {
        "PII_NEVER_EXPOSED": _check_pii_leak,
        "HONEST_LIMITATIONS": _check_fabrication_markers,
        "NO_TAX_ADVICE": _check_tax_advice,
        "NO_LEGAL_ADVICE": _check_legal_advice,
        "NO_INVESTMENT_ADVICE": _check_investment_advice,
    }

    for principle in principles:
        pid = principle.get("id", "")
        checker = checks.get(pid)
        if checker and checker(response_text):
            violations.append(
                {
                    "principle_id": pid,
                    "name": principle.get("name", ""),
                    "severity": principle.get("severity", "medium"),
                }
            )

    return violations


_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EIN_PATTERN = re.compile(r"\b\d{2}-\d{7}\b")


_API_KEY_PATTERNS = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|ghu_[a-zA-Z0-9]{36,}"
    r"|xox[bpsa]-[a-zA-Z0-9\-]{10,}|AKIA[0-9A-Z]{16})"
)


def _check_pii_leak(text: str) -> bool:
    """Check if response contains unmasked SSN, EIN, or API key patterns."""
    for m in _SSN_PATTERN.findall(text):
        if not m.startswith("XXX") and not m.startswith("***"):
            return True
    for m in _EIN_PATTERN.findall(text):
        if not m.startswith("XX") and not m.startswith("**"):
            return True
    return bool(_API_KEY_PATTERNS.search(text))


def _check_fabrication_markers(text: str) -> bool:
    """Check for confident claims about specific amounts without qualification."""
    danger_phrases = [
        "your refund will be exactly",
        "you will owe exactly",
        "guaranteed return of",
        "your tax liability is $",
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in danger_phrases)


def _check_tax_advice(text: str) -> bool:
    """Check for directive tax advice (Circular 230)."""
    directive_phrases = [
        "you should file as",
        "you need to claim",
        "you must deduct",
        "i recommend filing",
        "file as head of household",
        "take the standard deduction",
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in directive_phrases)


def _check_legal_advice(text: str) -> bool:
    """Check for directive legal advice (UPL prevention)."""
    directive_phrases = [
        "you should form in",
        "you should incorporate in",
        "i recommend forming",
        "you need to register in",
        "form your llc in delaware",
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in directive_phrases)


def _check_investment_advice(text: str) -> bool:
    """Check for directive investment advice."""
    directive_phrases = [
        "you should buy",
        "you should sell",
        "i recommend buying",
        "i recommend selling",
        "you need to invest in",
        "buy this stock",
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in directive_phrases)


def _get_circuit_breaker(redis_client: Any) -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker(redis_client)
    return _circuit_breaker


async def process(
    db: AsyncSession,
    redis_client: Any,
    *,
    organization_id: str,
    org_name: str,
    user_id: str | None = None,
    message: str,
    channel: str | None = None,
    channel_id: str | None = None,
    request_id: str | None = None,
    thread_context: list[dict[str, str]] | None = None,
    thread_id: str | None = None,
    persona_pin: str | None = None,
    strategy: str | None = None,
) -> dict:
    """Main agent loop entry point.

    ``persona_pin`` (Track F) lets trusted callers (tool handlers, schedulers)
    bypass the keyword router and force a specific persona. When set, the router
    returns the pinned slug verbatim and the rest of the pipeline (PersonaSpec
    lookup, model routing, cost ceiling) runs against that persona.
    """

    is_duplicate = await idempotency.check_and_set(redis_client, request_id, organization_id)
    if is_duplicate:
        logger.info("Duplicate request %s, skipping", request_id)
        return {
            "response": "",
            "persona": "system",
            "model": "none",
            "provider": "none",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost": 0.0,
            "is_duplicate": True,
        }

    trace = create_trace(
        "brain.process",
        user_id=user_id,
        session_id=organization_id,
        metadata={"channel": channel, "channel_id": channel_id, "request_id": request_id},
    )

    thread_persona: str | None = None
    if thread_id and not persona_pin:
        try:
            thread_persona = await memory.get_thread_persona(
                db, organization_id=organization_id, thread_key=thread_id
            )
        except Exception:
            logger.debug("get_thread_persona failed for %s", thread_id, exc_info=True)

    effective_pin = persona_pin or thread_persona
    persona = route_persona(message, channel_id=channel_id, persona_pin=effective_pin)
    logger.info(
        "Routed to persona=%s (org=%s, user=%s, pinned=%s, thread_sticky=%s)",
        persona,
        organization_id,
        user_id,
        bool(persona_pin),
        bool(thread_persona),
    )
    persona_span = trace.span(
        name="route_persona",
        input={"message": message[:100], "persona_pin": persona_pin, "thread_id": thread_id},
    )
    persona_span.end(
        output={
            "persona": persona,
            "pinned": bool(persona_pin),
            "thread_sticky": bool(thread_persona),
        }
    )

    try:
        persona_spec = get_persona_spec(persona)
    except ValueError:
        persona_spec = None

    persona_instructions = await _load_persona_instructions(persona, redis_client)
    if persona_instructions:
        persona_section = f"## Persona Instructions\n{persona_instructions}"
    else:
        persona_section = ""

    tone_prefix = ""
    if persona_spec and persona_spec.tone_prefix:
        tone_prefix = f"## Voice\n{persona_spec.tone_prefix}"

    fatigue_ids = await memory.get_fatigue_ids(redis_client, organization_id)
    episodes = await memory.search_episodes(
        db,
        organization_id=organization_id,
        query=message,
        limit=5,
        fatigue_ids=fatigue_ids,
    )

    if episodes:
        recalled_ids = [e.id for e in episodes]
        await memory.mark_recalled(redis_client, organization_id, recalled_ids)
        memory_context = "\n\n".join(
            f"[{e.source} | {e.created_at.strftime('%Y-%m-%d')}] {e.summary}" for e in episodes
        )
    else:
        memory_context = (
            "(No relevant memories found yet. Use read_github_file to check "
            "docs/TASKS.md or docs/KNOWLEDGE.md for project context.)"
        )

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        org_name=org_name,
        persona=persona,
        tone_prefix=tone_prefix,
        persona_instructions=persona_section,
        memory_context=memory_context,
    )

    # Track I: scrub PII from the user's message BEFORE it reaches the
    # LLM. scrub_pii is already applied to memory storage, tool outputs,
    # and logs; this closes the last remaining path (the prompt itself).
    # Third-party providers (Anthropic, OpenAI, Google) never see raw
    # SSNs/EINs/phone/routing numbers regardless of persona.
    scrubbed_message = scrub_pii(message)
    scrubbed_thread_context: list[dict[str, str]] | None = None
    if thread_context:
        scrubbed_thread_context = [
            {**m, "content": scrub_pii(m.get("content", ""))} for m in thread_context
        ]

    messages: list[dict[str, str]] = []
    if scrubbed_thread_context:
        messages.extend(scrubbed_thread_context)
    messages.append({"role": "user", "content": scrubbed_message})

    cb = _get_circuit_breaker(redis_client)

    input_tokens_measured = count_tokens(message, model="gpt-4o-mini")

    # Track I: per-persona requests_per_minute. Enforced on top of the
    # global SlowAPI default so a legit IP can still be throttled when
    # it hammers a single expensive persona.
    if persona_spec is not None and persona_spec.requests_per_minute is not None:
        try:
            await persona_rate_limit.check_and_increment(
                redis_client,
                organization_id=organization_id,
                persona=persona,
                limit_per_minute=persona_spec.requests_per_minute,
            )
        except PersonaRateLimitExceeded as exc:
            logger.warning(
                "persona rate limit hit for %s org=%s: %d/%d, retry_after=%ds",
                persona,
                organization_id,
                exc.current,
                exc.limit,
                exc.retry_after,
            )
            trace.score(name="rate_limit_enforced", value=1.0)
            flush_traces()
            return {
                "response": (
                    f"The {persona} persona is at its rate limit "
                    f"({exc.limit}/min). Retry in {exc.retry_after}s."
                ),
                "persona": persona,
                "persona_spec": persona_spec.name,
                "model": "none",
                "provider": "none",
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "classification": {
                    "error": "rate_limited",
                    "retry_after": exc.retry_after,
                },
                "tool_calls": [],
                "constitutional_violations": [],
                "episode_id": None,
                "episode_uri": None,
                "error": "rate_limited",
            }

    # H3: enforce daily_cost_ceiling_usd BEFORE we spend a cent with the
    # provider. Fail fast with a structured error; don't silently proceed.
    if persona_spec is not None and persona_spec.daily_cost_ceiling_usd is not None:
        try:
            await cost_tracker.check_ceiling(
                redis_client,
                organization_id=organization_id,
                persona=persona,
                ceiling_usd=persona_spec.daily_cost_ceiling_usd,
            )
        except CostCeilingExceeded as exc:
            logger.warning(
                "cost ceiling hit for %s org=%s: $%.4f of $%.4f",
                persona,
                organization_id,
                exc.spent_usd,
                exc.ceiling_usd,
            )
            trace.score(name="cost_ceiling_enforced", value=1.0)
            flush_traces()
            return {
                "response": (
                    f"The {persona} persona has reached its daily spend cap "
                    f"(${exc.spent_usd:.2f} of ${exc.ceiling_usd:.2f}). "
                    "Try again tomorrow or raise the ceiling in the persona spec."
                ),
                "persona": persona,
                "persona_spec": persona_spec.name,
                "model": "none",
                "provider": "none",
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "classification": {"error": "cost_ceiling_exceeded"},
                "tool_calls": [],
                "constitutional_violations": [],
                "episode_id": None,
                "episode_uri": None,
                "error": "cost_ceiling_exceeded",
            }

    strategy_override = (strategy or "").strip().lower() or None
    if strategy_override not in (None, "auto", "classify_route", "extract_reason"):
        logger.warning(
            "Unknown chain strategy '%s' requested; falling back to auto",
            strategy_override,
        )
        strategy_override = None

    chain_strategy: Any
    if strategy_override == "extract_reason":
        chain_strategy = ExtractAndReason(cb)
        strategy_name = "extract_and_reason"
    elif strategy_override == "classify_route":
        chain_strategy = ClassifyAndRoute(cb)
        strategy_name = "classify_and_route"
    elif persona_spec is not None:
        tokens_threshold: int | None = None
        escalate_on_compliance = False
        mention_targets: list[str] = []
        for tag in persona_spec.escalate_if:
            if tag == "compliance" and persona_spec.compliance_flagged:
                escalate_on_compliance = True
            elif tag.startswith("tokens>"):
                with contextlib.suppress(ValueError):
                    tokens_threshold = int(tag.split(">", 1)[1])
            elif tag.startswith("mention:"):
                mention_targets.append(tag.split(":", 1)[1])
        chain_strategy = PersonaPinnedRoute(
            cb,
            model=persona_spec.default_model,
            escalation_model=persona_spec.escalation_model,
            escalate_on_compliance=escalate_on_compliance,
            escalate_on_tokens_over=tokens_threshold,
            escalate_on_mentions=mention_targets,
            input_tokens=input_tokens_measured,
            requires_tools=persona_spec.requires_tools,
            max_output_tokens=persona_spec.max_output_tokens,
        )
        strategy_name = "persona_pinned_route"
    else:
        chain_strategy = ClassifyAndRoute(cb)
        strategy_name = "classify_and_route"

    context = ChainContext(
        message=scrubbed_message,
        system_prompt=system_prompt,
        messages=messages,
        channel_id=channel_id,
        organization_id=organization_id,
    )

    llm_span = trace.span(name=strategy_name, input={"message": message[:200]})
    try:
        result: ChainResult = await chain_strategy.execute(context)
    except LLMUnavailableError as exc:
        logger.error(
            "All providers failed for persona=%s: %s/%s — %s",
            persona,
            exc.provider,
            exc.model,
            exc.reason,
        )
        llm_span.end(output={"error": "llm_unavailable", "provider": exc.provider})
        trace.score(name="llm_available", value=0.0)
        flush_traces()
        return {
            "response": (
                "Brain is temporarily unable to reach its model providers. "
                "Please retry shortly. (If this persists, check "
                "/admin/infrastructure for provider status.)"
            ),
            "persona": persona,
            "persona_spec": persona_spec.name if persona_spec else None,
            "model": exc.model,
            "provider": exc.provider,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost": 0.0,
            "classification": {"error": "llm_unavailable", "reason": exc.reason},
            "tool_calls": [],
            "constitutional_violations": [],
            "episode_id": None,
            "episode_uri": None,
            "error": "llm_unavailable",
        }
    llm_span.end(
        output={
            "model": result.model,
            "provider": result.provider,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "cost": result.cost,
            "tools_used": len(result.tool_calls),
        }
    )

    violations = _check_constitution(result.content)
    if violations:
        logger.warning(
            "Constitutional violations detected: %s",
            [v["principle_id"] for v in violations],
        )

    # H3: record successful spend against the daily counter so subsequent
    # requests this UTC-rolling-24h see the accumulated total.
    if persona_spec is not None and result.cost > 0:
        await cost_tracker.record_spend(
            redis_client,
            organization_id=organization_id,
            persona=persona,
            amount_usd=result.cost,
        )

    # H4: for compliance-flagged personas with a confidence_floor, stamp
    # metadata so downstream UIs (Studio) can surface a
    # "needs human review" badge. D7 will turn this into an actionable
    # review queue; today it's audit-trail only.
    episode_metadata: dict[str, object] = {}
    needs_human_review = bool(
        persona_spec
        and persona_spec.compliance_flagged
        and persona_spec.confidence_floor is not None
    )
    if needs_human_review:
        episode_metadata["needs_human_review"] = True
        episode_metadata["confidence_floor"] = persona_spec.confidence_floor

    if persona_pin:
        episode_metadata["persona_pin"] = persona_pin
        episode_metadata["pinned"] = True
    elif thread_persona:
        episode_metadata["thread_sticky"] = True

    episode = await memory.store_episode(
        db,
        organization_id=organization_id,
        source=f"brain:{channel or 'api'}",
        summary=(
            f"User: {scrub_pii(message[:200])}\n"
            f"Brain ({persona}): {scrub_pii(result.content[:200])}"
        ),
        full_context=scrub_pii(f"User: {message}\nBrain: {result.content}"),
        user_id=user_id,
        channel=channel,
        persona=persona,
        # Track C: prefer thread_id as source_ref so future messages in the
        # same thread can look up the sticky persona. request_id stays in
        # metadata for idempotency / debugging.
        source_ref=thread_id or request_id,
        model_used=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        metadata={**(episode_metadata or {}), "request_id": request_id}
        if request_id
        else episode_metadata or None,
    )

    # D4: stamp provenance on the response so downstream channels (Studio)
    # can link back to the source episode. Skip for trivial
    # duplicate/mock responses where content is empty.
    episode_uri = f"brain://episode/{episode.id}" if episode and episode.id else None
    stamped_content = result.content
    if episode_uri and result.content and "brain://episode/" not in result.content:
        stamped_content = f"{result.content}\n\n_source: {episode_uri}_"

    if result.classification:
        await memory.store_episode(
            db,
            organization_id=organization_id,
            source="model_router",
            summary=(
                f"Routed '{scrub_pii(message[:80])}' to {result.model} "
                f"via {result.provider} (tools={result.classification.get('tools_needed')}, "
                f"domain={result.classification.get('domain')}, cost=${result.cost:.4f})"
            ),
            full_context=scrub_pii(
                f"Classification: {result.classification}\n"
                f"Tool calls: {len(result.tool_calls)}\n"
                f"Violations: {violations}"
            ),
            user_id=user_id,
            channel=channel,
            persona="router",
            source_ref=request_id,
            model_used=result.model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
        )

    trace.update(
        output={"persona": persona, "model": result.model, "cost": result.cost},
        metadata={"violations": [v["principle_id"] for v in violations]},
    )
    if violations:
        trace.score(name="constitutional_safety", value=0.0)
    else:
        trace.score(name="constitutional_safety", value=1.0)
    flush_traces()

    return {
        "response": stamped_content,
        "persona": persona,
        "persona_spec": persona_spec.name if persona_spec else None,
        "persona_pinned": bool(persona_pin),
        "chain_strategy": strategy_name,
        "model": result.model,
        "provider": result.provider,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost": result.cost,
        "classification": result.classification,
        "tool_calls": result.tool_calls,
        "constitutional_violations": violations,
        "episode_id": episode.id if episode else None,
        "episode_uri": episode_uri,
        "needs_human_review": needs_human_review,
    }
