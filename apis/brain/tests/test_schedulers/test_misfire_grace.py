"""Regression: scheduler installs must set ``misfire_grace_time`` for flaky DB/network."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.schedulers import sprint_auto_logger, sprint_completion
from app.services import workstream_progress_writeback


def test_critical_scheduler_installs_pass_misfire_grace_time() -> None:
    mock_scheduler = MagicMock()

    workstream_progress_writeback.install(mock_scheduler)
    sprint_auto_logger.install(mock_scheduler)
    sprint_completion.install(mock_scheduler)

    names_to_grace: dict[str, int | float] = {}
    for call in mock_scheduler.add_job.call_args_list:
        name = call.kwargs.get("name")
        grace = call.kwargs.get("misfire_grace_time")
        assert grace is not None
        names_to_grace[str(name)] = grace

    assert names_to_grace["Workstream progress JSON writeback (Track Z)"] >= 60
    assert names_to_grace["Sprint auto-logger (merged PRs → docs/sprints Outcome)"] >= 60
    assert names_to_grace["Sprint auto-close (merged PRs + completed workstreams → status: closed)"] >= 60
