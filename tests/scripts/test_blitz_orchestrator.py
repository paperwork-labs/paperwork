from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import blitz_orchestrator


def _queue_file(tmp_path: Path) -> Path:
    path = tmp_path / "merge_queue.json"
    path.write_text(
        json.dumps({"queue": [], "current": None, "history": [], "updated_at": None}),
        encoding="utf-8",
    )
    return path


def test_round_trip_enqueue_next_complete(tmp_path: Path, monkeypatch, capsys) -> None:
    path = _queue_file(tmp_path)
    monkeypatch.setenv("BLITZ_MERGE_QUEUE_PATH", str(path))

    assert (
        blitz_orchestrator.main(
            [
                "enqueue",
                "--pr",
                "401",
                "--branch",
                "feat/ws-42",
                "--agent-id",
                "agent-a",
                "--agent-model",
                "composer-2-fast",
                "--subagent-type",
                "generalPurpose",
                "--workstream-id",
                "WS-42",
            ]
        )
        == 0
    )
    assert "queue_depth=1" in capsys.readouterr().out
    assert blitz_orchestrator.main(["next"]) == 0
    assert "next PR #401" in capsys.readouterr().out
    assert blitz_orchestrator.main(["complete", "--pr", "401", "--status", "merged"]) == 0
    assert "completed PR #401 as merged" in capsys.readouterr().out

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["queue"] == []
    assert data["current"] is None
    assert data["history"][0]["pr"] == 401
    assert data["history"][0]["status"] == "merged"


def test_status_prints_expected_fields(tmp_path: Path, monkeypatch, capsys) -> None:
    path = _queue_file(tmp_path)
    path.write_text(
        json.dumps(
            {
                "queue": [{"pr": 402, "branch": "feat/ws-43"}],
                "current": {"pr": 401, "branch": "feat/ws-42", "status": "current"},
                "history": [
                    {"pr": 400, "status": "merged", "completed_at": "2026-04-28T23:00:00Z"}
                ],
                "updated_at": "2026-04-28T23:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BLITZ_MERGE_QUEUE_PATH", str(path))

    assert blitz_orchestrator.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "queue_depth: 1" in out
    assert "current: PR #401" in out
    assert "last_completed_count: 1" in out


def test_concurrent_enqueues_do_not_corrupt_file(tmp_path: Path) -> None:
    path = _queue_file(tmp_path)
    script = Path(__file__).resolve().parents[2] / "scripts" / "blitz_orchestrator.py"
    env = {**os.environ, "BLITZ_MERGE_QUEUE_PATH": str(path)}
    commands = [
        [
            sys.executable,
            str(script),
            "enqueue",
            "--pr",
            str(500 + i),
            "--branch",
            f"feat/ws-{i}",
            "--agent-id",
            f"agent-{i}",
            "--agent-model",
            "composer-2-fast",
            "--subagent-type",
            "generalPurpose",
            "--workstream-id",
            f"WS-{i}",
        ]
        for i in range(8)
    ]
    procs = [
        subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for cmd in commands
    ]
    for proc in procs:
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0, (stdout.decode(), stderr.decode())

    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["queue"]) == 8
    assert sorted(item["pr"] for item in data["queue"]) == list(range(500, 508))
