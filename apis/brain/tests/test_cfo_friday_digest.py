"""CFO Friday digest: tracker brief formatting and scheduler registration.

medallion: ops
"""

from __future__ import annotations

from datetime import date
from unittest.mock import ANY, MagicMock

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.schedulers.cfo_friday_digest import (
    _run_friday_digest,
    build_friday_tracker_brief,
    install,
)


@pytest.fixture
def sample_tracker() -> dict:
    return {
        "sprints": [
            {
                "title": "Active Sprint",
                "slug": "active-1",
                "status": "active",
                "owner": "engineering",
                "end": "2026-05-30",
            },
            {
                "title": "Just Shipped",
                "slug": "shipped-1",
                "status": "shipped",
                "owner": "engineering",
                "end": "2026-04-22",
            },
        ],
        "company": {
            "critical_dates": [
                {
                    "milestone": "LLC",
                    "deadline": "TODAY",
                    "status": "NOT STARTED",
                },
                {
                    "milestone": "Rotated",
                    "deadline": "2025",
                    "status": "DONE",
                },
            ],
        },
        "products": [
            {
                "plans": [
                    {"status": "active", "title": "Plan A"},
                    {"status": "shipped", "title": "Old Plan"},
                ],
            }
        ],
    }


def test_friday_brief_from_fixture_data(sample_tracker: dict):
    brief, meta = build_friday_tracker_brief(sample_tracker, as_of=date(2026, 4, 24))
    assert "Active Sprint" in brief
    assert "engineering" in brief
    assert "Just Shipped" in brief
    assert "2026-04-22" in brief
    assert "LLC" in brief
    assert "Rotated" not in brief
    assert "*Active product plans (status=active):* 1" in brief
    assert meta["active_sprint_count"] == 1
    assert meta["shipped_last_7d_count"] == 1
    assert meta["plan_count"] == 1


def test_friday_brief_missing_index():
    brief, meta = build_friday_tracker_brief(None)
    assert "unavailable" in brief.lower() or "Unavailable" in brief
    assert meta["active_sprint_count"] == 0
    assert meta["plan_count"] == 0
    assert meta["shipped_last_7d_count"] == 0


def test_install_registers_friday_cron_job():
    sched = MagicMock()
    install(sched)
    sched.add_job.assert_called_once_with(
        _run_friday_digest,
        trigger=ANY,
        id="cfo_friday_digest",
        name="CFO Friday weekly digest (tracker + persona)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    tr = sched.add_job.call_args[1]["trigger"]
    assert isinstance(tr, CronTrigger)
    spec = str(tr).lower()
    assert "fri" in spec and "18" in spec
