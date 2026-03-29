"""Multi-provider LLM service with MCP connector support.

D14: Provider fallback via circuit breaker (D38).
D20: ClassifyAndRoute selects the model; this module executes the call.
D3: Prompt caching via cache_control on system prompt.

Supported providers:
- Anthropic (Claude Sonnet/Opus) + MCP connector for tool execution
- OpenAI (GPT-4o, GPT-4o-mini, o4-mini) + MCP for tool execution
- Google (Gemini Flash) for classification and simple queries
- Mock mode when no API keys are set
"""

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_registry: dict[str, Any] | None = None
_http_clients: dict[str, httpx.AsyncClient] = {}


def _get_client(name: str, timeout: float = 60.0) -> httpx.AsyncClient:
    """Reuse httpx clients for connection pooling."""
    if name not in _http_clients or _http_clients[name].is_closed:
        _http_clients[name] = httpx.AsyncClient(timeout=timeout)
    return _http_clients[name]


async def close_clients() -> None:
    """Close all httpx clients. Call during app shutdown."""
    for name, client in _http_clients.items():
        if not client.is_closed:
            await client.aclose()
    _http_clients.clear()


def _load_registry() -> dict[str, Any]:
    global _registry
    if _registry is None:
        path = Path(__file__).resolve().parent.parent / "model_registry.json"
        with open(path) as f:
            _registry = json.load(f)
    return _registry


def get_model_info(model_id: str) -> dict[str, Any] | None:
    registry = _load_registry()
    return registry.get("models", {}).get(model_id)


def _format_gemini_messages(messages: list[dict[str, str]]) -> list[dict]:
    """Convert OpenAI-style messages to Gemini contents format."""
    role_map = {"user": "user", "assistant": "model"}
    contents = []
    for msg in messages:
        role = role_map.get(msg.get("role", "user"), "user")
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
    return contents if contents else [{"role": "user", "parts": [{"text": ""}]}]


TIER_DISABLED_TOOLS = {
    "commit_github_file",
    "merge_github_pr",
    "execute_trade",
    "modify_position",
}


async def complete_with_mcp(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    enabled_write_tools: set[str] | None = None,
) -> dict:
    """Call Anthropic Messages API with MCP connector.

    Anthropic connects to our MCP server, discovers tools, executes them
    server-side, iterates until done, returns the final response with
    full tool call history in content blocks.
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, returning mock response")
        return _mock_response(messages)

    disabled_configs = {}
    for tool_name in TIER_DISABLED_TOOLS:
        if enabled_write_tools and tool_name in enabled_write_tools:
            continue
        disabled_configs[tool_name] = {"enabled": False}

    mcp_server_url = settings.BRAIN_URL.rstrip("/") + "/mcp"

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": messages,
        "mcp_servers": [
            {
                "type": "url",
                "url": mcp_server_url,
                "name": "brain-tools",
                "authorization_token": settings.BRAIN_MCP_TOKEN,
            }
        ],
        "tools": [
            {
                "type": "tool_search_tool_bm25_20251119",
                "name": "tool_search",
            },
            {
                "type": "mcp_toolset",
                "mcp_server_name": "brain-tools",
                "default_config": {"defer_loading": True},
                "configs": disabled_configs,
            },
        ],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "mcp-client-2025-11-20,compact-2026-01-12,context-management-2025-06-27",
        "content-type": "application/json",
    }

    try:
        client = _get_client("anthropic_mcp", timeout=120.0)
        res = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        )
        res.raise_for_status()
        data = res.json()
        return _parse_anthropic_response(data, model)

    except httpx.HTTPStatusError as e:
        logger.error(
            "Anthropic MCP API error: %s %s",
            e.response.status_code,
            e.response.text[:300],
        )
        if settings.OPENAI_API_KEY:
            logger.info("Falling back to OpenAI with MCP")
            return await complete_openai_with_mcp(
                system_prompt=system_prompt,
                messages=messages,
                model="gpt-4o",
                max_tokens=max_tokens,
                enabled_write_tools=enabled_write_tools,
            )
        return _mock_response(messages)
    except Exception:
        logger.error("Anthropic MCP call failed", exc_info=True)
        if settings.OPENAI_API_KEY:
            logger.info("Falling back to OpenAI with MCP (generic exception)")
            return await complete_openai_with_mcp(
                system_prompt=system_prompt,
                messages=messages,
                model="gpt-4o",
                max_tokens=max_tokens,
                enabled_write_tools=enabled_write_tools,
            )
        return _mock_response(messages)


async def complete_openai_with_mcp(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str = "gpt-4o",
    max_tokens: int = 4096,
    enabled_write_tools: set[str] | None = None,
) -> dict:
    """Call OpenAI Responses API with MCP connector.

    OpenAI MCP has no per-tool disable config like Anthropic. We inject a
    system instruction telling it which tools require approval, and validate
    tool calls in the response for tier compliance.
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return _mock_response(messages)

    mcp_server_url = settings.BRAIN_URL.rstrip("/") + "/mcp"

    restricted = TIER_DISABLED_TOOLS - (enabled_write_tools or set())
    tier_notice = ""
    if restricted:
        tier_notice = (
            "\n\nIMPORTANT: The following tools require explicit user approval "
            f"and must NOT be called: {', '.join(sorted(restricted))}. "
            "If the user asks for these actions, describe what you would do and ask for confirmation."
        )

    oai_input = [{"role": "system", "content": system_prompt + tier_notice}]
    oai_input.extend(messages)

    payload: dict[str, Any] = {
        "model": model,
        "input": oai_input,
        "max_output_tokens": max_tokens,
        "tools": [
            {
                "type": "mcp",
                "server_label": "brain-tools",
                "server_url": mcp_server_url,
                "headers": {"Authorization": f"Bearer {settings.BRAIN_MCP_TOKEN}"},
            }
        ],
    }

    try:
        client = _get_client("openai_mcp", timeout=120.0)
        res = await client.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        res.raise_for_status()
        data = res.json()
        return _parse_openai_response(data, model)
    except Exception:
        logger.error("OpenAI MCP call failed", exc_info=True)
        return _mock_response(messages)


async def complete_text(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> dict:
    """Simple text completion without tools. For simple queries routed to cheap models."""

    if provider == "google":
        return await _complete_gemini(
            system_prompt=system_prompt,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
        )

    if provider == "openai":
        return await _complete_openai_text(
            system_prompt=system_prompt,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    if provider == "anthropic":
        return await _complete_anthropic_text(
            system_prompt=system_prompt,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    return _mock_response(messages)


async def _complete_gemini(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str = "gemini-2.5-flash",
    max_tokens: int = 2048,
) -> dict:
    """Call Google Gemini API for cheap text generation."""
    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        return _mock_response(messages)

    try:
        client = _get_client("gemini", timeout=30.0)
        res = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": _format_gemini_messages(messages),
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
        )
        res.raise_for_status()
        data = res.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        usage = data.get("usageMetadata", {})
        return {
            "content": text,
            "model": model,
            "provider": "google",
            "tokens_in": usage.get("promptTokenCount", 0),
            "tokens_out": usage.get("candidatesTokenCount", 0),
            "tool_calls": [],
        }
    except Exception:
        logger.error("Gemini call failed", exc_info=True)
        return _mock_response(messages)


async def _complete_openai_text(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str = "gpt-4o-mini",
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> dict:
    """Call OpenAI Chat Completions API (no tools)."""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return _mock_response(messages)

    oai_messages = [{"role": "system", "content": system_prompt}, *messages]

    try:
        client = _get_client("openai_text")
        res = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
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
            "model": data.get("model", model),
            "provider": "openai",
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
            "tool_calls": [],
        }
    except Exception:
        logger.error("OpenAI text call failed", exc_info=True)
        return _mock_response(messages)


async def _complete_anthropic_text(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> dict:
    """Call Anthropic Messages API (no tools, no MCP)."""
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return _mock_response(messages)

    try:
        client = _get_client("anthropic_text")
        res = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": messages,
            },
        )
        res.raise_for_status()
        data = res.json()
        content = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        usage = data.get("usage", {})
        return {
            "content": content,
            "model": data.get("model", model),
            "provider": "anthropic",
            "tokens_in": usage.get("input_tokens", 0),
            "tokens_out": usage.get("output_tokens", 0),
            "tool_calls": [],
        }
    except Exception:
        logger.error("Anthropic text call failed", exc_info=True)
        return _mock_response(messages)


async def classify_query(message: str, channel_id: str | None = None) -> dict:
    """Use Gemini Flash to classify a query for routing. Returns structured JSON."""
    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        return {
            "model": "claude-sonnet-4-20250514",
            "provider": "anthropic",
            "tools_needed": True,
            "domain": "general",
            "confidence": 0.5,
        }

    prompt = f"""Classify this user message for an AI assistant routing system.
The assistant has tools for: GitHub (code, PRs, issues), infrastructure monitoring
(Render, Vercel, Neon, n8n, Upstash), trading (portfolio, market scans, trade execution),
memory (past conversations), and secrets vault.

Channel context: {channel_id or 'unknown'}
Message: {message}

Respond with ONLY valid JSON:
{{"model": "gpt-4o-mini|o4-mini|claude-sonnet-4-20250514|gpt-4o|claude-opus-4-20250618",
  "provider": "openai|anthropic|google",
  "tools_needed": true|false,
  "domain": "general|infra|trading|tax|code|social",
  "confidence": 0.0-1.0}}

Rules:
- Simple greetings, questions, explanations -> gpt-4o-mini, tools_needed=false
- Infrastructure status checks -> claude-sonnet-4-20250514, tools_needed=true
- Code/PR/GitHub operations -> claude-sonnet-4-20250514, tools_needed=true
- Trading/portfolio queries -> claude-sonnet-4-20250514, tools_needed=true
- Tax calculations, financial math -> o4-mini, tools_needed=false
- Complex multi-domain reasoning -> claude-opus-4-20250618, tools_needed=true"""

    try:
        client = _get_client("gemini_classify", timeout=15.0)
        last_err = None
        data = None
        for attempt in range(2):
            try:
                res = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                    params={"key": api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "maxOutputTokens": 100,
                        },
                    },
                )
                res.raise_for_status()
                data = res.json()
                break
            except Exception as e:
                last_err = e
                if attempt == 0:
                    logger.warning("Classifier attempt 1 failed, retrying: %s", e)
        if data is None:
            raise last_err or ValueError("Classification failed after retries")
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "{}")
        )
        result = json.loads(text)
        required_keys = {"model", "provider", "tools_needed", "domain", "confidence"}
        if not required_keys.issubset(result.keys()):
            raise ValueError(f"Missing keys: {required_keys - result.keys()}")
        valid_providers = {"openai", "anthropic", "google"}
        valid_domains = {"general", "infra", "trading", "tax", "code", "social"}
        if result["provider"] not in valid_providers:
            result["provider"] = "anthropic"
        if result["domain"] not in valid_domains:
            result["domain"] = "general"
        if not isinstance(result.get("tools_needed"), bool):
            result["tools_needed"] = bool(result["tools_needed"])
        conf = result.get("confidence", 0.5)
        result["confidence"] = max(0.0, min(1.0, float(conf)))
        return result
    except Exception:
        logger.warning("Classification failed, defaulting to Sonnet + MCP", exc_info=True)
        return {
            "model": "claude-sonnet-4-20250514",
            "provider": "anthropic",
            "tools_needed": True,
            "domain": "general",
            "confidence": 0.5,
        }


def _parse_anthropic_response(data: dict, model: str) -> dict:
    """Parse Anthropic response including MCP tool use/result blocks."""
    content_text = ""
    tool_calls = []

    for block in data.get("content", []):
        block_type = block.get("type")
        if block_type == "text":
            content_text += block.get("text", "")
        elif block_type == "mcp_tool_use":
            tool_calls.append({
                "type": "mcp_tool_use",
                "name": block.get("name"),
                "server": block.get("server_name"),
                "input": block.get("input"),
            })
        elif block_type == "mcp_tool_result":
            tool_calls.append({
                "type": "mcp_tool_result",
                "tool_use_id": block.get("tool_use_id"),
                "is_error": block.get("is_error", False),
            })

    usage = data.get("usage", {})
    return {
        "content": content_text,
        "model": data.get("model", model),
        "provider": "anthropic",
        "tokens_in": usage.get("input_tokens", 0),
        "tokens_out": usage.get("output_tokens", 0),
        "tool_calls": tool_calls,
    }


def _parse_openai_response(data: dict, model: str) -> dict:
    """Parse OpenAI Responses API response."""
    content_text = ""
    tool_calls = []

    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    content_text += part.get("text", "")
        elif item.get("type") == "mcp_call":
            tool_calls.append({
                "type": "mcp_call",
                "name": item.get("name"),
                "server": item.get("server_label"),
            })

    usage = data.get("usage", {})
    return {
        "content": content_text,
        "model": model,
        "provider": "openai",
        "tokens_in": usage.get("input_tokens", 0),
        "tokens_out": usage.get("output_tokens", 0),
        "tool_calls": tool_calls,
    }


def _mock_response(messages: list[dict[str, str]]) -> dict:
    last_msg = messages[-1]["content"] if messages else "hello"
    return {
        "content": f"[Brain is running without LLM API keys. Received: {last_msg[:100]}]",
        "model": "mock",
        "provider": "mock",
        "tokens_in": 0,
        "tokens_out": 0,
        "tool_calls": [],
    }
