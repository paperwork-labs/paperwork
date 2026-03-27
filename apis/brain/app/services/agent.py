"""P11.2: Agent loop — the core intelligence pipeline.

Phase 1 (single-pass): receives a message, retrieves memory, calls LLM, stores episode.
Phase 2 will add D2 iterative tool dispatch (configurable max, default 5, ceiling 10).

D10: Request idempotency via Redis.
D14: Model fallback chains (Anthropic -> OpenAI -> mock).
D15: Memory fatigue on recalled episodes.

Pipeline per request:
1. Check idempotency (D10)
2. Route persona
3. Retrieve relevant episodes (hybrid FTS + recency search)
4. Assemble system prompt + context
5. LLM call
6. Store interaction as episode
7. Return response
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import idempotency, llm, memory
from app.services.personas import route_persona
from app.services.pii import scrub_pii

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are the Brain for {org_name} — an intelligent assistant.
You are operating as the {persona} persona.

## Your Memory (retrieved context)
{memory_context}

## Rules
- Be concise and actionable. Lead with the answer.
- Use your memory to provide personalized, context-aware responses.
- If you don't have enough context, say so honestly.
- Never expose raw PII (SSNs, passwords, API keys) in your responses.
- If asked about something in your memory, cite it naturally.
"""


async def process(
    db: AsyncSession,
    redis_client,
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
    """Main agent loop entry point. Returns {response, persona, model, tokens_in, tokens_out}."""

    is_duplicate = await idempotency.check_and_set(redis_client, request_id, organization_id)
    if is_duplicate:
        logger.info("Duplicate request %s, skipping", request_id)
        return {
            "response": "[Duplicate request — already processed]",
            "persona": "system",
            "model": "none",
            "tokens_in": 0,
            "tokens_out": 0,
        }

    persona = route_persona(message, channel_id=channel_id)
    logger.info("Routed to persona=%s (org=%s, user=%s)", persona, organization_id, user_id)

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
        memory_context = "(No relevant memories found yet.)"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        org_name=org_name,
        persona=persona,
        memory_context=memory_context,
    )

    messages = []
    if thread_context:
        messages.extend(thread_context)
    messages.append({"role": "user", "content": message})

    result = await llm.complete(
        system_prompt=system_prompt,
        messages=messages,
    )

    await memory.store_episode(
        db,
        organization_id=organization_id,
        source=f"brain:{channel or 'api'}",
        summary=(
            f"User: {scrub_pii(message[:200])}\n"
            f"Brain ({persona}): {scrub_pii(result['content'][:200])}"
        ),
        full_context=scrub_pii(f"User: {message}\nBrain: {result['content']}"),
        user_id=user_id,
        channel=channel,
        persona=persona,
        source_ref=request_id,
        model_used=result["model"],
        tokens_in=result["tokens_in"],
        tokens_out=result["tokens_out"],
    )

    return {
        "response": result["content"],
        "persona": persona,
        "model": result["model"],
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
    }
