"""OpenAI chat-completions adapter for plain-text portfolio narratives.

medallion: gold
"""

from __future__ import annotations

import hashlib
import os
from decimal import Decimal
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

from app.services.gold.narrative.provider import NarrativeProviderError, NarrativeResult

DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 60

# USD per 1M tokens (approximate list prices; adjust when OpenAI pricing changes).
_PRICE_PER_1M_INPUT = Decimal("0.15")
_PRICE_PER_1M_OUTPUT = Decimal("0.60")


class OpenAIChatProvider:
    """Minimal sync OpenAI client for one-shot narrative text."""

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
            raise NarrativeProviderError(
                "the 'requests' package is not installed; cannot use OpenAIChatProvider"
            )
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        self._api_url = api_url
        self._timeout = max(1, min(120, int(timeout_seconds)))
        self._session = session

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def generate(self, prompt: str, *, max_tokens: int = 400) -> NarrativeResult:
        if not self._api_key:
            raise NarrativeProviderError("OPENAI_API_KEY is not set")
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a concise financial editor. Follow the user's instructions "
                        "exactly. Output plain prose only (markdown emphasis allowed)."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": int(max_tokens),
        }
        try:
            sess = self._session or requests
            resp = sess.post(
                self._api_url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except Exception as e:
            raise NarrativeProviderError(f"openai network error: {e}") from e

        status = getattr(resp, "status_code", None)
        if status != 200:
            body = ""
            try:
                body = resp.text[:500]
            except Exception:
                body = ""
            raise NarrativeProviderError(f"openai http {status}: {body}")

        try:
            data = resp.json()
        except Exception as e:
            raise NarrativeProviderError(f"openai response was not JSON: {e}") from e

        content = _extract_content(data)
        if not content or not str(content).strip():
            raise NarrativeProviderError("openai response had no assistant content")

        usage = data.get("usage") or {}
        try:
            pt = int(usage.get("prompt_tokens") or 0)
            ct = int(usage.get("completion_tokens") or 0)
        except (TypeError, ValueError):
            pt, ct = 0, 0
        tokens_used = pt + ct if (pt or ct) else None
        cost: Optional[Decimal] = None
        if tokens_used:
            cost = (
                Decimal(pt) * _PRICE_PER_1M_INPUT / Decimal(1_000_000)
                + Decimal(ct) * _PRICE_PER_1M_OUTPUT / Decimal(1_000_000)
            ).quantize(Decimal("0.0001"))

        return NarrativeResult(
            text=str(content).strip(),
            provider="openai",
            model=self._model,
            tokens_used=tokens_used,
            cost_usd=cost,
            is_fallback=False,
            prompt_hash=prompt_hash,
        )


def _extract_content(data: Dict[str, Any]) -> Optional[str]:
    try:
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        return None
    except Exception:
        return None
