"""Tests for the hourly Vercel billing scheduler (Conversation alerts)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.schedulers import vercel_billing_monitor as vb_sched


@pytest.mark.asyncio
async def test_tick_creates_conversation_per_alert() -> None:
    alerts = [
        {
            "threshold": 0.5,
            "severity": "info",
            "spent_usd": 20.0,
            "budget_usd": 40.0,
            "pct": 50.0,
        }
    ]
    create = MagicMock()
    with (
        patch.object(vb_sched, "run", return_value={"ok": True, "alerts": alerts}),
        patch.object(vb_sched, "create_conversation", create),
    ):
        await vb_sched._tick()
    assert create.call_count == 1
    arg0 = create.call_args[0][0]
    assert arg0.urgency == "high"
    assert "vercel-budget" in arg0.tags
    assert "paperwork-labs" in arg0.tags
    assert "50%" in arg0.title or "50" in arg0.title


@pytest.mark.asyncio
async def test_tick_skips_when_run_not_ok() -> None:
    create = MagicMock()
    with (
        patch.object(vb_sched, "run", return_value={"ok": False, "reason": "no_token"}),
        patch.object(vb_sched, "create_conversation", create),
    ):
        await vb_sched._tick()
    create.assert_not_called()
