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
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import idempotency, memory
from app.services.observability import create_trace, flush as flush_traces
from app.services.pii import scrub_pii
from app.services.personas import route_persona
from app.services.router import (
    ChainContext,
    ChainResult,
    CircuitBreaker,
    ClassifyAndRoute,
)

logger = logging.getLogger(__name__)

PERSONA_MDC_PREFIX = ".cursor/rules/"
PERSONA_CACHE_TTL = 3600

SYSTEM_PROMPT_TEMPLATE = """You are the Brain for {org_name} — an intelligent assistant.
You are operating as the {persona} persona.

{persona_instructions}

## Your Memory (retrieved context)
{memory_context}

## Rules
- Be concise and actionable. Lead with the answer.
- Use your memory to provide personalized, context-aware responses.
- If you don't have enough context, use tools (read_github_file, search_github_code) to find answers.
- Never expose raw PII (SSNs, passwords, API keys) in your responses.
- If asked about something in your memory, cite it naturally.
- For project status, task progress, or "what to work on" questions, use read_github_file to read docs/TASKS.md.
- When using tools, prefer search_memory first for context before calling external tools.
"""


async def _load_persona_instructions(persona: str, redis_client: Any) -> str:
    """D13: Load persona .mdc from cache or GitHub. Returns instructions or empty string."""
    cache_key = f"persona_mdc:{persona}"

    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return cached if isinstance(cached, str) else cached.decode("utf-8")
        except Exception:
            logger.debug("Redis persona cache miss/error for %s", persona)

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
            violations.append({
                "principle_id": pid,
                "name": principle.get("name", ""),
                "severity": principle.get("severity", "medium"),
            })

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
    if _API_KEY_PATTERNS.search(text):
        return True
    return False


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
) -> dict:
    """Main agent loop entry point."""

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

    persona = route_persona(message, channel_id=channel_id)
    logger.info("Routed to persona=%s (org=%s, user=%s)", persona, organization_id, user_id)
    persona_span = trace.span(name="route_persona", input={"message": message[:100]})
    persona_span.end(output={"persona": persona})

    persona_instructions = await _load_persona_instructions(persona, redis_client)
    if persona_instructions:
        persona_section = f"## Persona Instructions\n{persona_instructions}"
    else:
        persona_section = ""

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
        memory_context = "(No relevant memories found yet. Use read_github_file to check docs/TASKS.md or docs/KNOWLEDGE.md for project context.)"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        org_name=org_name,
        persona=persona,
        persona_instructions=persona_section,
        memory_context=memory_context,
    )

    messages: list[dict[str, str]] = []
    if thread_context:
        messages.extend(thread_context)
    messages.append({"role": "user", "content": message})

    cb = _get_circuit_breaker(redis_client)
    strategy = ClassifyAndRoute(cb)
    context = ChainContext(
        message=message,
        system_prompt=system_prompt,
        messages=messages,
        channel_id=channel_id,
        organization_id=organization_id,
    )

    llm_span = trace.span(name="classify_and_route", input={"message": message[:200]})
    result: ChainResult = await strategy.execute(context)
    llm_span.end(output={
        "model": result.model,
        "provider": result.provider,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost": result.cost,
        "tools_used": len(result.tool_calls),
    })

    violations = _check_constitution(result.content)
    if violations:
        logger.warning(
            "Constitutional violations detected: %s",
            [v["principle_id"] for v in violations],
        )

    await memory.store_episode(
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
        source_ref=request_id,
        model_used=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )

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
        "response": result.content,
        "persona": persona,
        "model": result.model,
        "provider": result.provider,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost": result.cost,
        "classification": result.classification,
        "tool_calls": result.tool_calls,
        "constitutional_violations": violations,
    }
