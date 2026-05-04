"""Scheduler introspection (``/internal/schedulers``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.schedulers.introspect import classification_for_job_id, list_apscheduler_jobs

if TYPE_CHECKING:
    import pytest


def test_classification_for_job_id() -> None:
    assert classification_for_job_id("brain_daily_briefing") == "cutover"
    assert classification_for_job_id("brain_sprint_close") == "cutover"
    assert classification_for_job_id("brain_data_source_monitor") == "cutover"
    assert classification_for_job_id("brain_data_deep_validator") == "cutover"
    assert classification_for_job_id("sprint_auto_logger") == "operational"
    assert classification_for_job_id("brain_autopilot_dispatcher") == "operational"
    assert classification_for_job_id("brain_probe_failure_dispatcher") == "operational"
    assert classification_for_job_id("brain_sprint_planner") == "operational"
    assert classification_for_job_id("pr_sweep") == "net-new"


def test_list_apscheduler_jobs_empty_without_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.schedulers.introspect.get_scheduler", lambda: None)
    assert list_apscheduler_jobs() == []
