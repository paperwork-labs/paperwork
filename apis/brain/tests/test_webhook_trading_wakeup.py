"""Track M.2 — regressions on webhook → #trading persona wakeup.

These tests pin the decision table: which events wake the trading
persona vs. which stay as silent episode rows. They also make sure the
wakeup path noops cleanly when no Slack channel ID is configured
(happens in dev, shouldn't 500 the caller).

medallion: ops
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.routers import webhooks


@pytest.mark.asyncio
async def test_wakeup_events_are_exactly_the_noisy_ones():
    """Explicit list — protects against silent broadening of the fanout.

    If a future event is added to KNOWN_EVENTS that should also wake the
    persona (e.g. ``margin.call``), add it here consciously. The cost of
    a surprise Slack fanout is higher than the cost of updating this set.
    """
    assert webhooks._TRADING_WAKEUP_EVENTS == frozenset({
        "risk.gate.activated",
        "risk.alert",
        "approval.required",
        "approval.needed",
        "stop.triggered",
    })


@pytest.mark.asyncio
async def test_wakeup_noop_when_no_channel_configured():
    """No SLACK_TRADING_CHANNEL_ID and no SLACK_ENGINEERING_CHANNEL_ID →
    we log and return without invoking the agent. Guards against webhook
    floods in a dev environment missing Slack config.
    """
    with patch("app.config.settings.SLACK_TRADING_CHANNEL_ID", ""), \
         patch("app.config.settings.SLACK_ENGINEERING_CHANNEL_ID", ""):
        with patch("app.services.agent.process", new=AsyncMock()) as mock_proc:
            await webhooks._wake_trading_persona(
                db=None,
                organization_id="paperwork-labs",
                event="risk_gate_activated",
                event_norm="risk.gate.activated",
                data={"gate": "max_position_size"},
                timestamp=None,
                summary="Risk gate blocked AAPL buy",
            )
            mock_proc.assert_not_awaited()


@pytest.mark.asyncio
async def test_wakeup_calls_agent_with_trading_pin_and_slack_post():
    """Happy path: we pin persona=trading, hand it a Slack channel ID,
    username, and emoji so Brain posts in one shot. If this contract ever
    drifts, the 2-node n8n pattern breaks in the same way.
    """
    fake_process = AsyncMock(return_value={"response": "ok", "persona": "trading"})
    fake_redis = AsyncMock(return_value=None)
    with patch("app.config.settings.SLACK_TRADING_CHANNEL_ID", "C_TRADING"), \
         patch("app.services.agent.process", new=fake_process), \
         patch("app.redis.get_redis", new=fake_redis):
        await webhooks._wake_trading_persona(
            db=None,
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
    assert kwargs["slack_channel_id"] == "C_TRADING"
    assert kwargs["slack_username"] == "Trading"
    assert kwargs["slack_icon_emoji"] == ":chart_with_upwards_trend:"
    assert kwargs["thread_id"] == "trading:webhook:risk.gate.activated"
    assert kwargs["organization_id"] == "paperwork-labs"
