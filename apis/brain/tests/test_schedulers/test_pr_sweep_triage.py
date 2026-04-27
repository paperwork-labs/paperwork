"""Unit tests for PR triage classifiers (stale, ready nudge, rebase gate)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services import pr_sweep_triage as t

UTC = timezone.utc


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


class TestStaleActivity:
    def test_finds_max_activity(self) -> None:
        a = t.find_last_activity_at(
            pr_updated="2026-01-10T00:00:00Z",
            last_commit="2026-01-15T12:00:00Z",
            last_issue_comment="2026-01-12T00:00:00Z",
        )
        assert a == _dt("2026-01-15T12:00:00+00:00").replace(tzinfo=UTC)

    def test_stale_after_7d(self) -> None:
        now = _dt("2026-01-20T00:00:00+00:00")
        last = now - timedelta(days=8)
        assert t.is_stale_inactive(last_activity=last, now=now) is True
        last2 = now - timedelta(days=3)
        assert t.is_stale_inactive(last_activity=last2, now=now) is False


class TestReadyNudge:
    def test_respects_24h_activity(self) -> None:
        now = _dt("2026-01-20T00:00:00+00:00")
        recent = now - timedelta(hours=1)
        assert t.should_post_ready_nudge(
            has_green_ci=True,
            last_activity_on_thread=recent,
            now=now,
            head_sha="abc",
            issue_comment_bodies=[],
        ) is False

    def test_thin_once_per_sha(self) -> None:
        now = _dt("2026-01-20T00:00:00+00:00")
        old = now - timedelta(hours=30)
        sha = "deadbeef" * 5
        bodies: list[str] = [t.format_thin_copilot_style_review(sha)]
        assert t.should_post_ready_nudge(
            has_green_ci=True,
            last_activity_on_thread=old,
            now=now,
            head_sha=sha,
            issue_comment_bodies=bodies,
        ) is False


class TestRebase:
    def test_dispatches_only_after_4h(self) -> None:
        now = _dt("2026-01-20T12:00:00+00:00")
        first = _dt("2026-01-20T00:00:00+00:00")
        assert t.should_dispatch_rebase(
            first_dirty_marked=first, now=now, rebase_already_dispatched=False, hours=4
        ) is True
        assert t.should_dispatch_rebase(
            first_dirty_marked=now - timedelta(hours=2), now=now, rebase_already_dispatched=False, hours=4
        ) is False
        assert t.should_dispatch_rebase(
            first_dirty_marked=first, now=now, rebase_already_dispatched=True, hours=4
        ) is False


class TestMergeConflict:
    def test_dirty_is_conflict(self) -> None:
        assert t.is_merge_conflict(False, "dirty") is True

    def test_mergeable_false_unknown(self) -> None:
        assert t.is_merge_conflict(False, "unknown") is True

    def test_unstable_is_not_treated_as_merge_conflict(self) -> None:
        assert t.is_merge_conflict(True, "unstable") is False
        assert t.is_merge_conflict(False, "unstable") is False
