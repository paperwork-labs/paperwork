"""Unit tests for apis/brain/app/schedulers/visual_regression.py.

Tests mock screenshot capture and pixel diff since no real browser is required.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.schedulers import visual_regression

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_prod_urls(tmp_path: Path) -> Path:
    p = tmp_path / "production-urls.json"
    p.write_text(
        json.dumps(
            {
                "filefree": "https://filefree.ai",
                "axiomfolio": "https://axiomfolio.com",
                "launchfree": "https://launchfree.ai",
                "distill": "https://distill.ai",
                "studio": "https://studio.paperworklabs.com",
            }
        ),
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# capture_screenshot placeholder
# ---------------------------------------------------------------------------


def test_capture_screenshot_returns_false() -> None:
    """Placeholder capture_screenshot returns False (not implemented)."""
    from pathlib import Path

    result = visual_regression.capture_screenshot(
        "https://filefree.ai", Path("/tmp/screenshot.png")
    )
    assert result is False


# ---------------------------------------------------------------------------
# compute_pixel_diff placeholder
# ---------------------------------------------------------------------------


def test_compute_pixel_diff_returns_zero() -> None:
    """Placeholder compute_pixel_diff returns 0.0 (no diff)."""
    from pathlib import Path

    result = visual_regression.compute_pixel_diff(
        Path("/tmp/a.png"), Path("/tmp/b.png"), Path("/tmp/diff.png")
    )
    assert result == 0.0


# ---------------------------------------------------------------------------
# images_are_identical
# ---------------------------------------------------------------------------


def test_images_are_identical_same_content(tmp_path: Path) -> None:
    """Two files with identical content are considered identical."""
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    content = b"fake image content"
    a.write_bytes(content)
    b.write_bytes(content)

    assert visual_regression.images_are_identical(a, b) is True


def test_images_are_identical_different_content(tmp_path: Path) -> None:
    """Two files with different content are not identical."""
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    a.write_bytes(b"content A")
    b.write_bytes(b"content B")

    assert visual_regression.images_are_identical(a, b) is False


def test_images_are_identical_missing_file(tmp_path: Path) -> None:
    """Missing file returns False (not identical)."""
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    a.write_bytes(b"content")

    assert visual_regression.images_are_identical(a, b) is False


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------


def test_save_results_prunes_to_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """results.json is pruned to RESULTS_LIMIT entries."""
    monkeypatch.setattr(visual_regression, "_RESULTS_JSON", tmp_path / "results.json")
    monkeypatch.setattr(visual_regression, "RESULTS_LIMIT", 5)

    results = [{"product": f"p{i}", "status": "pass"} for i in range(10)]
    visual_regression._save_results(results)

    saved = json.loads((tmp_path / "results.json").read_text())
    assert len(saved["results"]) == 5
    assert saved["results"][0]["product"] == "p5"


def test_append_result_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_append_result creates the file if it doesn't exist."""
    results_path = tmp_path / "results.json"
    monkeypatch.setattr(visual_regression, "_RESULTS_JSON", results_path)

    assert not results_path.exists()
    visual_regression._append_result({"product": "filefree", "status": "pass"})
    assert results_path.exists()

    saved = json.loads(results_path.read_text())
    assert saved["results"][0]["product"] == "filefree"


def test_load_results_handles_corrupt_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Corrupt results.json returns empty list (fresh start)."""
    results_path = tmp_path / "results.json"
    results_path.write_text("not valid json", encoding="utf-8")
    monkeypatch.setattr(visual_regression, "_RESULTS_JSON", results_path)

    results = visual_regression._load_results()
    assert results == []


# ---------------------------------------------------------------------------
# _run_comparison
# ---------------------------------------------------------------------------


def test_run_comparison_skipped_when_capture_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When screenshot capture fails, status=skipped."""
    monkeypatch.setattr(visual_regression, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(visual_regression, "_BASELINES_DIR", tmp_path / "baselines")
    monkeypatch.setattr(visual_regression, "_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(visual_regression, "_DIFFS_DIR", tmp_path / "diffs")

    row = visual_regression._run_comparison("filefree", "/", "https://filefree.ai")

    assert row["status"] == "skipped"
    assert row["reason"] == "screenshot_capture_not_implemented"
    assert row["product"] == "filefree"
    assert row["page"] == "/"


def test_run_comparison_baseline_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When no baseline exists and capture succeeds, baseline is created."""
    monkeypatch.setattr(visual_regression, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(visual_regression, "_BASELINES_DIR", tmp_path / "baselines")
    monkeypatch.setattr(visual_regression, "_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(visual_regression, "_DIFFS_DIR", tmp_path / "diffs")

    def mock_capture(url: str, output_path: visual_regression.Path) -> bool:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake screenshot")
        return True

    with patch.object(visual_regression, "capture_screenshot", side_effect=mock_capture):
        row = visual_regression._run_comparison("filefree", "/", "https://filefree.ai")

    assert row["status"] == "baseline_created"
    assert "baseline_path" in row


def test_run_comparison_pass_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When snapshot matches baseline exactly, status=pass."""
    baselines = tmp_path / "baselines"
    snapshots = tmp_path / "snapshots"
    diffs = tmp_path / "diffs"
    baselines.mkdir()
    snapshots.mkdir()
    diffs.mkdir()

    monkeypatch.setattr(visual_regression, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(visual_regression, "_BASELINES_DIR", baselines)
    monkeypatch.setattr(visual_regression, "_SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr(visual_regression, "_DIFFS_DIR", diffs)

    baseline = baselines / "filefree_home.png"
    baseline.write_bytes(b"identical content")

    def mock_capture(url: str, output_path: visual_regression.Path) -> bool:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"identical content")
        return True

    with patch.object(visual_regression, "capture_screenshot", side_effect=mock_capture):
        row = visual_regression._run_comparison("filefree", "/", "https://filefree.ai")

    assert row["status"] == "pass"
    assert row["diff_percent"] == 0.0


def test_run_comparison_regression_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When diff exceeds threshold, status=regression."""
    baselines = tmp_path / "baselines"
    snapshots = tmp_path / "snapshots"
    diffs = tmp_path / "diffs"
    baselines.mkdir()
    snapshots.mkdir()
    diffs.mkdir()

    monkeypatch.setattr(visual_regression, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(visual_regression, "_BASELINES_DIR", baselines)
    monkeypatch.setattr(visual_regression, "_SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr(visual_regression, "_DIFFS_DIR", diffs)
    monkeypatch.setattr(visual_regression, "DIFF_THRESHOLD_PERCENT", 0.5)

    baseline = baselines / "filefree_home.png"
    baseline.write_bytes(b"original content")

    def mock_capture(url: str, output_path: visual_regression.Path) -> bool:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"different content")
        return True

    def mock_diff(
        baseline_path: visual_regression.Path,
        snapshot_path: visual_regression.Path,
        diff_output_path: visual_regression.Path,
    ) -> float:
        return 5.0

    with (
        patch.object(visual_regression, "capture_screenshot", side_effect=mock_capture),
        patch.object(visual_regression, "compute_pixel_diff", side_effect=mock_diff),
    ):
        row = visual_regression._run_comparison("filefree", "/", "https://filefree.ai")

    assert row["status"] == "regression"
    assert row["diff_percent"] == 5.0
    assert row["threshold_percent"] == 0.5


# ---------------------------------------------------------------------------
# install function
# ---------------------------------------------------------------------------


def test_install_registers_job() -> None:
    """install() registers the job with the scheduler."""
    from unittest.mock import MagicMock

    scheduler = MagicMock()
    visual_regression.install(scheduler)

    scheduler.add_job.assert_called_once()
    call_kwargs = scheduler.add_job.call_args[1]
    assert call_kwargs["id"] == "brain_visual_regression_daily"
    assert call_kwargs["name"] == "Visual Regression (Wave PROBE PR-PB2)"
