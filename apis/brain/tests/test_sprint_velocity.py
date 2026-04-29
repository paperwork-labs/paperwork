"""Tests for sprint_velocity service (WS-51).

Covers:
- Bootstrap (empty pr_outcomes + no completed workstreams -> measured=False)
- Single week computation with synthetic data
- by_author classification rules (founder / brain-self-dispatch / cheap-agent)
- History bounding to 26 weeks
- Scheduler registration smoke test
"""

from __future__ import annotations

import inspect
import json
import unittest.mock as mock
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from app.schemas.sprint_velocity import ByAuthor, SprintVelocityEntry, SprintVelocityFile
from app.services import sprint_velocity as sv_module
from app.services.sprint_velocity import (
    _classify_agent,
    compute_velocity,
    record_weekly_velocity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pr(
    pr_number: int,
    merged_at: str,
    merged_by_agent: str = "cheap-agent-x",
) -> dict[str, Any]:
    return {
        "pr_number": pr_number,
        "merged_at": merged_at,
        "merged_by_agent": merged_by_agent,
        "agent_model": "composer-1.5",
        "subagent_type": "cheap",
        "workstream_ids": [],
        "workstream_types": [],
        "outcomes": {},
    }


def _empty_outcomes_file() -> dict[str, Any]:
    return {"schema": "pr_outcomes/v1", "description": "test", "outcomes": []}


def _make_outcomes_file(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": "pr_outcomes/v1", "description": "test", "outcomes": outcomes}


# ---------------------------------------------------------------------------
# by_author classification
# ---------------------------------------------------------------------------


class TestClassifyAgent:
    def test_empty_string_is_founder(self) -> None:
        assert _classify_agent("") == "founder"

    def test_founder_literal(self) -> None:
        assert _classify_agent("founder") == "founder"

    def test_human_literal(self) -> None:
        assert _classify_agent("human") == "founder"

    def test_none_string(self) -> None:
        assert _classify_agent("none") == "founder"

    def test_brain_prefix(self) -> None:
        assert _classify_agent("brain-self-dispatch") == "brain-self-dispatch"

    def test_brain_arbitrary_suffix(self) -> None:
        assert _classify_agent("brain-v2-dispatch") == "brain-self-dispatch"

    def test_composer_is_cheap_agent(self) -> None:
        assert _classify_agent("composer-1.5") == "cheap-agent"

    def test_gpt_is_cheap_agent(self) -> None:
        assert _classify_agent("gpt-5.5-medium") == "cheap-agent"

    def test_unknown_is_cheap_agent(self) -> None:
        assert _classify_agent("some-random-bot") == "cheap-agent"


# ---------------------------------------------------------------------------
# Bootstrap: empty outcomes + no workstreams -> measured=False
# ---------------------------------------------------------------------------


class TestBootstrap:
    def test_measured_false_when_no_data(self, tmp_path: Path) -> None:
        """Bootstrap scenario: pr_outcomes empty, no completed workstreams -> measured=False."""
        velocity_json = tmp_path / "sprint_velocity.json"
        outcomes_json = tmp_path / "pr_outcomes.json"
        outcomes_json.write_text(json.dumps(_empty_outcomes_file()))

        with (
            mock.patch.object(
                sv_module, "sprint_velocity_file_path", return_value=str(velocity_json)
            ),
            mock.patch.object(sv_module, "_brain_data_dir", return_value=str(tmp_path)),
            mock.patch.object(sv_module, "_completed_workstreams_in_week", return_value=[]),
            mock.patch.object(sv_module, "_monorepo_root", return_value="/fake/root"),
        ):
            entry = compute_velocity(week_offset=0)

        assert entry.measured is False
        assert entry.prs_merged == 0
        assert entry.workstreams_completed == 0
        assert "bootstrap" in entry.notes.lower()

    def test_measured_false_bails_before_recording(self, tmp_path: Path) -> None:
        """record_weekly_velocity still writes when measured=False (history is preserved)."""
        velocity_json = tmp_path / "sprint_velocity.json"

        with (
            mock.patch.object(
                sv_module, "sprint_velocity_file_path", return_value=str(velocity_json)
            ),
            mock.patch.object(sv_module, "_brain_data_dir", return_value=str(tmp_path)),
            mock.patch.object(sv_module, "_completed_workstreams_in_week", return_value=[]),
            mock.patch.object(sv_module, "_monorepo_root", return_value="/fake/root"),
        ):
            entry = record_weekly_velocity()

        assert entry.measured is False
        assert velocity_json.exists()
        blob = SprintVelocityFile.model_validate(json.loads(velocity_json.read_text()))
        assert blob.current is not None
        assert blob.current.measured is False


# ---------------------------------------------------------------------------
# Single week computation with synthetic data
# ---------------------------------------------------------------------------


class TestComputeVelocity:
    def test_prs_merged_count(self, tmp_path: Path) -> None:
        week_start = datetime(2026, 4, 21, tzinfo=UTC)
        week_end = datetime(2026, 4, 27, 23, 59, 59, tzinfo=UTC)

        prs = [
            _pr(101, "2026-04-22T10:00:00Z", "founder"),
            _pr(102, "2026-04-23T11:00:00Z", "brain-self-dispatch"),
            _pr(103, "2026-04-24T12:00:00Z", "composer-1.5"),
            _pr(104, "2026-04-25T13:00:00Z", "composer-1.5"),
        ]
        outcomes_file = tmp_path / "pr_outcomes.json"
        outcomes_file.write_text(json.dumps(_make_outcomes_file(prs)))

        with (
            mock.patch.object(sv_module, "_brain_data_dir", return_value=str(tmp_path)),
            mock.patch.object(sv_module, "_week_window", return_value=(week_start, week_end)),
            mock.patch.object(sv_module, "_completed_workstreams_in_week", return_value=[]),
            mock.patch.object(sv_module, "_monorepo_root", return_value="/fake/root"),
        ):
            entry = compute_velocity(week_offset=0)

        assert entry.prs_merged == 4
        assert entry.measured is True

    def test_prs_outside_week_excluded(self, tmp_path: Path) -> None:
        week_start = datetime(2026, 4, 21, tzinfo=UTC)
        week_end = datetime(2026, 4, 27, 23, 59, 59, tzinfo=UTC)

        prs = [
            _pr(100, "2026-04-20T23:59:00Z", "composer-1.5"),  # before window
            _pr(101, "2026-04-22T10:00:00Z", "composer-1.5"),  # in window
            _pr(102, "2026-04-28T00:01:00Z", "composer-1.5"),  # after window
        ]
        outcomes_file = tmp_path / "pr_outcomes.json"
        outcomes_file.write_text(json.dumps(_make_outcomes_file(prs)))

        with (
            mock.patch.object(sv_module, "_brain_data_dir", return_value=str(tmp_path)),
            mock.patch.object(sv_module, "_week_window", return_value=(week_start, week_end)),
            mock.patch.object(sv_module, "_completed_workstreams_in_week", return_value=[]),
            mock.patch.object(sv_module, "_monorepo_root", return_value="/fake/root"),
        ):
            entry = compute_velocity(week_offset=0)

        assert entry.prs_merged == 1

    def test_throughput_per_day(self, tmp_path: Path) -> None:
        week_start = datetime(2026, 4, 21, tzinfo=UTC)
        week_end = datetime(2026, 4, 27, 23, 59, 59, tzinfo=UTC)

        prs = [_pr(i, f"2026-04-{21 + i % 6:02d}T10:00:00Z", "composer-1.5") for i in range(7)]
        outcomes_file = tmp_path / "pr_outcomes.json"
        outcomes_file.write_text(json.dumps(_make_outcomes_file(prs)))

        with (
            mock.patch.object(sv_module, "_brain_data_dir", return_value=str(tmp_path)),
            mock.patch.object(sv_module, "_week_window", return_value=(week_start, week_end)),
            mock.patch.object(sv_module, "_completed_workstreams_in_week", return_value=[]),
            mock.patch.object(sv_module, "_monorepo_root", return_value="/fake/root"),
        ):
            entry = compute_velocity(week_offset=0)

        assert entry.throughput_per_day == round(7 / 7.0, 2)

    def test_story_points_from_workstreams(self, tmp_path: Path) -> None:
        week_start = datetime(2026, 4, 21, tzinfo=UTC)
        week_end = datetime(2026, 4, 27, 23, 59, 59, tzinfo=UTC)

        prs = [_pr(101, "2026-04-22T10:00:00Z", "composer-1.5")]
        outcomes_file = tmp_path / "pr_outcomes.json"
        outcomes_file.write_text(json.dumps(_make_outcomes_file(prs)))

        completed_ws = [("WS-10", 2), ("WS-11", 3)]

        with (
            mock.patch.object(sv_module, "_brain_data_dir", return_value=str(tmp_path)),
            mock.patch.object(sv_module, "_week_window", return_value=(week_start, week_end)),
            mock.patch.object(
                sv_module, "_completed_workstreams_in_week", return_value=completed_ws
            ),
            mock.patch.object(sv_module, "_monorepo_root", return_value="/fake/root"),
        ):
            entry = compute_velocity(week_offset=0)

        assert entry.workstreams_completed == 2
        assert entry.workstreams_completed_estimated_pr_count == 5
        assert entry.story_points_burned == 5


# ---------------------------------------------------------------------------
# by_author classification rules
# ---------------------------------------------------------------------------


class TestByAuthorClassification:
    def _compute_with_prs(
        self,
        tmp_path: Path,
        prs: list[dict[str, Any]],
    ) -> ByAuthor:
        week_start = datetime(2026, 4, 21, tzinfo=UTC)
        week_end = datetime(2026, 4, 27, 23, 59, 59, tzinfo=UTC)
        outcomes_file = tmp_path / "pr_outcomes.json"
        outcomes_file.write_text(json.dumps(_make_outcomes_file(prs)))

        with (
            mock.patch.object(sv_module, "_brain_data_dir", return_value=str(tmp_path)),
            mock.patch.object(sv_module, "_week_window", return_value=(week_start, week_end)),
            mock.patch.object(sv_module, "_completed_workstreams_in_week", return_value=[]),
            mock.patch.object(sv_module, "_monorepo_root", return_value="/fake/root"),
        ):
            entry = compute_velocity(week_offset=0)

        return entry.by_author

    def test_founder_classified_correctly(self, tmp_path: Path) -> None:
        prs = [_pr(1, "2026-04-22T10:00:00Z", "founder")]
        ba = self._compute_with_prs(tmp_path, prs)
        assert ba.founder == 1
        assert ba.brain_self_dispatch == 0
        assert ba.cheap_agent == 0

    def test_brain_self_dispatch_classified_correctly(self, tmp_path: Path) -> None:
        prs = [_pr(1, "2026-04-22T10:00:00Z", "brain-self-dispatch")]
        ba = self._compute_with_prs(tmp_path, prs)
        assert ba.brain_self_dispatch == 1
        assert ba.founder == 0
        assert ba.cheap_agent == 0

    def test_cheap_agent_classified_correctly(self, tmp_path: Path) -> None:
        prs = [_pr(1, "2026-04-22T10:00:00Z", "composer-1.5")]
        ba = self._compute_with_prs(tmp_path, prs)
        assert ba.cheap_agent == 1
        assert ba.founder == 0
        assert ba.brain_self_dispatch == 0

    def test_mixed_classification(self, tmp_path: Path) -> None:
        prs = [
            _pr(1, "2026-04-22T10:00:00Z", "founder"),
            _pr(2, "2026-04-22T11:00:00Z", "brain-self-dispatch"),
            _pr(3, "2026-04-22T12:00:00Z", "brain-v2"),
            _pr(4, "2026-04-22T13:00:00Z", "composer-1.5"),
            _pr(5, "2026-04-22T14:00:00Z", "gpt-5.5-medium"),
        ]
        ba = self._compute_with_prs(tmp_path, prs)
        assert ba.founder == 1
        assert ba.brain_self_dispatch == 2
        assert ba.cheap_agent == 2


# ---------------------------------------------------------------------------
# History bounding to 26 weeks
# ---------------------------------------------------------------------------


class TestHistoryBounding:
    def test_history_bounded_to_26_weeks(self, tmp_path: Path) -> None:
        velocity_json = tmp_path / "sprint_velocity.json"
        existing_entries = [
            SprintVelocityEntry(
                week_start=f"2025-{(i % 12) + 1:02d}-01",
                week_end=f"2025-{(i % 12) + 1:02d}-07",
                computed_at=f"2025-{(i % 12) + 1:02d}-08T00:00:00Z",
                measured=True,
            )
            for i in range(26)
        ]
        blob = SprintVelocityFile(history=existing_entries)
        velocity_json.write_text(json.dumps(blob.model_dump(mode="json", by_alias=True), indent=2))

        new_entry = SprintVelocityEntry(
            week_start="2026-07-01",
            week_end="2026-07-07",
            computed_at="2026-07-08T00:00:00Z",
            prs_merged=5,
            measured=True,
        )

        with mock.patch.object(
            sv_module, "sprint_velocity_file_path", return_value=str(velocity_json)
        ):
            record_weekly_velocity(new_entry)

        blob_after = SprintVelocityFile.model_validate(json.loads(velocity_json.read_text()))
        assert len(blob_after.history) == 26, (
            f"Expected 26 history entries (bounded), got {len(blob_after.history)}"
        )
        assert blob_after.history[-1].week_start == "2026-07-01"

    def test_history_under_26_grows_freely(self, tmp_path: Path) -> None:
        velocity_json = tmp_path / "sprint_velocity.json"
        velocity_json.write_text(
            json.dumps(SprintVelocityFile().model_dump(mode="json", by_alias=True))
        )

        for i in range(5):
            entry = SprintVelocityEntry(
                week_start=f"2026-0{i + 1:01d}-01",
                week_end=f"2026-0{i + 1:01d}-07",
                computed_at=f"2026-0{i + 1:01d}-08T00:00:00Z",
                measured=True,
            )
            with mock.patch.object(
                sv_module, "sprint_velocity_file_path", return_value=str(velocity_json)
            ):
                record_weekly_velocity(entry)

        blob = SprintVelocityFile.model_validate(json.loads(velocity_json.read_text()))
        assert len(blob.history) == 5


# ---------------------------------------------------------------------------
# Scheduler registration smoke test
# ---------------------------------------------------------------------------


class TestSchedulerRegistration:
    def test_sprint_velocity_scheduler_importable(self) -> None:
        from app.schedulers import sprint_velocity as sv_sched

        assert callable(sv_sched.install), "install() must be callable"

    def test_sprint_velocity_in_init_registry(self) -> None:
        """Verify that schedulers/__init__.py references sprint_velocity."""
        from app import schedulers as sched_pkg

        init_source = inspect.getsource(sched_pkg)
        assert "sprint_velocity" in init_source, (
            "schedulers/__init__.py must reference sprint_velocity"
        )

    def test_install_registers_job(self) -> None:
        """install() should add a job to the scheduler without error."""
        from app.schedulers.sprint_velocity import install

        mock_scheduler = MagicMock()
        install(mock_scheduler)
        mock_scheduler.add_job.assert_called_once()
        call_kwargs = mock_scheduler.add_job.call_args
        assert call_kwargs is not None
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        assert kwargs.get("id") == "sprint_velocity_weekly"
