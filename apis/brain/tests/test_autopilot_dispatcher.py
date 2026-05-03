"""Tests for autopilot_dispatcher (Wave AUTO PR-AU3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import (
    AsyncIOScheduler,
)
from apscheduler.triggers.cron import CronTrigger

from app.models.dispatch import (
    DispatchEntry,
    DispatchResult,
)
from app.schedulers.autopilot_dispatcher import (
    JOB_ID,
    append_dispatch_log,
    dispatch_entry,
    install,
    load_dispatch_queue,
    pending_entries,
    run_autopilot_dispatch_sync,
    save_dispatch_queue,
    select_agent_model,
    select_persona,
)


def test_dispatch_entry_defaults() -> None:
    e = DispatchEntry(task_id="t-1", source="probe", agent_model="composer-2-fast")
    assert e.status == "pending"
    assert e.agent_model == "composer-2-fast"
    assert e.t_shirt_size == "S"
    assert e.dispatched_at is None


def test_dispatch_result_roundtrip() -> None:
    r = DispatchResult(
        task_id="t-2",
        persona_id="ux-lead",
        agent_model="composer-2-fast",
        pr_number=42,
        outcome="merged",
        duration_ms=12345,
    )
    data: dict[str, Any] = r.model_dump()
    assert data["pr_number"] == 42
    assert data["duration_ms"] == 12345
    assert data["t_shirt_size"] == "S"


def test_persona_uses_suggested_persona() -> None:
    row: dict[str, Any] = {
        "suggested_persona": "infra-ops",
        "product": "studio",
    }
    assert select_persona(row) == "infra-ops"


def test_persona_falls_back_to_product() -> None:
    row: dict[str, Any] = {"product": "axiomfolio"}
    assert select_persona(row) == "ux-lead"


def test_persona_falls_back_to_brain() -> None:
    row: dict[str, Any] = {"product": "brain"}
    assert select_persona(row) == "ops-engineer"


def test_persona_default_ops_engineer() -> None:
    row: dict[str, Any] = {"product": "unknown"}
    assert select_persona(row) == "ops-engineer"


def test_cheap_model_for_simple_task() -> None:
    row: dict[str, Any] = {
        "description": "fix typo in readme",
    }
    model = select_agent_model(row)
    assert model == "composer-2-fast"


def test_expensive_model_for_complex_task() -> None:
    row: dict[str, Any] = {
        "description": "database migration needed",
    }
    model = select_agent_model(row)
    assert model == "claude-4.6-sonnet-medium-thinking"


def test_expensive_from_error_message() -> None:
    row: dict[str, Any] = {
        "description": "probe failed",
        "error_message": "security headers missing",
    }
    model = select_agent_model(row)
    assert model == "claude-4.6-sonnet-medium-thinking"


def test_load_missing_queue(tmp_path: Path) -> None:
    result = load_dispatch_queue(
        tmp_path / "nope.json",
    )
    assert result == []


def test_load_malformed_queue(tmp_path: Path) -> None:
    p = tmp_path / "dispatch_queue.json"
    p.write_text("{bad json")
    assert load_dispatch_queue(p) == []


def test_save_and_load_queue(tmp_path: Path) -> None:
    p = tmp_path / "dispatch_queue.json"
    entries: list[dict[str, Any]] = [
        {"id": "d-1", "dispatched": False},
        {"id": "d-2", "dispatched": True},
    ]
    save_dispatch_queue(p, entries)
    loaded = load_dispatch_queue(p)
    assert len(loaded) == 2
    assert loaded[0]["id"] == "d-1"


def test_save_prunes_to_500(tmp_path: Path) -> None:
    p = tmp_path / "dispatch_queue.json"
    big: list[dict[str, Any]] = [{"id": f"d-{i}"} for i in range(600)]
    save_dispatch_queue(p, big)
    loaded = load_dispatch_queue(p)
    assert len(loaded) == 500
    assert loaded[0]["id"] == "d-100"


def test_append_dispatch_log(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    r1 = DispatchResult(
        task_id="t-1",
        persona_id="ux-lead",
        agent_model="composer-2-fast",
        outcome="dispatched",
    )
    r2 = DispatchResult(
        task_id="t-2",
        persona_id="infra-ops",
        agent_model="claude-4.6-sonnet-medium-thinking",
        outcome="dispatched",
    )
    append_dispatch_log(p, r1)
    append_dispatch_log(p, r2)
    lines = p.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    first: dict[str, Any] = json.loads(lines[0])
    assert first["task_id"] == "t-1"


def test_pending_filters_dispatched() -> None:
    entries: list[dict[str, Any]] = [
        {"id": "a", "dispatched": False},
        {"id": "b", "dispatched": True},
        {"id": "c"},
    ]
    result = pending_entries(entries)
    assert len(result) == 2
    ids = [str(e.get("id", "")) for e in result]
    assert "a" in ids
    assert "c" in ids


def test_dispatch_entry_creates_pair() -> None:
    raw: dict[str, Any] = {
        "id": "probe-dispatch-studio-20260430",
        "product": "studio",
        "suggested_persona": "ux-lead",
        "error_message": "element not found",
        "source": "probe",
    }
    entry, result = dispatch_entry(raw)
    assert isinstance(entry, DispatchEntry)
    assert isinstance(result, DispatchResult)
    assert entry.persona_id == "ux-lead"
    assert entry.agent_model == "composer-2-fast"
    assert entry.t_shirt_size == "S"
    assert entry.status == "dispatched"
    assert entry.dispatched_at is not None
    assert result.outcome == "dispatched"


def test_dispatch_entry_unknown_source_defaults() -> None:
    raw: dict[str, Any] = {
        "id": "x-1",
        "source": "unknown_source",
    }
    entry, _result = dispatch_entry(raw)
    assert entry.source == "probe"


def _write_queue(
    path: Path,
    entries: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema": "dispatch_queue/v1",
        "entries": entries,
    }
    path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def test_sync_dispatch_processes_pending(
    tmp_path: Path,
) -> None:
    q = tmp_path / "dispatch_queue.json"
    log = tmp_path / "log.jsonl"
    _write_queue(
        q,
        [
            {
                "id": "d-1",
                "product": "axiomfolio",
                "error_message": "selector fail",
                "dispatched": False,
            },
            {
                "id": "d-2",
                "product": "brain",
                "error_message": "database error",
                "dispatched": False,
            },
        ],
    )

    count = run_autopilot_dispatch_sync(
        queue_path=q,
        log_path=log,
    )
    assert count == 2

    reloaded = load_dispatch_queue(q)
    for e in reloaded:
        assert e["dispatched"] is True
        assert "dispatched_at" in e
        assert "assigned_persona" in e

    lines = log.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    first: dict[str, Any] = json.loads(lines[0])
    assert first["persona_id"] == "ux-lead"
    assert first["agent_model"] in ("composer-2-fast", "claude-4.6-sonnet-medium-thinking")

    second: dict[str, Any] = json.loads(lines[1])
    assert second["persona_id"] == "ops-engineer"
    assert second["agent_model"] in ("composer-2-fast", "claude-4.6-sonnet-medium-thinking")


def test_sync_dispatch_skips_already_dispatched(
    tmp_path: Path,
) -> None:
    q = tmp_path / "dispatch_queue.json"
    log = tmp_path / "log.jsonl"
    _write_queue(
        q,
        [{"id": "d-1", "dispatched": True}],
    )
    count = run_autopilot_dispatch_sync(
        queue_path=q,
        log_path=log,
    )
    assert count == 0
    assert not log.exists()


def test_sync_dispatch_empty_queue(
    tmp_path: Path,
) -> None:
    q = tmp_path / "dispatch_queue.json"
    log = tmp_path / "log.jsonl"
    count = run_autopilot_dispatch_sync(
        queue_path=q,
        log_path=log,
    )
    assert count == 0


def test_install_registers_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == JOB_ID
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab(
        "*/5 * * * *",
        timezone="UTC",
    )
    assert t.fields == ref.fields


# ---------------------------------------------------------------------------
# Wave L: T-Shirt size enforcement tests
# ---------------------------------------------------------------------------


def test_select_agent_model_explicit_slug_xs() -> None:
    """Queue entry with explicit cheap model slug bypasses heuristics."""
    row: dict[str, Any] = {"agent_model": "composer-1.5"}
    assert select_agent_model(row) == "composer-1.5"


def test_select_agent_model_explicit_slug_l() -> None:
    row: dict[str, Any] = {"agent_model": "claude-4.6-sonnet-medium-thinking"}
    assert select_agent_model(row) == "claude-4.6-sonnet-medium-thinking"


def test_select_agent_model_explicit_size_xs() -> None:
    row: dict[str, Any] = {"t_shirt_size": "xs"}
    assert select_agent_model(row) == "composer-1.5"


def test_select_agent_model_explicit_size_m() -> None:
    row: dict[str, Any] = {"t_shirt_size": "m"}
    assert select_agent_model(row) == "gpt-5.5-medium"


def test_select_agent_model_never_returns_opus() -> None:
    """Ensure no input can cause the dispatcher to return an Opus model."""
    opus_inputs = [
        {"agent_model": "claude-4.5-opus-high-thinking"},
        {"agent_model": "opus"},
        {"agent_model": "claude-opus-4-7-thinking-xhigh"},
    ]
    for row in opus_inputs:
        model = select_agent_model(row)
        assert "opus" not in model.lower(), f"Dispatcher returned Opus model for {row}: {model}"


def test_dispatch_entry_sets_t_shirt_size() -> None:
    """dispatch_entry must produce an entry with t_shirt_size set from model."""
    raw: dict[str, Any] = {
        "id": "test-size",
        "description": "generate scaffold",
        "agent_model": "composer-1.5",
        "source": "manual",
    }
    entry, result = dispatch_entry(raw)
    assert entry.t_shirt_size == "XS"
    assert result.t_shirt_size == "XS"


def test_dispatched_queue_entry_has_t_shirt_size(tmp_path: Path) -> None:
    """run_autopilot_dispatch_sync writes t_shirt_size to queue entries."""
    q = tmp_path / "q.json"
    log = tmp_path / "log.jsonl"
    _write_queue(q, [{"id": "e-1", "description": "stub readme", "agent_model": "composer-1.5"}])
    run_autopilot_dispatch_sync(queue_path=q, log_path=log)
    loaded = load_dispatch_queue(q)
    assert loaded[0].get("t_shirt_size") == "XS"
