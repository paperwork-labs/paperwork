"""Line-range semantics for AgentBrain._tool_read_file (PR review: end_line without start_line)."""

import os
from unittest.mock import MagicMock

import pytest

from backend.services.agent.brain import AgentBrain


@pytest.fixture
def brain() -> AgentBrain:
    return AgentBrain(db=MagicMock())


@pytest.fixture
def repo_root() -> str:
    """Repository root (parent of backend/). _tool_read_file resolves base via relative ``backend/``."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_read_file_end_line_only_reads_from_line_one(
    brain: AgentBrain, repo_root: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo_root)
    r = await brain._tool_read_file(
        "tests/fixtures/agent_read_file_sample.txt",
        start_line=None,
        end_line=2,
    )
    assert "error" not in r
    assert r["showing_lines"] == "1-2"
    assert r["content"].splitlines() == ["line1", "line2"]


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_read_file_rejects_end_before_start(
    brain: AgentBrain, repo_root: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo_root)
    r = await brain._tool_read_file(
        "tests/fixtures/agent_read_file_sample.txt",
        start_line=4,
        end_line=2,
    )
    assert r.get("error")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_read_file_start_only_to_eof(
    brain: AgentBrain, repo_root: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo_root)
    r = await brain._tool_read_file(
        "tests/fixtures/agent_read_file_sample.txt",
        start_line=4,
        end_line=None,
    )
    assert "error" not in r
    assert r["showing_lines"] == "4-5"
    assert r["content"].splitlines() == ["line4", "line5"]
