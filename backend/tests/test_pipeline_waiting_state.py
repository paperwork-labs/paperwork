"""
Coverage for the pipeline `waiting` state classifier added in
fix/v1-pipeline-waiting-state.

Truth table under test (from `_classify_stale_queued`):

| Age          | Workers reachable | Workers busy | Resulting status |
|--------------|-------------------|--------------|------------------|
| <30s         | n/a               | n/a          | queued           |
| 30s..900s    | yes               | yes          | waiting          |
| 30s..900s    | yes               | no           | queued           |
| 30s..900s    | no                | n/a          | queued           |
| >900s        | yes               | yes          | waiting          |
| >900s        | yes               | no           | error (idle)     |
| >900s        | no                | n/a          | error (down)     |
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pytest

from backend.services.pipeline import dag as dag_module
from backend.services.pipeline.dag import (
    RUN_ERROR,
    RUN_QUEUED,
    RUN_RUNNING,
    RUN_WAITING,
    _classify_stale_queued,
)


def _meta(age_s: float, status: str = RUN_QUEUED) -> Dict[str, Any]:
    started = datetime.fromtimestamp(time.time() - age_s, tz=timezone.utc)
    return {
        "run_id": "manual-abc",
        "status": status,
        "started_at": started.isoformat(),
    }


def _patch_inspect(
    monkeypatch: pytest.MonkeyPatch, value: Optional[Dict[str, Any]]
) -> None:
    monkeypatch.setattr(
        dag_module, "_inspect_active_tasks", lambda: value
    )


# ---------------------------------------------------------------------------
# Non-queued runs are returned untouched
# ---------------------------------------------------------------------------

def test_non_queued_meta_returned_untouched(monkeypatch):
    """Running/ok/error/partial runs must not be reclassified."""
    for status in (RUN_RUNNING, "ok", "error", "partial"):
        meta = _meta(age_s=99999, status=status)
        out = _classify_stale_queued(meta)
        assert out is meta, f"status={status} should be untouched"


def test_meta_without_started_at_is_passthrough(monkeypatch):
    meta = {"run_id": "x", "status": RUN_QUEUED}
    assert _classify_stale_queued(meta) is meta


# ---------------------------------------------------------------------------
# Below the surface threshold — must remain `queued`
# ---------------------------------------------------------------------------

def test_young_queued_run_stays_queued(monkeypatch):
    """A 5-second-old queued run is too fresh to reclassify."""
    _patch_inspect(monkeypatch, {"worker-1": []})
    out = _classify_stale_queued(_meta(age_s=5))
    assert out["status"] == RUN_QUEUED
    assert "current_task" not in out


# ---------------------------------------------------------------------------
# Worker reachable + busy → `waiting`
# ---------------------------------------------------------------------------

def test_busy_worker_surfaces_waiting_with_longest_running_task(monkeypatch):
    """Two workers, two tasks; we report the older one as the blocker."""
    now = time.time()
    active = {
        "worker-fast@host": [
            {
                "id": "task-a",
                "name": "warm_dashboard_cache",
                "time_start": now - 10,
            },
        ],
        "worker-heavy@host": [
            {
                "id": "task-b",
                "name": "admin_repair_stage_history",
                "time_start": now - 173,
            },
        ],
    }
    _patch_inspect(monkeypatch, active)

    out = _classify_stale_queued(_meta(age_s=60))
    assert out["status"] == RUN_WAITING
    assert out["error"] is None
    assert out["waiting_for_s"] == pytest.approx(60, abs=2)
    assert out["current_task"]["name"] == "admin_repair_stage_history"
    assert out["current_task"]["worker"] == "worker-heavy@host"
    assert out["current_task"]["id"] == "task-b"
    assert out["current_task"]["running_for_s"] >= 170


def test_old_queued_run_with_busy_worker_still_waiting_not_error(monkeypatch):
    """Even past 900s, if a worker is actually busy we report `waiting`,
    not `error`. Heavy tasks like full_historical run for >30 minutes."""
    active = {
        "worker-heavy": [
            {"id": "t", "name": "full_historical", "time_start": time.time() - 1200},
        ],
    }
    _patch_inspect(monkeypatch, active)

    out = _classify_stale_queued(_meta(age_s=1500))
    assert out["status"] == RUN_WAITING
    assert "Queued but never started" not in (out.get("error") or "")


# ---------------------------------------------------------------------------
# Worker reachable but idle → keep `queued` until timeout, then `error`
# ---------------------------------------------------------------------------

def test_idle_worker_within_timeout_stays_queued(monkeypatch):
    _patch_inspect(monkeypatch, {"worker-fast": []})
    out = _classify_stale_queued(_meta(age_s=300))
    assert out["status"] == RUN_QUEUED


def test_idle_worker_past_timeout_escalates_to_error(monkeypatch):
    """Workers reachable but nothing running and run is >900s old.
    Likely broker/queue routing bug — escalate."""
    _patch_inspect(monkeypatch, {"worker-fast": []})
    out = _classify_stale_queued(_meta(age_s=1000))
    assert out["status"] == RUN_ERROR
    err = out["error"] or ""
    assert "broker" in err.lower() or "idle" in err.lower()


# ---------------------------------------------------------------------------
# No worker reachable → keep `queued` until timeout, then `error`
# ---------------------------------------------------------------------------

def test_no_worker_within_timeout_stays_queued(monkeypatch):
    """Transient broker glitches must not flap the row to error."""
    _patch_inspect(monkeypatch, None)
    out = _classify_stale_queued(_meta(age_s=300))
    assert out["status"] == RUN_QUEUED


def test_no_worker_past_timeout_errors_with_worker_down_message(monkeypatch):
    _patch_inspect(monkeypatch, None)
    out = _classify_stale_queued(_meta(age_s=1000))
    assert out["status"] == RUN_ERROR
    assert "worker may be down" in (out["error"] or "").lower()


# ---------------------------------------------------------------------------
# Backward-compat: the removed-but-aliased _expire_stale_queued must work
# ---------------------------------------------------------------------------

def test_legacy_alias_still_callable():
    assert dag_module._expire_stale_queued is dag_module._classify_stale_queued
