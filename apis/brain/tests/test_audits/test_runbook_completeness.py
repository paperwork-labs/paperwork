"""Tests for runbook completeness audit.

medallion: ops
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.audits import runbook_completeness as rc
from app.audits.runbook_completeness import COMPLETENESS_ALERT_THRESHOLD, audit_runbooks

_GOOD_RUNBOOK = """---
doc_kind: runbook
owner: ops
last_reviewed: 2026-04-01
---

# Good

## Purpose
Why.

## Prerequisites
N/A.

## Steps
1. Do the thing.

## Verification
It works.

## Rollback
Revert.
"""


def _write(p: Path, rel: str, text: str) -> Path:
    full = p / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text, encoding="utf-8")
    return full


def test_complete_runbook_zero_gaps(tmp_path: Path) -> None:
    _write(tmp_path, "docs/runbooks/ok.md", _GOOD_RUNBOOK)
    r = audit_runbooks(tmp_path)
    assert r.total == 1
    assert r.complete == 1
    assert r.completeness_pct == 100.0
    assert r.per_doc[0].gaps == []


def test_missing_section_emits_expected_gap(tmp_path: Path) -> None:
    bad = _GOOD_RUNBOOK.replace("## Rollback", "## NotRollback")
    _write(tmp_path, "docs/runbooks/bad.md", bad)
    r = audit_runbooks(tmp_path)
    assert r.complete == 0
    assert any("missing-section-rollback-or-recovery" in g for g in r.per_doc[0].gaps)


def test_missing_frontmatter(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/runbooks/nofm.md",
        "# X\n\n## Purpose\nx\n## Prerequisites\nx\n## Steps\n1.\n## Verification\nx\n## Rollback\nx\n",
    )
    r = audit_runbooks(tmp_path)
    assert "missing-frontmatter" in r.per_doc[0].gaps


def test_missing_required_frontmatter_field(tmp_path: Path) -> None:
    partial = """---
doc_kind: runbook
owner: ops
---

## Purpose
x
## Prerequisites
x
## Steps
1. x
## Verification
x
## Rollback
x
"""
    _write(tmp_path, "docs/runbooks/partial.md", partial)
    r = audit_runbooks(tmp_path)
    assert "missing-frontmatter-last_reviewed" in r.per_doc[0].gaps


def test_aggregate_pct_two_files_one_complete(tmp_path: Path) -> None:
    _write(tmp_path, "docs/runbooks/ok.md", _GOOD_RUNBOOK)
    _write(
        tmp_path,
        "docs/runbooks/bad.md",
        "# n\n",  # almost everything missing
    )
    r = audit_runbooks(tmp_path)
    assert r.total == 2
    assert r.complete == 1
    assert r.completeness_pct == 50.0


def test_run_opens_conversation_when_below_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRAIN_RUNBOOK_REPO_ROOT", str(tmp_path))
    _write(tmp_path, "docs/runbooks/a.md", "# only")
    _write(tmp_path, "docs/runbooks/b.md", "# only")
    created: list[object] = []

    def fake_create(_c: object) -> None:
        created.append(_c)

    with patch.object(rc, "create_conversation", side_effect=fake_create):
        run = rc.run()
    assert run.audit_id == "runbook_completeness"
    assert created, "expected debt conversation when completeness < threshold"
    r = audit_runbooks(tmp_path)
    assert r.completeness_pct < COMPLETENESS_ALERT_THRESHOLD


def test_run_no_conversation_at_or_above_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRAIN_RUNBOOK_REPO_ROOT", str(tmp_path))
    for name in ("a.md", "b.md", "c.md", "d.md", "e.md"):
        _write(tmp_path, f"docs/runbooks/{name}", _GOOD_RUNBOOK)
    created: list[object] = []

    def fake_create(_c: object) -> None:
        created.append(_c)

    with patch.object(rc, "create_conversation", side_effect=fake_create):
        rc.run()
    assert not created
