"""Track M.2 — regressions on webhook → trading persona wakeup.

WS-69 PR J: Slack channel routing removed. The wake-up path now always calls
agent.process (no channel-ID guard) and creates a Brain Conversation for
high-priority events. Tests updated accordingly.

medallion: ops
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers import webhooks


@pytest.mark.asyncio
async def test_wakeup_events_are_exactly_the_noisy_ones():
    """Explicit list — protects against silent broadening of the fanout.

    If a future event is added to KNOWN_EVENTS that should also wake the
    persona (e.g. ``margin.call``), add it here consciously.
    """
    assert (
        frozenset(
            {
                "risk.gate.activated",
                "risk.alert",
                "approval.required",
                "approval.needed",
                "stop.triggered",
            }
        )
        == webhooks._TRADING_WAKEUP_EVENTS
    )


@pytest.mark.asyncio
async def test_wakeup_calls_agent_with_trading_persona_pin():
    """Happy path: we pin persona=trading and create a Brain Conversation.

    Brain Conversation is only created when the agent returns a non-empty response.
    """
    fake_process = AsyncMock(
        return_value={"response": "Risk gate activated. Monitor position.", "persona": "trading"}
    )
    fake_redis = AsyncMock(return_value=None)
    mock_db = MagicMock()

    with (
        patch("app.services.agent.process", new=fake_process),
        patch("app.redis.get_redis", new=fake_redis),
        patch("app.services.conversations.create_conversation") as mock_conv,
    ):
        await webhooks._wake_trading_persona(
            db=mock_db,
            organization_id="paperwork-labs",
            event="risk_gate_activated",
            event_norm="risk.gate.activated",
            data={"gate": "max_position_size"},
            timestamp=None,
            summary="Risk gate blocked AAPL buy",
        )
    assert fake_process.await_count == 1
    kwargs = fake_process.await_args.kwargs
    assert kwargs["persona_pin"] == "trading"
    assert kwargs["thread_id"] == "trading:webhook:risk.gate.activated"
    assert kwargs["organization_id"] == "paperwork-labs"
    mock_conv.assert_called_once()


@pytest.mark.asyncio
async def test_wakeup_noop_conversation_when_agent_returns_empty():
    """Empty agent response → no Brain Conversation created."""
    fake_process = AsyncMock(return_value={"response": "", "persona": "trading"})
    fake_redis = AsyncMock(return_value=None)
    mock_db = MagicMock()

    with (
        patch("app.services.agent.process", new=fake_process),
        patch("app.redis.get_redis", new=fake_redis),
        patch("app.services.conversations.create_conversation") as mock_conv,
    ):
        await webhooks._wake_trading_persona(
            db=mock_db,
            organization_id="paperwork-labs",
            event="risk_gate_activated",
            event_norm="risk.gate.activated",
            data={},
            timestamp=None,
            summary="test",
        )
    mock_conv.assert_not_called()
