"""Tests for recover_stale_job_runs_impl: only stale RUNNING jobs are cancelled."""

from datetime import datetime, timedelta
from unittest.mock import patch

from backend.models.market_data import JobRun


def test_only_stale_running_jobs_are_cancelled(db_session):
    now = datetime.utcnow()
    stale = JobRun(task_name="task_a", status="running", started_at=now - timedelta(hours=3))
    fresh = JobRun(task_name="task_b", status="running", started_at=now - timedelta(minutes=30))
    done = JobRun(task_name="task_c", status="ok", started_at=now - timedelta(hours=5), finished_at=now)

    db_session.add_all([stale, fresh, done])
    db_session.flush()

    from backend.tasks.market_data_tasks import recover_stale_job_runs_impl

    with patch("backend.tasks.market_data_tasks.SessionLocal", return_value=db_session):
        with patch.object(db_session, "close"):
            result = recover_stale_job_runs_impl(stale_minutes=120)

    assert result["cancelled_count"] == 1

    db_session.expire_all()
    assert stale.status == "cancelled"
    assert stale.finished_at is not None
    assert stale.error is not None
    assert fresh.status == "running"
    assert done.status == "ok"
