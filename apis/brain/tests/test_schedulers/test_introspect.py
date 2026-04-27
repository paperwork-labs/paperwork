"""Scheduler introspection (``/internal/schedulers``)."""

from __future__ import annotations

import pytest

from app.schedulers.introspect import classification_for_job_id, list_apscheduler_jobs


def test_classification_for_job_id() -> None:
    assert classification_for_job_id("n8n_shadow_brain_daily") == "n8n-shadow"
    assert classification_for_job_id("brain_daily_briefing") == "cutover"
    assert classification_for_job_id("brain_sprint_close") == "cutover"
    assert classification_for_job_id("brain_data_source_monitor") == "cutover"
    assert classification_for_job_id("sprint_auto_logger") == "operational"
    assert classification_for_job_id("pr_sweep") == "net-new"


def test_list_apscheduler_jobs_empty_without_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.schedulers.introspect.get_scheduler", lambda: None)
    assert list_apscheduler_jobs() == []
