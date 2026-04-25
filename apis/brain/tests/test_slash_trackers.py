"""Slack slash commands backed by tracker-index.json (/sprint, /tasks, /plan)."""

from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from starlette.background import BackgroundTasks
from starlette.requests import Request

from app.routers import webhooks
from app.services.tracker_slash import TRACKER_UNAVAILABLE_MSG


def _sample_index() -> dict:
    return {
        "company": {
            "critical_dates": [
                {
                    "milestone": "Open item",
                    "deadline": "Soon",
                    "status": "NOT STARTED",
                },
                {
                    "milestone": "In flight",
                    "deadline": "Next week",
                    "status": "IN PROGRESS",
                },
                {
                    "milestone": "Done item",
                    "deadline": "Past",
                    "status": "DONE",
                },
            ],
        },
        "sprints": [
            {
                "title": "Current sprint",
                "slug": "current",
                "status": "active",
                "start": "2026-04-01",
                "end": "2026-04-30",
            },
            {
                "title": "Old ship",
                "slug": "old",
                "status": "shipped",
                "start": "2026-03-01",
                "end": "2026-03-15",
                "pr": 99,
                "pr_url": "https://github.com/paperwork-labs/paperwork/pull/99",
            },
            {
                "title": "Latest ship",
                "slug": "new",
                "status": "shipped",
                "start": "2026-04-01",
                "end": "2026-04-23",
                "pr": 141,
                "pr_url": "https://github.com/paperwork-labs/paperwork/pull/141",
            },
        ],
        "products": [
            {
                "label": "DemoProduct",
                "slug": "demo",
                "plans": [
                    {
                        "title": "Plan A",
                        "status": "active",
                        "path": "docs/demo/PLAN.md",
                    },
                ],
            },
        ],
    }


def _make_slack_request(form: dict) -> Request:
    body = urlencode(form).encode()
    done = False

    async def receive():
        nonlocal done
        if not done:
            done = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/webhooks/slack/command",
        "raw_path": b"/api/v1/webhooks/slack/command",
        "query_string": b"",
        "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        "client": ("test", 50000),
        "server": ("test", 80),
    }
    return Request(scope, receive)


@contextmanager
def _slack_command_dev():
    with (
        patch("app.config.settings.ENVIRONMENT", "development"),
        patch("app.config.settings.SLACK_SIGNING_SECRET", ""),
    ):
        yield


@pytest.mark.asyncio
async def test_slack_command_sprint_active_and_shipped(monkeypatch):
    monkeypatch.setattr(webhooks, "load_tracker_index", lambda: _sample_index())

    with _slack_command_dev():
        r_active = await webhooks.slack_slash_command(
            _make_slack_request(
                {
                    "command": "/sprint",
                    "text": "",
                    "user_id": "U1",
                    "channel_id": "C1",
                    "response_url": "https://hooks.slack.com/commands/fake",
                },
            ),
            BackgroundTasks(),
        )
    assert r_active["response_type"] == "in_channel"
    assert "Active sprints" in r_active["text"]
    assert "Current sprint" in r_active["text"]

    with _slack_command_dev():
        r_ship = await webhooks.slack_slash_command(
            _make_slack_request(
                {
                    "command": "/sprint",
                    "text": "shipped",
                    "user_id": "U1",
                    "channel_id": "C1",
                    "response_url": "https://hooks.slack.com/commands/fake",
                },
            ),
            BackgroundTasks(),
        )
    assert r_ship["response_type"] == "in_channel"
    assert "Latest ship" in r_ship["text"]
    assert "pull/141" in r_ship["text"]
    assert "Old ship" in r_ship["text"]


@pytest.mark.asyncio
async def test_slack_command_tasks_open_and_all(monkeypatch):
    monkeypatch.setattr(webhooks, "load_tracker_index", lambda: _sample_index())

    with _slack_command_dev():
        r_open = await webhooks.slack_slash_command(
            _make_slack_request(
                {
                    "command": "/tasks",
                    "text": "",
                    "user_id": "U1",
                    "channel_id": "C1",
                    "response_url": "https://hooks.slack.com/commands/fake",
                },
            ),
            BackgroundTasks(),
        )
    assert r_open["response_type"] == "in_channel"
    assert "Open item" in r_open["text"]
    assert "In flight" in r_open["text"]
    assert "Done item" not in r_open["text"]

    with _slack_command_dev():
        r_all = await webhooks.slack_slash_command(
            _make_slack_request(
                {
                    "command": "/tasks",
                    "text": "all",
                    "user_id": "U1",
                    "channel_id": "C1",
                    "response_url": "https://hooks.slack.com/commands/fake",
                },
            ),
            BackgroundTasks(),
        )
    assert r_all["response_type"] == "in_channel"
    assert "Done item" in r_all["text"]


@pytest.mark.asyncio
async def test_slack_command_plan_list_and_product(monkeypatch):
    monkeypatch.setattr(webhooks, "load_tracker_index", lambda: _sample_index())

    with _slack_command_dev():
        r_list = await webhooks.slack_slash_command(
            _make_slack_request(
                {
                    "command": "/plan",
                    "text": "",
                    "user_id": "U1",
                    "channel_id": "C1",
                    "response_url": "https://hooks.slack.com/commands/fake",
                },
            ),
            BackgroundTasks(),
        )
    assert r_list["response_type"] == "in_channel"
    assert "demo" in r_list["text"]
    assert "1 plan" in r_list["text"]

    with _slack_command_dev():
        r_demo = await webhooks.slack_slash_command(
            _make_slack_request(
                {
                    "command": "/plan",
                    "text": "demo",
                    "user_id": "U1",
                    "channel_id": "C1",
                    "response_url": "https://hooks.slack.com/commands/fake",
                },
            ),
            BackgroundTasks(),
        )
    assert r_demo["response_type"] == "in_channel"
    assert "Plan A" in r_demo["text"]
    assert "github.com" in r_demo["text"]
    assert "[active]" in r_demo["text"]


@pytest.mark.asyncio
async def test_slack_command_tracker_missing(monkeypatch):
    monkeypatch.setattr(webhooks, "load_tracker_index", lambda: None)

    with _slack_command_dev():
        r = await webhooks.slack_slash_command(
            _make_slack_request(
                {
                    "command": "/sprint",
                    "text": "",
                    "user_id": "U1",
                    "channel_id": "C1",
                    "response_url": "https://hooks.slack.com/commands/fake",
                },
            ),
            BackgroundTasks(),
        )
    assert r["response_type"] == "ephemeral"
    assert r["text"] == TRACKER_UNAVAILABLE_MSG
