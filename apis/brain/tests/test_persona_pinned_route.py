"""Unit tests for PersonaPinnedRoute + CostTracker (Phase D H1/H2/H3/H6).

These cover the critical path that was untested in the first D1 commit:
- escalation signals (compliance, tokens>N, mention:)
- requires_tools routing (MCP vs text-completion)
- LLMUnavailableError propagation (no silent fallback)
- cost ceiling enforcement (fail-fast before spend)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.cost_tracker import CostCeilingExceeded, check_ceiling, record_spend
from app.services.errors import LLMUnavailableError
from app.services.router import (
    ChainContext,
    CircuitBreaker,
    PersonaPinnedRoute,
    _provider_for_model,
)


def _ctx(message: str = "hello") -> ChainContext:
    return ChainContext(
        message=message,
        system_prompt="you are a bot",
        messages=[{"role": "user", "content": message}],
        organization_id="test-org",
    )


@pytest.fixture
def cb() -> CircuitBreaker:
    return CircuitBreaker(redis_client=None)


# ---------- provider inference ----------------------------------------------


def test_provider_for_model_routes_claude_to_anthropic():
    assert _provider_for_model("claude-sonnet-4-20250514") == "anthropic"


def test_provider_for_model_routes_gpt_to_openai():
    assert _provider_for_model("gpt-4o-mini") == "openai"


def test_provider_for_model_routes_gemini_to_google():
    assert _provider_for_model("gemini-2.5-flash") == "google"


# ---------- escalation ------------------------------------------------------


@pytest.mark.asyncio
async def test_pinned_route_no_escalation_stays_on_default(cb):
    route = PersonaPinnedRoute(
        cb,
        model="gpt-4o-mini",
        escalation_model=None,
        escalate_on_compliance=False,
        escalate_on_tokens_over=None,
        escalate_on_mentions=[],
        input_tokens=10,
        requires_tools=False,
    )
    with patch("app.services.router.llm.complete_text", new=AsyncMock(return_value={
        "content": "hi", "model": "gpt-4o-mini", "provider": "openai",
        "tokens_in": 5, "tokens_out": 3,
    })):
        res = await route.execute(_ctx())
    assert res.model == "gpt-4o-mini"
    assert res.classification["escalated"] is False
    assert res.classification["escalation_reason"] is None


@pytest.mark.asyncio
async def test_pinned_route_escalates_on_compliance(cb):
    route = PersonaPinnedRoute(
        cb,
        model="gpt-4o-mini",
        escalation_model="claude-sonnet-4-20250514",
        escalate_on_compliance=True,
        escalate_on_tokens_over=None,
        escalate_on_mentions=[],
        input_tokens=10,
        requires_tools=False,
    )
    with patch("app.services.router.llm.complete_text", new=AsyncMock(return_value={
        "content": "hi", "model": "claude-sonnet-4-20250514",
        "provider": "anthropic", "tokens_in": 5, "tokens_out": 3,
    })):
        res = await route.execute(_ctx())
    assert res.classification["escalation_reason"] == "compliance"


@pytest.mark.asyncio
async def test_pinned_route_escalates_on_tokens_over_threshold(cb):
    route = PersonaPinnedRoute(
        cb,
        model="gpt-4o-mini",
        escalation_model="claude-sonnet-4-20250514",
        escalate_on_compliance=False,
        escalate_on_tokens_over=100,
        escalate_on_mentions=[],
        input_tokens=500,
        requires_tools=False,
    )
    with patch("app.services.router.llm.complete_text", new=AsyncMock(return_value={
        "content": "hi", "model": "claude-sonnet-4-20250514",
        "provider": "anthropic", "tokens_in": 500, "tokens_out": 3,
    })):
        res = await route.execute(_ctx("big prompt"))
    assert res.classification["escalation_reason"] == "tokens"


@pytest.mark.asyncio
async def test_pinned_route_escalates_on_mention_keyword(cb):
    route = PersonaPinnedRoute(
        cb,
        model="gpt-4o-mini",
        escalation_model="claude-sonnet-4-20250514",
        escalate_on_compliance=False,
        escalate_on_tokens_over=None,
        escalate_on_mentions=["quarterly"],
        input_tokens=10,
        requires_tools=False,
    )
    with patch("app.services.router.llm.complete_text", new=AsyncMock(return_value={
        "content": "hi", "model": "claude-sonnet-4-20250514",
        "provider": "anthropic", "tokens_in": 5, "tokens_out": 3,
    })):
        res = await route.execute(_ctx("let's plan Quarterly strategy"))
    assert res.classification["escalation_reason"] == "mention"


@pytest.mark.asyncio
async def test_pinned_route_escalation_priority_compliance_first(cb):
    """compliance wins over mention/tokens when all fire."""
    route = PersonaPinnedRoute(
        cb,
        model="gpt-4o-mini",
        escalation_model="claude-sonnet-4-20250514",
        escalate_on_compliance=True,
        escalate_on_tokens_over=10,
        escalate_on_mentions=["audit"],
        input_tokens=500,
        requires_tools=False,
    )
    with patch("app.services.router.llm.complete_text", new=AsyncMock(return_value={
        "content": "hi", "model": "claude-sonnet-4-20250514",
        "provider": "anthropic", "tokens_in": 500, "tokens_out": 3,
    })):
        res = await route.execute(_ctx("security audit memo"))
    assert res.classification["escalation_reason"] == "compliance"


# ---------- tools routing ---------------------------------------------------


@pytest.mark.asyncio
async def test_requires_tools_true_routes_via_mcp(cb):
    route = PersonaPinnedRoute(
        cb,
        model="claude-sonnet-4-20250514",
        escalation_model=None,
        escalate_on_compliance=False,
        escalate_on_tokens_over=None,
        escalate_on_mentions=[],
        input_tokens=10,
        requires_tools=True,
    )
    mock_mcp = AsyncMock(return_value={
        "content": "hi", "model": "claude-sonnet-4-20250514",
        "provider": "anthropic", "tokens_in": 5, "tokens_out": 3,
        "tool_calls": [{"name": "read_github_file"}],
    })
    with (
        patch("app.services.router.llm.complete_with_mcp", new=mock_mcp),
        patch("app.services.router.llm.complete_text", new=AsyncMock(
            side_effect=AssertionError("text path should not be taken"),
        )),
    ):
        res = await route.execute(_ctx())
    mock_mcp.assert_awaited_once()
    assert res.classification["requires_tools"] is True


@pytest.mark.asyncio
async def test_requires_tools_false_routes_via_text(cb):
    route = PersonaPinnedRoute(
        cb,
        model="gpt-4o-mini",
        escalation_model=None,
        escalate_on_compliance=False,
        escalate_on_tokens_over=None,
        escalate_on_mentions=[],
        input_tokens=10,
        requires_tools=False,
    )
    mock_text = AsyncMock(return_value={
        "content": "hi", "model": "gpt-4o-mini", "provider": "openai",
        "tokens_in": 5, "tokens_out": 3,
    })
    with (
        patch("app.services.router.llm.complete_text", new=mock_text),
        patch("app.services.router.llm.complete_with_mcp", new=AsyncMock(
            side_effect=AssertionError("mcp path should not be taken"),
        )),
    ):
        await route.execute(_ctx())
    mock_text.assert_awaited_once()


# ---------- silent fallback removed -----------------------------------------


@pytest.mark.asyncio
async def test_pinned_route_raises_llm_unavailable_on_failure(cb):
    """H1: real LLM failure must raise, not return mock content."""
    route = PersonaPinnedRoute(
        cb,
        model="gpt-4o-mini",
        escalation_model=None,
        escalate_on_compliance=False,
        escalate_on_tokens_over=None,
        escalate_on_mentions=[],
        input_tokens=10,
        requires_tools=False,
    )
    with patch(
        "app.services.router.llm.complete_text",
        new=AsyncMock(side_effect=RuntimeError("connection refused")),
    ):
        with pytest.raises(LLMUnavailableError) as exc:
            await route.execute(_ctx())
    assert exc.value.provider == "openai"
    assert "connection refused" in exc.value.reason


# ---------- cost tracker ----------------------------------------------------


class _FakeRedis:
    """Minimal Redis-ish fixture for cost_tracker testing."""

    def __init__(self):
        self.store: dict[str, float] = {}
        self.ttl: dict[str, int] = {}

    async def get(self, key: str):
        val = self.store.get(key)
        return str(val) if val is not None else None

    async def incrbyfloat(self, key: str, amount: float) -> float:
        self.store[key] = self.store.get(key, 0.0) + amount
        return self.store[key]

    async def expire(self, key: str, ttl: int, nx: bool = False) -> None:
        if nx and key in self.ttl:
            return
        self.ttl[key] = ttl


@pytest.mark.asyncio
async def test_cost_tracker_allows_under_ceiling():
    r = _FakeRedis()
    r.store["cost:daily:org-1:cpa"] = 2.50
    spent = await check_ceiling(
        r, organization_id="org-1", persona="cpa", ceiling_usd=5.00,
    )
    assert spent == 2.50


@pytest.mark.asyncio
async def test_cost_tracker_raises_when_over_ceiling():
    r = _FakeRedis()
    r.store["cost:daily:org-1:cpa"] = 6.00
    with pytest.raises(CostCeilingExceeded) as exc:
        await check_ceiling(
            r, organization_id="org-1", persona="cpa", ceiling_usd=5.00,
        )
    assert exc.value.persona == "cpa"
    assert exc.value.spent_usd == 6.00
    assert exc.value.ceiling_usd == 5.00


@pytest.mark.asyncio
async def test_cost_tracker_fails_open_when_redis_missing():
    """Prefer degraded ops over taking Brain down when Redis blips."""
    spent = await check_ceiling(
        None, organization_id="org-1", persona="cpa", ceiling_usd=5.00,
    )
    assert spent == 0.0


@pytest.mark.asyncio
async def test_cost_tracker_no_check_when_ceiling_none():
    spent = await check_ceiling(
        _FakeRedis(), organization_id="org-1", persona="cpa", ceiling_usd=None,
    )
    assert spent == 0.0


@pytest.mark.asyncio
async def test_cost_tracker_records_spend_and_sets_ttl():
    r = _FakeRedis()
    total = await record_spend(
        r, organization_id="org-1", persona="cpa", amount_usd=0.05,
    )
    assert total == pytest.approx(0.05)
    assert r.ttl["cost:daily:org-1:cpa"] == 26 * 60 * 60
    total = await record_spend(
        r, organization_id="org-1", persona="cpa", amount_usd=0.02,
    )
    assert total == pytest.approx(0.07)


@pytest.mark.asyncio
async def test_cost_tracker_record_spend_ignores_nonpositive():
    r = _FakeRedis()
    total = await record_spend(
        r, organization_id="org-1", persona="cpa", amount_usd=0.0,
    )
    assert total == 0.0
    assert "cost:daily:org-1:cpa" not in r.store
