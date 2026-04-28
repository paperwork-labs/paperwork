"""Sprint markdown auto-close from ``closes_pr_urls`` + ``closes_workstreams``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.schemas.workstream import Workstream, WorkstreamsFile
from app.services import sprint_md_auto_close as smac


@pytest.fixture
def completed_board() -> WorkstreamsFile:
    return WorkstreamsFile(
        version=1,
        updated="2026-04-27T12:00:00Z",
        workstreams=[
            Workstream(
                id="WS-90-testdone",
                title="Done workstream for sprint close test",
                track="Z",
                priority=0,
                status="completed",
                percent_done=100,
                owner="brain",
                brief_tag="track:sprint-close-test",
                blockers=[],
                last_pr=None,
                last_activity="2026-04-27T12:00:00Z",
                last_dispatched_at=None,
                notes="",
                estimated_pr_count=None,
                github_actions_workflow=None,
                related_plan=None,
            )
        ],
    )


@pytest.mark.asyncio
async def test_collect_updates_when_pr_merged_and_ws_completed(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    completed_board: WorkstreamsFile,
) -> None:
    root = tmp_path
    sp = root / "docs" / "sprints"
    sp.mkdir(parents=True)
    md = """---
status: active
closes_pr_urls:
  - https://github.com/paperwork-labs/paperwork/pull/999
closes_workstreams:
  - WS-90-testdone
---

# Sprint

Body
"""
    (sp / "ws-close-fixture.md").write_text(md, encoding="utf-8")

    monkeypatch.setattr(
        smac,
        "load_workstreams_file",
        lambda **_: completed_board,
    )

    async def fake_pr(n: int):
        if n == 999:
            return {"merged_at": "2026-04-01T00:00:00Z"}
        return None

    monkeypatch.setattr(smac.gh, "get_github_pull_dict", fake_pr)

    updates = await smac.collect_sprint_auto_close_updates(repo_root=root)
    rel = "docs/sprints/ws-close-fixture.md"
    assert rel in updates
    assert "status: closed" in updates[rel]
    assert "last_auto_status_check_at" in updates[rel]


@pytest.mark.asyncio
async def test_collect_skips_when_pr_not_merged(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    completed_board: WorkstreamsFile,
) -> None:
    root = tmp_path
    sp = root / "docs" / "sprints"
    sp.mkdir(parents=True)
    md = """---
status: active
closes_pr_urls:
  - https://github.com/paperwork-labs/paperwork/pull/998
closes_workstreams:
  - WS-90-testdone
---

# Sprint
"""
    (sp / "open-pr.md").write_text(md, encoding="utf-8")
    monkeypatch.setattr(smac, "load_workstreams_file", lambda **_: completed_board)
    monkeypatch.setattr(
        smac.gh,
        "get_github_pull_dict",
        AsyncMock(return_value={"merged_at": None, "state": "open"}),
    )
    updates = await smac.collect_sprint_auto_close_updates(repo_root=root)
    assert updates == {}


@pytest.mark.asyncio
async def test_collect_skips_terminal_status(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path
    sp = root / "docs" / "sprints"
    sp.mkdir(parents=True)
    md = """---
status: shipped
closes_pr_urls:
  - https://github.com/paperwork-labs/paperwork/pull/1
---

# Sprint
"""
    (sp / "already.md").write_text(md, encoding="utf-8")
    monkeypatch.setattr(
        smac,
        "load_workstreams_file",
        lambda **_: WorkstreamsFile(version=1, updated="2026-04-27T12:00:00Z", workstreams=[]),
    )
    updates = await smac.collect_sprint_auto_close_updates(repo_root=root)
    assert updates == {}
