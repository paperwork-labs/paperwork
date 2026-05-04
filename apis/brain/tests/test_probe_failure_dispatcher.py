"""Tests for probe_failure_dispatcher (Wave PROBE PR-PB4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.schedulers.probe_failure_dispatcher import (
    JOB_ID,
    build_dispatch_entries,
    filter_recent_failures,
    install,
    load_dispatch_queue,
    load_probe_results,
    save_dispatch_queue,
    suggest_persona,
)

# -------------------------------------------------------------------
# suggest_persona
# -------------------------------------------------------------------


def test_infra_error_maps_to_infra_ops() -> None:
    assert suggest_persona("infrastructure_error", "", []) == "infra-ops"


def test_timeout_maps_to_infra_ops() -> None:
    assert suggest_persona("timeout", "", []) == "infra-ops"


def test_failure_maps_to_ux_lead() -> None:
    assert suggest_persona("failure", "", []) == "ux-lead"


def test_500_keyword_in_error_maps_to_infra_ops() -> None:
    assert suggest_persona("unknown", "HTTP 500 server error", []) == "infra-ops"


def test_selector_keyword_maps_to_ux_lead() -> None:
    assert suggest_persona("unknown", "element not found on page", []) == "ux-lead"


def test_failing_test_error_keyword_overrides_default() -> None:
    tests: list[dict[str, Any]] = [
        {"title": "homepage", "error": "503 Service Unavailable"},
    ]
    assert suggest_persona("unknown", "", tests) == "infra-ops"


def test_default_persona_is_ux_lead() -> None:
    assert suggest_persona("unknown", "some random error", []) == "ux-lead"


# -------------------------------------------------------------------
# load_probe_results
# -------------------------------------------------------------------


def test_load_missing_file(tmp_path: Path) -> None:
    assert load_probe_results(tmp_path / "nope.json") == []


def test_load_valid_file(tmp_path: Path) -> None:
    p = tmp_path / "probe_results.json"
    p.write_text(
        json.dumps({"results": [{"product": "studio", "status": "pass"}]}),
    )
    rows = load_probe_results(p)
    assert len(rows) == 1
    assert rows[0]["product"] == "studio"


def test_load_malformed_json(tmp_path: Path) -> None:
    p = tmp_path / "probe_results.json"
    p.write_text("{bad json")
    assert load_probe_results(p) == []


# -------------------------------------------------------------------
# filter_recent_failures
# -------------------------------------------------------------------


def _make_row(
    product: str,
    status: str,
    minutes_ago: int,
    now: datetime,
) -> dict[str, Any]:
    ts = now - timedelta(minutes=minutes_ago)
    return {
        "product": product,
        "status": status,
        "started_at": ts.isoformat().replace("+00:00", "Z"),
    }


def test_filter_recent_failures_basic() -> None:
    now = datetime.now(UTC)
    rows = [
        _make_row("filefree", "failure", 30, now),
        _make_row("studio", "pass", 10, now),
        _make_row("distill", "infrastructure_error", 90, now),
    ]
    failures = filter_recent_failures(rows, window_minutes=60, now=now)
    assert len(failures) == 1
    assert failures[0]["product"] == "filefree"


def test_filter_excludes_pass_and_skipped() -> None:
    now = datetime.now(UTC)
    rows = [
        _make_row("filefree", "pass", 10, now),
        _make_row("studio", "skipped", 10, now),
    ]
    failures = filter_recent_failures(rows, window_minutes=60, now=now)
    assert failures == []


def test_filter_includes_edge_of_window() -> None:
    now = datetime.now(UTC)
    rows = [_make_row("studio", "failure", 59, now)]
    failures = filter_recent_failures(rows, window_minutes=60, now=now)
    assert len(failures) == 1


def test_filter_excludes_beyond_window() -> None:
    now = datetime.now(UTC)
    rows = [_make_row("studio", "failure", 61, now)]
    failures = filter_recent_failures(rows, window_minutes=60, now=now)
    assert failures == []


# -------------------------------------------------------------------
# build_dispatch_entries
# -------------------------------------------------------------------


def test_build_dispatch_entries_creates_entries() -> None:
    now = datetime.now(UTC)
    failures = [
        {
            "product": "filefree",
            "status": "failure",
            "started_at": now.isoformat(),
            "error_message": "element not found",
            "failing_tests": [],
        },
    ]
    entries = build_dispatch_entries(failures)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["product"] == "filefree"
    assert entry["suggested_persona"] == "ux-lead"
    assert entry["dispatched"] is False
    assert entry["id"].startswith("probe-dispatch-filefree-")


def test_build_dispatch_deduplicates_same_product_status() -> None:
    now = datetime.now(UTC)
    failures = [
        {
            "product": "studio",
            "status": "failure",
            "started_at": now.isoformat(),
            "error_message": "err1",
        },
        {
            "product": "studio",
            "status": "failure",
            "started_at": now.isoformat(),
            "error_message": "err2",
        },
    ]
    entries = build_dispatch_entries(failures)
    assert len(entries) == 1


def test_build_dispatch_uses_failing_test_error_as_fallback() -> None:
    now = datetime.now(UTC)
    failures = [
        {
            "product": "axiomfolio",
            "status": "failure",
            "started_at": now.isoformat(),
            "error_message": "",
            "failing_tests": [
                {"title": "homepage loads", "error": "timeout waiting"},
            ],
        },
    ]
    entries = build_dispatch_entries(failures)
    assert len(entries) == 1
    assert "timeout waiting" in entries[0]["error_message"]


# -------------------------------------------------------------------
# dispatch queue persistence
# -------------------------------------------------------------------


def test_save_and_load_dispatch_queue(tmp_path: Path) -> None:
    p = tmp_path / "dispatch_queue.json"
    entries: list[dict[str, Any]] = [
        {"id": "d-1", "product": "filefree", "dispatched": False},
    ]
    save_dispatch_queue(p, entries)
    loaded = load_dispatch_queue(p)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "d-1"


def test_load_dispatch_queue_missing_file(tmp_path: Path) -> None:
    assert load_dispatch_queue(tmp_path / "nope.json") == []


def test_save_dispatch_queue_prunes_to_500(tmp_path: Path) -> None:
    p = tmp_path / "dispatch_queue.json"
    entries: list[dict[str, Any]] = [{"id": f"d-{i}"} for i in range(600)]
    save_dispatch_queue(p, entries)
    loaded = load_dispatch_queue(p)
    assert len(loaded) == 500
    assert loaded[0]["id"] == "d-100"


# -------------------------------------------------------------------
# install
# -------------------------------------------------------------------


def test_install_registers_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == JOB_ID
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("*/15 * * * *", timezone="UTC")
    assert t.fields == ref.fields


# -------------------------------------------------------------------
# Path resolution (Wave 0 fix: parents[4] crashed in /app container).
# Path helper itself is exhaustively covered in test_paths.py; here we only
# verify the dispatcher's env-override pass-through still works.
# -------------------------------------------------------------------


def test_probe_results_path_env_override_wins(monkeypatch, tmp_path: Path) -> None:
    from app.schedulers import probe_failure_dispatcher as mod

    explicit = tmp_path / "custom_probe.json"
    monkeypatch.setenv("BRAIN_PROBE_RESULTS_JSON", str(explicit))
    assert mod._probe_results_path() == explicit


def test_dispatch_queue_path_env_override_wins(monkeypatch, tmp_path: Path) -> None:
    from app.schedulers import probe_failure_dispatcher as mod

    explicit = tmp_path / "custom_queue.json"
    monkeypatch.setenv("BRAIN_DISPATCH_QUEUE_JSON", str(explicit))
    assert mod._dispatch_queue_path() == explicit


def test_probe_results_path_default_uses_canonical_brain_data_dir(
    monkeypatch, tmp_path: Path
) -> None:
    """Without ``BRAIN_PROBE_RESULTS_JSON``, path comes from ``brain_data_dir()``."""
    from app.schedulers import probe_failure_dispatcher as mod

    monkeypatch.delenv("BRAIN_PROBE_RESULTS_JSON", raising=False)
    target = tmp_path / "brain-data"
    target.mkdir()
    monkeypatch.setenv("BRAIN_DATA_DIR", str(target))
    assert mod._probe_results_path() == target / "probe_results.json"
