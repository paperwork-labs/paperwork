"""Unit tests for apis/brain/app/schedulers/ux_probe_runner.py.

Tests mock subprocess.run so no real Playwright binaries are required.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.schedulers import ux_probe_runner

if TYPE_CHECKING:
    from pathlib import Path
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["pnpm", "--filter", "@paperwork/probes", "test:filefree"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


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
# _run_product_probe — happy path
# ---------------------------------------------------------------------------


def test_run_product_probe_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful probe run returns status=pass."""
    monkeypatch.setattr(ux_probe_runner, "_PROBE_RESULTS_JSON", tmp_path / "probe_results.json")

    with (
        patch("shutil.which", return_value="/usr/bin/pnpm"),
        patch("subprocess.run", return_value=_make_completed(0, stdout="1 passed")),
        patch.object(ux_probe_runner, "_parse_playwright_json", return_value=None),
    ):
        row = ux_probe_runner._run_product_probe("filefree", "https://filefree.ai")

    assert row["status"] == "pass"
    assert row["exit_code"] == 0
    assert row["product"] == "filefree"
    assert row["base_url"] == "https://filefree.ai"
    assert "started_at" in row
    assert "finished_at" in row


def test_run_product_probe_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-zero exit code produces status=failure with failing_tests populated."""
    monkeypatch.setattr(ux_probe_runner, "_PROBE_RESULTS_JSON", tmp_path / "probe_results.json")

    pw_json = {
        "suites": [
            {
                "specs": [
                    {
                        "title": "sign-in page renders Clerk widget with FileFree branding",
                        "tests": [
                            {
                                "results": [
                                    {
                                        "status": "failed",
                                        "error": {"message": "Expected 'FileFree'"},
                                        "attachments": [{"path": "/tmp/screenshot.png"}],
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }
        ]
    }

    with (
        patch("shutil.which", return_value="/usr/bin/pnpm"),
        patch("subprocess.run", return_value=_make_completed(1, stderr="1 failed")),
        patch.object(ux_probe_runner, "_parse_playwright_json", return_value=pw_json),
    ):
        row = ux_probe_runner._run_product_probe("filefree", "https://filefree.ai")

    assert row["status"] == "failure"
    assert row["exit_code"] == 1
    assert len(row["failing_tests"]) == 1
    assert row["failing_tests"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# _run_product_probe — no-silent-fallback: infrastructure errors
# ---------------------------------------------------------------------------


def test_run_product_probe_no_pnpm() -> None:
    """Missing pnpm → infrastructure_error row, not a silent skip."""
    with patch("shutil.which", return_value=None):
        row = ux_probe_runner._run_product_probe("filefree", "https://filefree.ai")

    assert row["status"] == "infrastructure_error"
    assert row["exit_code"] is None
    assert "pnpm not found" in row["error_message"]


def test_run_product_probe_missing_browser() -> None:
    """Playwright browser not installed → infrastructure_error row, not a silent skip."""
    stderr = "browserType.launch: Executable doesn't exist\nrun playwright install"

    with (
        patch("shutil.which", return_value="/usr/bin/pnpm"),
        patch("subprocess.run", return_value=_make_completed(1, stderr=stderr)),
    ):
        row = ux_probe_runner._run_product_probe("filefree", "https://filefree.ai")

    assert row["status"] == "infrastructure_error"
    assert "browser binaries" in row["error_message"]


def test_run_product_probe_timeout() -> None:
    """Subprocess timeout → status=timeout, not a silent skip."""
    with (
        patch("shutil.which", return_value="/usr/bin/pnpm"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pnpm", timeout=120),
        ),
    ):
        row = ux_probe_runner._run_product_probe("filefree", "https://filefree.ai")

    assert row["status"] == "timeout"
    assert row["exit_code"] is None
    assert "timed out" in row["error_message"]


# ---------------------------------------------------------------------------
# Result persistence: rolling 1000 cap
# ---------------------------------------------------------------------------


def test_save_results_prunes_to_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """probe_results.json is pruned to _PROBE_RESULTS_LIMIT entries."""
    monkeypatch.setattr(ux_probe_runner, "_PROBE_RESULTS_JSON", tmp_path / "probe_results.json")
    monkeypatch.setattr(ux_probe_runner, "_PROBE_RESULTS_LIMIT", 5)

    results = [{"product": f"p{i}", "status": "pass"} for i in range(10)]
    ux_probe_runner._save_results(results)

    saved = json.loads((tmp_path / "probe_results.json").read_text())
    assert len(saved["results"]) == 5
    # Should keep the tail (most recent)
    assert saved["results"][0]["product"] == "p5"


def test_append_result_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_append_result creates the file if it doesn't exist."""
    results_path = tmp_path / "probe_results.json"
    monkeypatch.setattr(ux_probe_runner, "_PROBE_RESULTS_JSON", results_path)

    assert not results_path.exists()
    ux_probe_runner._append_result({"product": "filefree", "status": "pass"})
    assert results_path.exists()

    saved = json.loads(results_path.read_text())
    assert saved["results"][0]["product"] == "filefree"


# ---------------------------------------------------------------------------
# _load_production_urls — missing file raises, not silently returns empty
# ---------------------------------------------------------------------------


def test_load_production_urls_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing production-urls.json raises FileNotFoundError (no silent fallback)."""
    monkeypatch.setattr(
        ux_probe_runner, "_PRODUCTION_URLS_JSON", tmp_path / "nonexistent.json"
    )
    with pytest.raises(FileNotFoundError, match=r"production-urls\.json not found"):
        ux_probe_runner._load_production_urls()


def test_load_production_urls_filters_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_comment keys are stripped from the loaded URL map."""
    p = tmp_path / "production-urls.json"
    p.write_text(
        json.dumps({"_comment": "ignore me", "filefree": "https://filefree.ai"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ux_probe_runner, "_PRODUCTION_URLS_JSON", p)
    urls = ux_probe_runner._load_production_urls()
    assert "_comment" not in urls
    assert urls["filefree"] == "https://filefree.ai"
