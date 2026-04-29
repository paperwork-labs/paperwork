from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import UUID

import log_agent_dispatch

RFC3339Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _dispatch_log(tmp_path: Path) -> Path:
    path = tmp_path / "agent_dispatch_log.json"
    path.write_text(json.dumps({"dispatches": [], "updated_at": None}), encoding="utf-8")
    return path


def test_appends_dispatch_with_default_id_and_timestamp(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    path = _dispatch_log(tmp_path)
    monkeypatch.setenv("BLITZ_AGENT_DISPATCH_LOG_PATH", str(path))

    assert (
        log_agent_dispatch.main(
            [
                "--agent-id",
                "agent-a",
                "--agent-model",
                "composer-2-fast",
                "--subagent-type",
                "generalPurpose",
                "--workstream-id",
                "WS-42",
                "--branch",
                "feat/ws-42",
                "--task",
                "Implement drift detector",
            ]
        )
        == 0
    )

    assert "logged dispatch" in capsys.readouterr().out
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data["dispatches"][0]
    UUID(entry["dispatch_id"])
    assert entry["agent_id"] == "agent-a"
    assert entry["agent_model"] == "composer-2-fast"
    assert entry["workstream_id"] == "WS-42"
    assert RFC3339Z_RE.match(entry["dispatched_at"])


def test_appends_dispatch_with_explicit_id(tmp_path: Path, monkeypatch) -> None:
    path = _dispatch_log(tmp_path)
    monkeypatch.setenv("BLITZ_AGENT_DISPATCH_LOG_PATH", str(path))

    assert (
        log_agent_dispatch.main(
            [
                "--dispatch-id",
                "dispatch-1",
                "--agent-id",
                "agent-b",
                "--agent-model",
                "gpt-5.5-medium",
                "--subagent-type",
                "shell",
                "--workstream-id",
                "WS-45",
                "--success-metric",
                "PR opened",
            ]
        )
        == 0
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["dispatches"][0]["dispatch_id"] == "dispatch-1"
    assert data["dispatches"][0]["success_metric"] == "PR opened"
