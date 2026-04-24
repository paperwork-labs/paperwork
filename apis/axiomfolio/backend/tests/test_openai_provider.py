"""
Tests for the sync OpenAI implementation of LLMProvider.

We do not hit the network. A small ``_FakeSession`` stands in for
``requests`` and we exercise:

* Happy path -> returns the JSON content string
* Missing API key -> raises LLMProviderError
* Non-200 HTTP -> raises LLMProviderError with body excerpt
* Non-JSON body -> raises
* Empty / shapeless choices -> raises
* Network exceptions -> wrapped in LLMProviderError
* End-to-end with the AnomalyExplainer -> happy path explanation
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import pytest

from backend.services.agent.anomaly_explainer import (
    Anomaly,
    AnomalyCategory,
    AnomalyExplainer,
    AnomalySeverity,
    LLMProviderError,
)
from backend.services.agent.anomaly_explainer.provider import (
    LLMProviderRateLimitedError,
)
from backend.services.agent.anomaly_explainer.openai_provider import (
    DEFAULT_MODEL,
    OPENAI_API_URL,
    OpenAIChatProvider,
)


# ---------------------------------------------------------------------------
# Fake session: matches the requests.post(...) signature we use.
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: Optional[Dict[str, Any]] = None,
                 text: str = "", json_raises: bool = False,
                 headers: Optional[Dict[str, str]] = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload or {})
        self._json_raises = json_raises
        self.headers = headers or {}

    def json(self) -> Dict[str, Any]:
        if self._json_raises:
            raise ValueError("not json")
        return self._payload or {}


class _FakeSession:
    def __init__(self, response: _FakeResponse, raise_on_post: Optional[Exception] = None):
        self.response = response
        self.raise_on_post = raise_on_post
        self.last_call: Optional[Dict[str, Any]] = None

    def post(self, url, *, headers, json, timeout):  # noqa: A002 -- shadowing 'json' is the requests signature
        if self.raise_on_post:
            raise self.raise_on_post
        self.last_call = {
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        }
        return self.response


def _ok_response(content: str) -> _FakeResponse:
    return _FakeResponse(
        200,
        {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ]
        },
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_defaults_use_env_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        provider = OpenAIChatProvider()
        assert provider.is_configured is True
        assert provider.name == f"openai:{DEFAULT_MODEL}"

    def test_explicit_key_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        provider = OpenAIChatProvider(api_key="sk-explicit")
        assert provider._api_key == "sk-explicit"

    def test_missing_key_marks_unconfigured(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIChatProvider()
        assert provider.is_configured is False

    def test_timeout_clamped(self):
        slow = OpenAIChatProvider(api_key="x", timeout_seconds=10000)
        assert slow._timeout == 120
        fast = OpenAIChatProvider(api_key="x", timeout_seconds=0)
        assert fast._timeout == 1

    def test_default_url(self):
        p = OpenAIChatProvider(api_key="x")
        assert p._api_url == OPENAI_API_URL


# ---------------------------------------------------------------------------
# complete_json: happy path
# ---------------------------------------------------------------------------


class TestCompleteJsonHappyPath:
    def test_returns_message_content(self):
        sess = _FakeSession(_ok_response('{"ok": true}'))
        p = OpenAIChatProvider(api_key="sk-x", session=sess)
        out = p.complete_json("system", "user")
        assert out == '{"ok": true}'

    def test_request_payload_contract(self):
        sess = _FakeSession(_ok_response('{"x":1}'))
        p = OpenAIChatProvider(api_key="sk-x", session=sess, model="custom-model")
        p.complete_json("sys-prompt", "user-prompt", max_tokens=500, temperature=0.5)

        call = sess.last_call
        assert call is not None
        assert call["url"] == OPENAI_API_URL
        assert call["headers"]["Authorization"] == "Bearer sk-x"
        body = call["json"]
        assert body["model"] == "custom-model"
        assert body["max_tokens"] == 500
        assert body["temperature"] == 0.5
        # Forced JSON-object output is critical for the explainer's parser.
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == "sys-prompt"
        assert body["messages"][1]["role"] == "user"
        assert body["messages"][1]["content"] == "user-prompt"


# ---------------------------------------------------------------------------
# complete_json: failure modes -> LLMProviderError (429 exhaustion -> rate limited)
# ---------------------------------------------------------------------------


class TestCompleteJsonErrors:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        p = OpenAIChatProvider(session=_FakeSession(_ok_response("{}")))
        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
            p.complete_json("s", "u")

    def test_non_200_raises_with_body(self):
        sess = _FakeSession(_FakeResponse(403, text="forbidden"))
        p = OpenAIChatProvider(api_key="x", session=sess)
        with pytest.raises(LLMProviderError, match="http 403"):
            p.complete_json("s", "u")

    def test_429_exhausts_retries_raises_rate_limited(self, monkeypatch):
        monkeypatch.setattr(
            "backend.services.agent.anomaly_explainer.openai_provider.time.sleep",
            lambda _s: None,
        )
        sess = _FakeSession(_FakeResponse(429, text="rate limited"))
        p = OpenAIChatProvider(api_key="x", session=sess)
        with pytest.raises(LLMProviderRateLimitedError, match="max retries"):
            p.complete_json("s", "u")

    def test_500_raises(self):
        sess = _FakeSession(_FakeResponse(500, text="boom"))
        p = OpenAIChatProvider(api_key="x", session=sess)
        with pytest.raises(LLMProviderError, match="http 500"):
            p.complete_json("s", "u")

    def test_response_not_json_raises(self):
        bad = _FakeResponse(200, json_raises=True)
        sess = _FakeSession(bad)
        p = OpenAIChatProvider(api_key="x", session=sess)
        with pytest.raises(LLMProviderError, match="was not JSON"):
            p.complete_json("s", "u")

    def test_no_choices_raises(self):
        sess = _FakeSession(_FakeResponse(200, {"choices": []}))
        p = OpenAIChatProvider(api_key="x", session=sess)
        with pytest.raises(LLMProviderError, match="no choices"):
            p.complete_json("s", "u")

    def test_empty_content_raises(self):
        sess = _FakeSession(
            _FakeResponse(200, {"choices": [{"message": {"content": ""}}]})
        )
        p = OpenAIChatProvider(api_key="x", session=sess)
        with pytest.raises(LLMProviderError, match="no choices"):
            p.complete_json("s", "u")

    def test_network_exception_wrapped(self):
        sess = _FakeSession(_ok_response("{}"), raise_on_post=ConnectionError("dns fail"))
        p = OpenAIChatProvider(api_key="x", session=sess)
        with pytest.raises(LLMProviderError, match="network error"):
            p.complete_json("s", "u")


# ---------------------------------------------------------------------------
# Integration with AnomalyExplainer
# ---------------------------------------------------------------------------


class TestExplainerIntegration:
    def test_end_to_end_happy_path(self):
        canned = json.dumps(
            {
                "title": "Stale snapshots for tracked universe",
                "summary": "12 symbols are > 24h old.",
                "root_cause_hypothesis": "Daily refresh task failed at 16:35.",
                "narrative": "Detail.",
                "confidence": 0.7,
                "steps": [
                    {
                        "order": 1,
                        "description": "Inspect failed JobRun row.",
                        "requires_approval": False,
                    }
                ],
            }
        )
        sess = _FakeSession(_ok_response(canned))
        provider = OpenAIChatProvider(api_key="x", session=sess)
        explainer = AnomalyExplainer(provider)

        anomaly = Anomaly(
            id="stale:test",
            category=AnomalyCategory.STALE_SNAPSHOT,
            severity=AnomalySeverity.WARNING,
            title="12 stale snapshots",
            facts={"count": 12},
            raw_evidence="last_refresh=2026-04-08T16:35:00Z",
        )
        exp = explainer.explain(anomaly)
        assert exp.is_fallback is False
        assert exp.title == "Stale snapshots for tracked universe"
        assert exp.model.startswith("openai:")
        assert exp.steps[0].requires_approval is False

    def test_provider_failure_falls_back_cleanly(self):
        sess = _FakeSession(_FakeResponse(503, text="unavailable"))
        provider = OpenAIChatProvider(api_key="x", session=sess)
        explainer = AnomalyExplainer(provider)
        exp = explainer.explain(
            Anomaly(
                id="x",
                category=AnomalyCategory.PIPELINE_FAILURE,
                severity=AnomalySeverity.ERROR,
                title="t",
            )
        )
        assert exp.is_fallback is True
        assert exp.model.startswith("openai:")
