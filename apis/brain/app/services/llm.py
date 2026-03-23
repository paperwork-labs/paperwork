"""LLM service — D14 fallback chains. Opus -> Sonnet -> GPT-4o -> basic mode.
P1: single model call (Sonnet primary for cost). Fallback chains in P2."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def complete(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> dict:
    """Call Anthropic Messages API. Returns {content, model, tokens_in, tokens_out}."""
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, returning mock response")
        return _mock_response(messages)

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            res.raise_for_status()
            data = res.json()

            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")

            return {
                "content": content,
                "model": data.get("model", model),
                "tokens_in": data.get("usage", {}).get("input_tokens", 0),
                "tokens_out": data.get("usage", {}).get("output_tokens", 0),
            }
    except httpx.HTTPStatusError as e:
        logger.error("Anthropic API error: %s %s", e.response.status_code, e.response.text[:200])
        if settings.OPENAI_API_KEY:
            logger.info("Falling back to OpenAI")
            return await _openai_fallback(system_prompt, messages, max_tokens, temperature)
        return _mock_response(messages)
    except Exception:
        logger.error("LLM call failed", exc_info=True)
        return _mock_response(messages)


async def _openai_fallback(
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> dict:
    """D14 fallback: OpenAI GPT-4o."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            oai_messages = [{"role": "system", "content": system_prompt}] + messages
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o",
                    "messages": oai_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            res.raise_for_status()
            data = res.json()
            choice = data["choices"][0]["message"]
            usage = data.get("usage", {})
            return {
                "content": choice.get("content", ""),
                "model": data.get("model", "gpt-4o"),
                "tokens_in": usage.get("prompt_tokens", 0),
                "tokens_out": usage.get("completion_tokens", 0),
            }
    except Exception:
        logger.error("OpenAI fallback failed", exc_info=True)
        return _mock_response(messages)


def _mock_response(messages: list[dict[str, str]]) -> dict:
    last_msg = messages[-1]["content"] if messages else "hello"
    return {
        "content": f"[Brain is running without LLM API keys. Received: {last_msg[:100]}]",
        "model": "mock",
        "tokens_in": 0,
        "tokens_out": 0,
    }
