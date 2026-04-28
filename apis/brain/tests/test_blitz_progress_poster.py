from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.services import blitz_progress_poster


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_hourly_summary_contains_queue_depth_and_workstream_changes(
    tmp_path: Path, monkeypatch
) -> None:
    _write_json(
        tmp_path / "apis/brain/data/merge_queue.json",
        {
            "queue": [{"pr": 402}],
            "current": {"pr": 401, "branch": "feat/ws-42"},
            "history": [{"pr": 400, "status": "merged"}],
            "updated_at": "2026-04-28T23:30:00Z",
        },
    )
    _write_json(
        tmp_path / "apps/studio/src/data/workstreams.json",
        {
            "version": 1,
            "workstreams": [
                {
                    "id": "WS-42",
                    "status": "in_progress",
                    "percent_done": 50,
                    "last_activity": "2026-04-28T23:45:00Z",
                }
            ],
        },
    )
    (tmp_path / "apis/brain/data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "apis/brain/data/procedural_memory.yaml").write_text(
        """
version: 1
rules:
  - id: queue_head_only
    do: merge only from queue head
    learned_at: "2026-04-28T23:40:00Z"
""",
        encoding="utf-8",
    )

    def fake_run(args: list[str], cwd: Path) -> str:
        if args[:2] == ["git", "log"]:
            return "2026-04-28T23:50:00+00:00\tMerge pull request #401 from feat/ws-42\n"
        if args[:3] == ["gh", "pr", "view"]:
            return "MERGED\thttps://github.com/paperwork-labs/paperwork/pull/401\n"
        return ""

    monkeypatch.setattr(blitz_progress_poster, "_run_command", fake_run)

    summary = blitz_progress_poster.compose_hourly_progress_summary(
        root=tmp_path,
        now=datetime(2026, 4, 29, 0, 0, tzinfo=UTC),
    )

    assert "## Rebase Queue" in summary
    assert "- Queue depth: 1" in summary
    assert "## Workstream Status Changes" in summary
    assert "WS-42: status=in_progress" in summary
    assert "PR #401" in summary
    assert "queue_head_only" in summary


def test_hourly_summary_handles_empty_log_gracefully(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "apis/brain/data/merge_queue.json",
        {"queue": [], "current": None, "history": [], "updated_at": None},
    )
    _write_json(
        tmp_path / "apps/studio/src/data/workstreams.json",
        {"version": 1, "workstreams": []},
    )
    (tmp_path / "apis/brain/data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "apis/brain/data/procedural_memory.yaml").write_text(
        "version: 1\nrules: []\n",
        encoding="utf-8",
    )

    def empty_run(_args: list[str], _cwd: Path) -> str:
        return ""

    monkeypatch.setattr(blitz_progress_poster, "_run_command", empty_run)

    summary = blitz_progress_poster.compose_hourly_progress_summary(
        root=tmp_path,
        now=datetime(2026, 4, 29, 0, 0, tzinfo=UTC),
    )

    assert "- No PR merges found in git log for this window." in summary
    assert "- No workstream status changes found in this window." in summary
    assert "- Queue depth: 0" in summary
