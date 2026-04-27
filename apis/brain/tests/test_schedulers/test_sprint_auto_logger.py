"""Tests for :mod:`app.schedulers.sprint_auto_logger` parsing and markdown edits."""

from __future__ import annotations

import re
from datetime import UTC

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.schedulers import sprint_auto_logger as sal

# Acceptance shapes from ``apps/studio/src/app/admin/sprints/page.tsx`` (keep in sync).
PR_REF_RE_STUDIO = re.compile(r"(?:#|PR\s*#|pull\/)(\d{2,5})", re.I)
SHIPPED_DATE_RE_STUDIO = re.compile(r"(?:^shipped\s+|\bshipped\s+)(\d{4}-\d{2}-\d{2})", re.I)


def test_pr_ref_regex_matches_studio_token_shapes() -> None:
    for sample in ("PR #42", "#42", "pull/42", "PR #1234"):
        assert sal.PR_REF_RE.search(sample), sample
        assert PR_REF_RE_STUDIO.search(sample), sample


def test_shipped_date_regex_matches_studio() -> None:
    for sample in ("shipped 2026-04-26:", "x shipped 2026-04-26 y"):
        assert sal.SHIPPED_DATE_RE.search(sample), sample
        assert SHIPPED_DATE_RE_STUDIO.search(sample), sample


def test_sprint_paths_from_body_file_and_bare_id() -> None:
    body = """
Some text

Sprint: docs/sprints/FOO_2026Q2.md

Footer

Sprint: BAR_2026Q3
"""
    paths = sal.sprint_paths_from_body(body)
    assert paths == ["docs/sprints/FOO_2026Q2.md", "docs/sprints/BAR_2026Q3.md"]


def test_sprint_paths_from_labels() -> None:
    assert sal.sprint_paths_from_labels(["sprint:BAZ_2026Q1", "unrelated"]) == [
        "docs/sprints/BAZ_2026Q1.md",
    ]


def test_collect_sprint_paths_merges_body_and_labels_dedupes() -> None:
    body = "Sprint: docs/sprints/ZZZ.md"
    labels = ["sprint:ZZZ"]
    assert sal.collect_sprint_paths(body, labels) == ["docs/sprints/ZZZ.md"]


def test_collect_sprint_paths_rejects_unsafe_paths() -> None:
    assert sal.collect_sprint_paths("Sprint: docs/../secrets.md", []) == []


def test_strip_conventional_prefix_nested() -> None:
    assert sal.strip_conventional_prefix("feat(brain): do the thing") == "do the thing"
    assert sal.strip_conventional_prefix("chore: fix: typo") == "typo"


@pytest.mark.parametrize(
    "bullet",
    [
        "- shipped 2026-04-26: Hello world PR #42",
        "- shipped 2026-04-26: Hello pull/42",
    ],
)
def test_shipped_bullet_matches_studio_regex(bullet: str) -> None:
    assert SHIPPED_DATE_RE_STUDIO.search(bullet)
    assert PR_REF_RE_STUDIO.search(bullet)


def test_apply_sprint_file_updates_idempotent() -> None:
    doc = """---
title: T
related_prs:
  - 1
---

# Sprint

## Outcome

- _Tracking_
- shipped 2026-01-01: Old PR #1

## What we learned

- keep

## Tracker

- [ ] task
"""
    adds = [(99, "New thing", "2026-04-20")]
    first = sal.apply_sprint_file_updates(doc, adds)
    assert first is not None
    new_doc, nums = first
    assert nums == [99]
    assert "PR #99" in new_doc
    assert "What we learned" in new_doc
    assert "keep" in new_doc
    assert "## Tracker" in new_doc
    second = sal.apply_sprint_file_updates(new_doc, adds)
    assert second is None


def test_related_prs_sorted_deduped() -> None:
    doc = """---
title: T
related_prs:
  - 10
  - 5
---

## Outcome

- x

## What we learned

- y
"""
    out = sal.apply_sprint_file_updates(doc, [(99, "A", "2026-04-20")])
    assert out is not None
    new_doc, _ = out
    assert "related_prs:" in new_doc
    # yaml dump order: should include 5, 10, 99 sorted
    assert "5" in new_doc and "10" in new_doc and "99" in new_doc
    after_lines = [
        ln
        for ln in new_doc.splitlines()
        if ln.strip().startswith("- ") and ln.strip()[2:].strip().isdigit()
    ]
    nums = sorted(
        int(ln.split("-", 1)[1].strip()) for ln in after_lines if ln.strip().startswith("- ")
    )
    assert nums == [5, 10, 99]


def test_install_respects_brain_owns_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_OWNS_SPRINT_AUTO_LOGGER", raising=False)
    sched = AsyncIOScheduler(timezone="UTC")
    sal.install(sched)
    assert len(sched.get_jobs()) == 0

    monkeypatch.setenv("BRAIN_OWNS_SPRINT_AUTO_LOGGER", "true")
    sched2 = AsyncIOScheduler(timezone="UTC")
    sal.install(sched2)
    jobs = sched2.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "sprint_auto_logger"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("*/15 * * * *", timezone=UTC)
    assert t.fields == ref.fields
