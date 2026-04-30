"""Tracker formatter functions (/sprint, /tasks, /plan) backed by tracker-index.json.

WS-69 PR J: migrated from Slack slash command endpoint tests to direct unit
tests of tracker_response_* functions (the Slack slash command endpoint was
removed; the formatting logic lives on in tracker_slash.py for MCP tools / CLI).
"""

from __future__ import annotations

from app.services.tracker_slash import (
    TRACKER_UNAVAILABLE_MSG,
    tracker_response_plan,
    tracker_response_sprint,
    tracker_response_tasks,
)


def _sample_index() -> dict:  # type: ignore[type-arg]
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


def test_tracker_response_sprint_active_and_shipped() -> None:
    idx = _sample_index()

    r_active = tracker_response_sprint(idx, "")
    assert r_active["response_type"] == "in_channel"
    assert "Active sprints" in r_active["text"]
    assert "Current sprint" in r_active["text"]

    r_ship = tracker_response_sprint(idx, "shipped")
    assert r_ship["response_type"] == "in_channel"
    assert "Latest ship" in r_ship["text"]
    assert "pull/141" in r_ship["text"]
    assert "Old ship" in r_ship["text"]


def test_tracker_response_tasks_open_and_all() -> None:
    idx = _sample_index()

    r_open = tracker_response_tasks(idx, "")
    assert r_open["response_type"] == "in_channel"
    assert "Open item" in r_open["text"]
    assert "In flight" in r_open["text"]
    assert "Done item" not in r_open["text"]

    r_all = tracker_response_tasks(idx, "all")
    assert r_all["response_type"] == "in_channel"
    assert "Done item" in r_all["text"]


def test_tracker_response_plan_list_and_product() -> None:
    idx = _sample_index()

    r_list = tracker_response_plan(idx, "")
    assert r_list["response_type"] == "in_channel"
    assert "demo" in r_list["text"]
    assert "1 plan" in r_list["text"]

    r_demo = tracker_response_plan(idx, "demo")
    assert r_demo["response_type"] == "in_channel"
    assert "Plan A" in r_demo["text"]
    assert "github.com" in r_demo["text"]
    assert "[active]" in r_demo["text"]


def test_tracker_response_tracker_missing() -> None:
    r = tracker_response_sprint(None, "")
    assert r["response_type"] == "ephemeral"
    assert r["text"] == TRACKER_UNAVAILABLE_MSG
