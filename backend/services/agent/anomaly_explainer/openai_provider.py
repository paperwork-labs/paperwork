"""
Sync OpenAI implementation of :class:`LLMProvider`.

Why a separate, sync adapter instead of reusing ``AgentBrain._call_llm``?

* ``AgentBrain._call_llm`` is async (aiohttp) and tied to the chat / tool
  loop. It also injects all of the agent's tools into every call, which
  is the wrong shape for a one-shot "explain this anomaly" request.
* AutoOps callers (``auto_remediate_health``, admin routes) are sync. We
  do not want to spin up an event loop on every Celery beat tick to
  bridge sync->async->sync just to call one POST.
* This module deliberately uses ``requests`` (already pinned) and
  exposes nothing but :class:`OpenAIChatProvider` so the surface area
  stays minimal and reviewable.

Failure mode contract:

* Most HTTP errors, timeouts, missing API key, or non-OK statuses raise
  :class:`LLMProviderError`. After max 429 retries, raises
  :class:`LLMProviderRateLimitedError` so callers can skip without treating
  the task as a generic LLM failure. The explainer catches both and falls
  back to its deterministic runbook where appropriate.

JSON output mode:

* OpenAI's ``response_format={"type": "json_object"}`` is enabled so the
  model is forced to return a single JSON object. The explainer's
  schema-validation gate is the second line of defence.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:  # pragma: no cover -- requests is pinned, but be defensive
    requests = None  # type: ignore[assignment]

from .provider import LLMProviderError, LLMProviderRateLimitedError

DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 60
# Transient 429s: bounded retries with backoff; see LLMProviderRateLimitedError.
_MAX_429_ATTEMPTS = 4


class OpenAIChatProvider:
    """One-shot ``LLMProvider`` backed by OpenAI Chat Completions.

    Args:
        api_key: OpenAI key. Falls back to ``OPENAI_API_KEY`` env var. If
            both are missing, :meth:`complete_json` raises immediately
            instead of attempting a doomed HTTP call.
        model: Model slug; ``gpt-4o-mini`` is the default for cost.
        api_url: Override for non-prod / proxied deployments.
        timeout_seconds: Per-request timeout. Soft-capped at 120s so a
            stuck call can't hold a Celery worker forever.
        session: Optional injected ``requests.Session`` for connection
            pooling and -- crucially -- for tests that want to swap in a
            fake session without monkey-patching the global ``requests``.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        api_url: str = OPENAI_API_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        session: Any = None,
    ) -> None:
        if requests is None and session is None:
            raise LLMProviderError(
                "the 'requests' package is not installed; cannot use OpenAIChatProvider"
            )
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        self._api_url = api_url
        self._timeout = max(1, min(120, int(timeout_seconds)))
        self._session = session
        self.name = f"openai:{model}"

    @property
    def is_configured(self) -> bool:
        """``True`` if an API key is present. Lets callers skip without raising."""
        return bool(self._api_key)

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> str:
        if not self._api_key:
            raise LLMProviderError("OPENAI_API_KEY is not set")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            # Force JSON-object output so the explainer never has to peel
            # markdown fences or stray prose.
            "response_format": {"type": "json_object"},
        }

        session = self._session or requests
        resp: Any = None
        for attempt in range(_MAX_429_ATTEMPTS):
            try:
                resp = session.post(
                    self._api_url,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout,
                )
            except Exception as e:  # network / DNS / SSL / requests adapter
                raise LLMProviderError(f"openai network error: {e}") from e

            status = getattr(resp, "status_code", None)
            if status == 200:
                break
            if status == 429 and attempt < _MAX_429_ATTEMPTS - 1:
                retry_s = 1
                try:
                    ra = resp.headers.get("Retry-After")
                    if ra is not None:
                        retry_s = int(ra)
                except (TypeError, ValueError):
                    retry_s = 1
                # Cap backoff so explain_anomaly (soft_time_limit=30) can finish
                # without Celery killing the task while sleeping on large Retry-After.
                time.sleep(max(1, min(8, retry_s)))
                continue
            if status == 429:
                raise LLMProviderRateLimitedError(
                    "openai rate limited after max retries (429)"
                )
            body = ""
            try:
                body = resp.text[:500]
            except Exception:  # noqa: BLE001
                body = ""
            raise LLMProviderError(f"openai http {status}: {body}")

        if resp is None or getattr(resp, "status_code", None) != 200:
            raise LLMProviderError("openai: unexpected end of request loop")

        try:
            data = resp.json()
        except Exception as e:
            raise LLMProviderError(f"openai response was not JSON: {e}") from e

        content = self._extract_content(data)
        if not content:
            raise LLMProviderError("openai response had no choices[0].message.content")
        return content

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> Optional[str]:
        """Pull ``choices[0].message.content`` out, defensively."""
        try:
            choices = data.get("choices") or []
            if not choices:
                return None
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            return None
        except Exception:  # noqa: BLE001
            return None
