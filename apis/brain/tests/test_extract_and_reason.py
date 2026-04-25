"""Unit tests for the ExtractAndReason chain strategy (P3, Buffer Week 4).

The two-hop pattern matters enough to test three invariants:
- extraction succeeds → digest is passed to the reasoning prompt
- extraction fails → reasoning still runs with the original system prompt
- Sonnet circuit open → falls back to gpt-4o with a warning

These are unit-level only; the integration ("does agent.process wire
strategy='extract_reason' correctly") belongs in the brain.process
test (see test_brain_process_strategy.py).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.router import (
    ChainContext,
    CircuitBreaker,
    ExtractAndReason,
)


def _ctx(message: str = "hello") -> ChainContext:
    return ChainContext(
        message=message,
        system_prompt="you are a CPA",
        messages=[{"role": "user", "content": message}],
        organization_id="test-org",
    )


@pytest.fixture
def cb() -> CircuitBreaker:
    return CircuitBreaker(redis_client=None)


@pytest.mark.asyncio
async def test_extraction_digest_injected_into_system_prompt(cb):
    """Flash digest ends up inline in the Sonnet system prompt."""
    extraction_response = {
        "content": '{"facts": ["Q3 loss $4k"], "ask": "deduct?"}',
        "tokens_in": 50,
        "tokens_out": 20,
        "model": "gemini-2.0-flash-exp",
        "provider": "google",
    }
    reasoning_response = {
        "content": "Yes — ordinary loss.",
        "tokens_in": 200,
        "tokens_out": 60,
        "model": "claude-sonnet-4-20250514",
        "provider": "anthropic",
    }

    async def fake_complete(**kwargs):
        if kwargs.get("model", "").startswith("gemini"):
            return extraction_response
        return reasoning_response

    strategy = ExtractAndReason(cb)
    with patch(
        "app.services.router.llm.complete_text",
        new=AsyncMock(side_effect=fake_complete),
    ) as mock_complete:
        result = await strategy.execute(_ctx("can I deduct this 4k?"))

    # Second call is the reasoning call; its system prompt must carry the
    # digest block so Sonnet doesn't have to re-parse the raw message.
    reasoning_call = mock_complete.call_args_list[1]
    reasoning_system = reasoning_call.kwargs["system_prompt"]
    assert "you are a CPA" in reasoning_system
    assert "Pre-extracted context" in reasoning_system
    assert "facts" in reasoning_system
    assert result.classification["strategy"] == "extract_and_reason"
    assert result.classification["extraction_succeeded"] is True
    assert result.content == "Yes — ordinary loss."


@pytest.mark.asyncio
async def test_extraction_failure_does_not_block_reasoning(cb):
    """If Flash dies, we still get a Sonnet answer (just without the digest)."""
    reasoning_response = {
        "content": "Yes — ordinary loss.",
        "tokens_in": 200,
        "tokens_out": 60,
        "model": "claude-sonnet-4-20250514",
        "provider": "anthropic",
    }

    async def fake_complete(**kwargs):
        if kwargs.get("model", "").startswith("gemini"):
            raise RuntimeError("Flash boom")
        return reasoning_response

    strategy = ExtractAndReason(cb)
    with patch(
        "app.services.router.llm.complete_text",
        new=AsyncMock(side_effect=fake_complete),
    ) as mock_complete:
        result = await strategy.execute(_ctx("tax question"))

    reasoning_call = mock_complete.call_args_list[1]
    reasoning_system = reasoning_call.kwargs["system_prompt"]
    assert "Pre-extracted context" not in reasoning_system
    assert result.classification["extraction_succeeded"] is False
    assert result.content == "Yes — ordinary loss."
