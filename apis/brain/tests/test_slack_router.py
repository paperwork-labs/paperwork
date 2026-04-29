"""Tests for ``app.services.slack_router``.

Covers:
- Channel routing per event_type
- Dedup window (within window → thread_reply; after window → new_post)
- Rate limit budget → defer_to_digest
- Quiet hours (high severity posts immediately; low defers)
- Morning digest flush gathers and clears queue
- Malformed YAML config → log warning + use defaults
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from app.schemas.slack_routing import RoutingAction
from app.services import slack_router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_router_state() -> None:
    """Reset all in-memory state between tests."""
    slack_router._dedup.clear()
    slack_router._rate_window.clear()
    slack_router._morning_queue.clear()
    slack_router._state_loaded = False


def _write_routing_yaml(path: Path, extra: dict[str, Any] | None = None) -> None:
    config: dict[str, Any] = {
        "schema": "slack_routing/v1",
        "default_channel": "#ops",
        "channels": {
            "pr_merged": "#ops",
            "pr_failed": "#ops",
            "anomaly_high": "#alerts",
            "weekly_retro": "#strategy",
            "blitz_progress": "#ops",
        },
        "dedup_window_minutes": 60,
        "rate_limit_per_hour": 30,
        "quiet_hours": {
            "start": "22:00",
            "end": "09:00",
            "timezone": "UTC",
            "weekends_quiet": True,
        },
        "quiet_severity_threshold": "high",
    }
    if extra:
        config.update(extra)
    config_path = path / "apis/brain/data/slack_routing.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_router_state(tmp_path: Path):
    """Reset in-memory state and provide tmp_path before each test."""
    _reset_router_state()
    _write_routing_yaml(tmp_path)
    yield tmp_path
    _reset_router_state()


# ---------------------------------------------------------------------------
# Shared business-hours timestamp (Tuesday 15:00 UTC — not quiet, not weekend)
# ---------------------------------------------------------------------------

_BIZ = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)  # Tuesday 15:00 UTC


# ---------------------------------------------------------------------------
# 1. Channel routing per event_type
# ---------------------------------------------------------------------------


def test_channel_routing_pr_merged(tmp_path: Path) -> None:
    decision = slack_router.route(event_type="pr_merged", key="pr-1", now=_BIZ, root=tmp_path)
    assert decision.action == RoutingAction.new_post
    assert decision.channel == "#ops"


def test_channel_routing_anomaly_high(tmp_path: Path) -> None:
    decision = slack_router.route(event_type="anomaly_high", key="alert-1", now=_BIZ, root=tmp_path)
    assert decision.action == RoutingAction.new_post
    assert decision.channel == "#alerts"


def test_channel_routing_weekly_retro(tmp_path: Path) -> None:
    decision = slack_router.route(event_type="weekly_retro", key="retro-1", now=_BIZ, root=tmp_path)
    assert decision.action == RoutingAction.new_post
    assert decision.channel == "#strategy"


def test_channel_routing_unknown_event_falls_back_to_default(tmp_path: Path) -> None:
    decision = slack_router.route(event_type="some_unknown_event", key="x", now=_BIZ, root=tmp_path)
    assert decision.action == RoutingAction.new_post
    assert decision.channel == "#ops"


def test_channel_routing_blitz_progress(tmp_path: Path) -> None:
    decision = slack_router.route(
        event_type="blitz_progress", key="tick-1", now=_BIZ, root=tmp_path
    )
    assert decision.action == RoutingAction.new_post
    assert decision.channel == "#ops"


# ---------------------------------------------------------------------------
# 2. Dedup window
# ---------------------------------------------------------------------------


def test_dedup_within_window_returns_thread_reply(tmp_path: Path) -> None:
    now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)  # within business hours

    first = slack_router.route(
        event_type="pr_merged", severity="low", key="pr-42", now=now, root=tmp_path
    )
    assert first.action == RoutingAction.new_post

    second = slack_router.route(
        event_type="pr_merged",
        severity="low",
        key="pr-42",
        now=now + timedelta(minutes=30),
        root=tmp_path,
    )
    assert second.action == RoutingAction.thread_reply


def test_dedup_after_window_returns_new_post(tmp_path: Path) -> None:
    now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)

    slack_router.route(event_type="pr_merged", severity="low", key="pr-99", now=now, root=tmp_path)

    after = slack_router.route(
        event_type="pr_merged",
        severity="low",
        key="pr-99",
        now=now + timedelta(minutes=61),
        root=tmp_path,
    )
    assert after.action == RoutingAction.new_post


def test_dedup_different_keys_both_new_post(tmp_path: Path) -> None:
    now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)

    d1 = slack_router.route(
        event_type="pr_merged", severity="low", key="pr-1", now=now, root=tmp_path
    )
    d2 = slack_router.route(
        event_type="pr_merged", severity="low", key="pr-2", now=now, root=tmp_path
    )
    assert d1.action == RoutingAction.new_post
    assert d2.action == RoutingAction.new_post


def test_dedup_empty_key_never_deduplicates(tmp_path: Path) -> None:
    """Empty key means every call is unique — no dedup."""
    now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)

    d1 = slack_router.route(event_type="pr_merged", key="", now=now, root=tmp_path)
    d2 = slack_router.route(
        event_type="pr_merged", key="", now=now + timedelta(minutes=1), root=tmp_path
    )
    assert d1.action == RoutingAction.new_post
    assert d2.action == RoutingAction.new_post


# ---------------------------------------------------------------------------
# 3. Rate limit budget → defer_to_digest
# ---------------------------------------------------------------------------


def test_rate_limit_exceeded_returns_defer_to_digest(tmp_path: Path) -> None:
    _write_routing_yaml(tmp_path, {"rate_limit_per_hour": 3})
    _reset_router_state()
    _write_routing_yaml(tmp_path, {"rate_limit_per_hour": 3})

    now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)

    for i in range(3):
        d = slack_router.route(
            event_type="pr_merged",
            key=f"pr-{i}",
            now=now + timedelta(seconds=i),
            root=tmp_path,
        )
        assert d.action == RoutingAction.new_post

    overflow = slack_router.route(
        event_type="pr_merged",
        key="pr-overflow",
        now=now + timedelta(seconds=10),
        root=tmp_path,
    )
    assert overflow.action == RoutingAction.defer_to_digest


def test_rate_limit_resets_after_window(tmp_path: Path) -> None:
    _write_routing_yaml(tmp_path, {"rate_limit_per_hour": 2})
    _reset_router_state()
    _write_routing_yaml(tmp_path, {"rate_limit_per_hour": 2})

    now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)

    for i in range(2):
        slack_router.route(
            event_type="pr_merged", key=f"pr-{i}", now=now + timedelta(seconds=i), root=tmp_path
        )

    # 61 minutes later — window should have cleared
    after = slack_router.route(
        event_type="pr_merged",
        key="pr-new",
        now=now + timedelta(minutes=61),
        root=tmp_path,
    )
    assert after.action == RoutingAction.new_post


# ---------------------------------------------------------------------------
# 4. Quiet hours
# ---------------------------------------------------------------------------


def test_quiet_hours_high_severity_posts_immediately(tmp_path: Path) -> None:
    # 23:00 UTC weekday = quiet hours
    now = datetime(2026, 4, 27, 23, 0, 0, tzinfo=UTC)  # Monday 23:00
    decision = slack_router.route(
        event_type="anomaly_high",
        severity="high",
        key="crit-1",
        now=now,
        root=tmp_path,
    )
    assert decision.action == RoutingAction.new_post


def test_quiet_hours_low_severity_defers(tmp_path: Path) -> None:
    now = datetime(2026, 4, 27, 23, 0, 0, tzinfo=UTC)  # Monday 23:00
    decision = slack_router.route(
        event_type="pr_merged",
        severity="low",
        key="pr-quiet",
        now=now,
        root=tmp_path,
    )
    assert decision.action == RoutingAction.defer_to_morning


def test_quiet_hours_medium_severity_defers(tmp_path: Path) -> None:
    now = datetime(2026, 4, 27, 23, 0, 0, tzinfo=UTC)
    decision = slack_router.route(
        event_type="anomaly_medium",
        severity="medium",
        key="med-1",
        now=now,
        root=tmp_path,
    )
    assert decision.action == RoutingAction.defer_to_morning


def test_business_hours_low_severity_posts_immediately(tmp_path: Path) -> None:
    now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)  # Tuesday 15:00 UTC
    decision = slack_router.route(
        event_type="pr_merged",
        severity="low",
        key="pr-biz",
        now=now,
        root=tmp_path,
    )
    assert decision.action == RoutingAction.new_post


def test_weekend_low_severity_defers(tmp_path: Path) -> None:
    # Saturday 14:00 UTC
    now = datetime(2026, 4, 25, 14, 0, 0, tzinfo=UTC)
    decision = slack_router.route(
        event_type="pr_merged",
        severity="low",
        key="pr-weekend",
        now=now,
        root=tmp_path,
    )
    assert decision.action == RoutingAction.defer_to_morning


def test_weekend_high_severity_posts_immediately(tmp_path: Path) -> None:
    now = datetime(2026, 4, 25, 14, 0, 0, tzinfo=UTC)  # Saturday
    decision = slack_router.route(
        event_type="incident_high",
        severity="high",
        key="inc-1",
        now=now,
        root=tmp_path,
    )
    assert decision.action == RoutingAction.new_post


# ---------------------------------------------------------------------------
# 5. Morning digest flush
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_morning_digest_flush_clears_queue(tmp_path: Path) -> None:
    now = datetime(2026, 4, 27, 23, 0, 0, tzinfo=UTC)

    # Enqueue a few items via quiet-hours deferral
    for i in range(3):
        slack_router.route(
            event_type="pr_merged",
            severity="low",
            key=f"pr-deferred-{i}",
            payload={"text": f"PR {i} merged"},
            now=now,
            root=tmp_path,
        )

    assert len(slack_router._morning_queue) == 3

    with patch(
        "app.services.slack_router._slack_post_message",
        new_callable=AsyncMock,
        return_value={"ok": True, "ts": "1234567890.000001"},
    ) as mock_post:
        result = await slack_router.flush_morning_digest(root=tmp_path)

    assert result["sent"] == 3
    assert result["skipped"] == 0
    assert len(slack_router._morning_queue) == 0
    mock_post.assert_called_once()  # batched into one post per channel


@pytest.mark.asyncio
async def test_morning_digest_empty_queue_no_post(tmp_path: Path) -> None:
    with patch(
        "app.services.slack_router._slack_post_message",
        new_callable=AsyncMock,
    ) as mock_post:
        result = await slack_router.flush_morning_digest(root=tmp_path)

    assert result["sent"] == 0
    assert result["skipped"] == 0
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_morning_digest_skipped_when_slack_fails(tmp_path: Path) -> None:
    now = datetime(2026, 4, 27, 23, 0, 0, tzinfo=UTC)

    slack_router.route(
        event_type="pr_merged",
        severity="low",
        key="pr-fail",
        payload={"text": "oops"},
        now=now,
        root=tmp_path,
    )

    with patch(
        "app.services.slack_router._slack_post_message",
        new_callable=AsyncMock,
        return_value={"ok": False, "error": "channel_not_found"},
    ):
        result = await slack_router.flush_morning_digest(root=tmp_path)

    assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# 6. Malformed YAML config → log warning + use defaults
# ---------------------------------------------------------------------------


def test_malformed_yaml_falls_back_to_defaults(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config_path = tmp_path / "apis/brain/data/slack_routing.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("this: is: not: valid: yaml: [[[", encoding="utf-8")

    _reset_router_state()

    import logging

    with caplog.at_level(logging.WARNING, logger="app.services.slack_router"):
        decision = slack_router.route(event_type="pr_merged", key="test", root=tmp_path)

    assert decision.channel == "#ops"  # default_channel fallback
    assert any("config load failed" in rec.message for rec in caplog.records)


def test_missing_yaml_falls_back_to_defaults(tmp_path: Path) -> None:
    empty = tmp_path / "empty_repo"
    empty.mkdir()
    _reset_router_state()

    decision = slack_router.route(event_type="pr_merged", key="test", root=empty)
    assert decision.channel == "#ops"


# ---------------------------------------------------------------------------
# 7. Persistence round-trip
# ---------------------------------------------------------------------------


def test_dedup_state_persisted_to_disk(tmp_path: Path) -> None:
    now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=UTC)

    slack_router.route(
        event_type="pr_merged", severity="low", key="pr-persist", now=now, root=tmp_path
    )

    state_path = tmp_path / "apis/brain/data/slack_dedup_state.json"
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert "dedup" in data
    assert len(data["dedup"]) >= 1


def test_morning_queue_persisted_to_disk(tmp_path: Path) -> None:
    now = datetime(2026, 4, 27, 23, 0, 0, tzinfo=UTC)

    slack_router.route(
        event_type="pr_merged",
        severity="low",
        key="pr-mq",
        payload={"text": "hello"},
        now=now,
        root=tmp_path,
    )

    queue_path = tmp_path / "apis/brain/data/slack_morning_queue.json"
    assert queue_path.exists()
    items = json.loads(queue_path.read_text())
    assert isinstance(items, list)
    assert len(items) == 1
