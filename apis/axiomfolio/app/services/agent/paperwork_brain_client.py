"""Track M.1 — Delegation client for TradingAgent ↔ Paperwork Brain.

Thin HTTP shim that replaces the hardcoded ``api.openai.com`` call inside
``TradingAgent.chat()`` with a call to
``POST {PAPERWORK_BRAIN_URL}/brain/process?persona_pin=trading``.

Why this is a separate module (and not inline in brain.py):
  * The file already clocks in at 2,800 lines. Any future FileFree or
    LaunchFree agent will reuse the same delegation pattern, so we want
    an importable client, not copy-pasted HTTP.
  * Making the call path easy to mock in tests. Injecting a fake client
    into ``TradingAgent`` is cleaner than patching ``aiohttp.ClientSession``.
  * Keeping BYOK logic in ``brain.py::_resolve_llm_target`` unchanged —
    Track M preserves that code path 100% for paid-tier self-directed
    users. We only delegate when the platform key is in play.

What the client returns (shape mirrors Brain's ``/brain/process`` response
so TradingAgent barely has to adapt):

    {
        "response": str,          # final assistant text
        "tool_calls": list[dict], # OpenAI-shape tool calls, if any
        "episode_id": int | None, # for provenance stamp on AgentAction
        "episode_uri": str | None,
        "model": str,             # the actual model Brain's router picked
        "cost_usd": float,
        "error": str | None,
    }

Failure modes fail CLOSED: we raise ``PaperworkBrainUnavailable`` so
callers can fall through to direct-OpenAI. We never silently return
mock content (enforces the no-silent-fallback rule from
.cursor/rules/no-silent-fallback.mdc).

medallion: ops
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)


class PaperworkBrainUnavailable(Exception):
    """Raised when Brain returns an error or is unreachable.

    Callers MUST handle this (typically by falling back to direct-LLM).
    """

    def __init__(self, reason: str, status: Optional[int] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class PaperworkBrainClient:
    """Minimal client for Paperwork Brain's ``/brain/process`` endpoint."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or settings.PAPERWORK_BRAIN_URL or "").rstrip("/")
        self.api_key = api_key or settings.BRAIN_API_KEY or ""
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.PAPERWORK_BRAIN_TIMEOUT_SECONDS
        )

    @property
    def enabled(self) -> bool:
        return bool(
            settings.AXIOMFOLIO_USE_PAPERWORK_BRAIN
            and self.base_url
            and self.api_key
        )

    async def process(
        self,
        *,
        message: str,
        session_id: str,
        user_id: Optional[int],
        organization_id: Optional[str] = None,
        thread_context: Optional[list[dict[str, str]]] = None,
        surface: str = "axiomfolio-agent",
        strategy: str = "classify_route",
    ) -> dict[str, Any]:
        """Send one chat turn through Brain's trading persona.

        ``thread_context`` is the OpenAI-shape conversation history
        (role/content/tool_calls). Brain's PII scrubber runs on both
        message and thread_context, so this data is sanitised upstream of
        any LLM call.
        """
        if not self.base_url:
            raise PaperworkBrainUnavailable("PAPERWORK_BRAIN_URL not configured")
        if not self.api_key:
            raise PaperworkBrainUnavailable("BRAIN_API_KEY not configured")

        payload: dict[str, Any] = {
            "message": message,
            "thread_id": f"axiomfolio:{session_id}",
            "organization_id": organization_id or "paperwork-labs",
            "user_id": str(user_id) if user_id is not None else None,
            "persona_pin": "trading",
            "strategy": strategy,
            "surface": surface,
        }
        if thread_context:
            payload["thread_context"] = thread_context

        headers = {
            "Content-Type": "application/json",
            "X-Brain-Api-Key": self.api_key,
        }

        url = f"{self.base_url}/brain/process"
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    body: Any = None
                    try:
                        body = await resp.json()
                    except Exception:
                        body = await resp.text()
                    if resp.status >= 500:
                        raise PaperworkBrainUnavailable(
                            f"brain 5xx: {resp.status}", status=resp.status
                        )
                    if resp.status == 429:
                        raise PaperworkBrainUnavailable(
                            "brain rate-limited", status=429
                        )
                    if resp.status >= 400:
                        raise PaperworkBrainUnavailable(
                            f"brain {resp.status}: {str(body)[:200]}",
                            status=resp.status,
                        )
                    if not isinstance(body, dict):
                        raise PaperworkBrainUnavailable("brain returned non-JSON")
                    if body.get("error"):
                        # Structured Brain error (cost ceiling, rate limit, etc.)
                        raise PaperworkBrainUnavailable(
                            f"brain error: {body['error']}", status=resp.status
                        )
                    return {
                        "response": body.get("response") or "",
                        "tool_calls": body.get("tool_calls") or [],
                        "episode_id": body.get("episode_id"),
                        "episode_uri": body.get("episode_uri"),
                        "model": body.get("model") or "unknown",
                        "cost_usd": float(body.get("cost") or 0.0),
                        "persona": body.get("persona") or "trading",
                        "error": None,
                    }
        except aiohttp.ClientError as exc:
            logger.warning("Paperwork Brain unreachable: %s", exc)
            raise PaperworkBrainUnavailable(f"network: {exc}") from exc
        except TimeoutError as exc:
            logger.warning("Paperwork Brain timed out after %ss", self.timeout_seconds)
            raise PaperworkBrainUnavailable("timeout") from exc
