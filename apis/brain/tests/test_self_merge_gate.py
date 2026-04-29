"""Tests for WS-44 Brain graduated self-merge gate."""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import app.services.self_merge_gate as gate

NOW = datetime(2026, 4, 28, 12, 0, tzinfo=UTC)


def _empty_file(current_tier: str = "data-only") -> dict[str, object]:
    return {
        "schema": {
            "description": "Brain self-merge graduation log. cheap-agent-fleet.mdc rule + WS-44.",
            "tier_definitions": {
                "data-only": (
                    "merges only paths matching apis/brain/data/**, docs/**, .cursor/rules/**"
                ),
                "brain-code": (
                    "merges paths under apis/brain/** "
                    "(graduation requires N=50 clean data-only merges)"
                ),
                "app-code": (
                    "merges paths under apis/<other>/, apps/, packages/ "
                    "(graduation requires N=50 clean brain-code merges)"
                ),
            },
        },
        "version": 1,
        "current_tier": current_tier,
        "promotions": [],
        "merges": [],
        "reverts": [],
    }


@pytest.fixture
def promotions_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "self_merge_promotions.json"
    path.write_text(json.dumps(_empty_file()) + "\n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_SELF_MERGE_PROMOTIONS_JSON", str(path))
    monkeypatch.setattr(gate, "_utcnow", lambda: NOW)
    return path


def _write(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def test_tier_allows_path_data_only() -> None:
    assert gate.tier_allows_path("apis/brain/data/self_merge_promotions.json", "data-only")
    assert gate.tier_allows_path("docs/runbooks/brain-self-merge-graduation.md", "data-only")
    assert gate.tier_allows_path(".cursor/rules/cheap-agent-fleet.mdc", "data-only")
    assert not gate.tier_allows_path("apis/brain/app/services/self_merge_gate.py", "data-only")
    assert not gate.tier_allows_path("apps/studio/src/app/admin/page.tsx", "data-only")


def test_tier_allows_path_brain_code() -> None:
    assert gate.tier_allows_path("apis/brain/app/services/self_merge_gate.py", "brain-code")
    assert gate.tier_allows_path("apis/brain/data/self_merge_promotions.json", "brain-code")
    assert not gate.tier_allows_path("apps/studio/src/data/workstreams.json", "brain-code")


def test_tier_allows_path_app_code() -> None:
    assert gate.tier_allows_path("apps/studio/src/data/workstreams.json", "app-code")
    assert gate.tier_allows_path("packages/ui/src/button.tsx", "app-code")
    assert gate.tier_allows_path("apis/launchfree/app/main.py", "app-code")


def test_pr_qualifies_for_self_merge_allows_current_data_tier(
    promotions_path: Path,
) -> None:
    allowed, reason = gate.pr_qualifies_for_self_merge(
        ["apis/brain/data/self_merge_promotions.json", "docs/runbooks/x.md"]
    )
    assert allowed is True
    assert "data-only" in reason
    assert promotions_path.exists()


def test_pr_qualifies_for_self_merge_rejects_mixed_paths(promotions_path: Path) -> None:
    allowed, reason = gate.pr_qualifies_for_self_merge(
        ["apis/brain/data/self_merge_promotions.json", "apis/brain/app/main.py"]
    )
    assert allowed is False
    assert "paths outside current tier (data-only)" in reason
    assert promotions_path.exists()


def test_clean_merge_count_ignores_reverted_prs(promotions_path: Path) -> None:
    gate.record_merge(1, ["apis/brain/data/a.json"], NOW)
    gate.record_merge(2, ["apis/brain/data/b.json"], NOW)
    gate.record_revert(10, 1, "post-merge CI failed", NOW)
    assert gate.clean_merge_count() == 1
    assert promotions_path.exists()


def test_eligible_for_promotion_false_below_50_clean_merges(promotions_path: Path) -> None:
    for pr_number in range(1, 50):
        gate.record_merge(pr_number, ["apis/brain/data/a.json"], NOW)
    assert gate.eligible_for_promotion() is False
    assert promotions_path.exists()


def test_eligible_for_promotion_false_with_recent_revert(promotions_path: Path) -> None:
    for pr_number in range(1, 52):
        gate.record_merge(pr_number, ["apis/brain/data/a.json"], NOW)
    gate.record_revert(900, 1, "incident", NOW - timedelta(days=1))
    assert gate.eligible_for_promotion() is False
    assert promotions_path.exists()


def test_eligible_for_promotion_true_at_50_clean_merges(promotions_path: Path) -> None:
    for pr_number in range(1, 51):
        gate.record_merge(pr_number, ["apis/brain/data/a.json"], NOW)
    assert gate.eligible_for_promotion() is True
    assert promotions_path.exists()


def test_promote_transitions_and_appends_record(promotions_path: Path) -> None:
    for pr_number in range(1, 51):
        gate.record_merge(pr_number, ["apis/brain/data/a.json"], NOW)
    record = gate.promote()
    assert record is not None
    assert record.from_tier == "data-only"
    assert record.to_tier == "brain-code"
    data = json.loads(promotions_path.read_text(encoding="utf-8"))
    assert data["current_tier"] == "brain-code"
    assert len(data["promotions"]) == 1
    assert data["promotions"][0]["clean_merge_count_at_promotion"] == 50


def test_promote_returns_none_at_top_tier(promotions_path: Path) -> None:
    data = _empty_file("app-code")
    data["merges"] = [
        {
            "pr_number": pr_number,
            "merged_at": NOW.isoformat(),
            "tier": "app-code",
            "paths_touched": ["apps/studio/src/app/page.tsx"],
            "graduation_eligible": False,
        }
        for pr_number in range(1, 60)
    ]
    _write(promotions_path, data)
    assert gate.promote() is None
    assert json.loads(promotions_path.read_text(encoding="utf-8"))["current_tier"] == "app-code"


def test_file_lock_handles_concurrent_updates(promotions_path: Path) -> None:
    def _record(pr_number: int) -> None:
        gate.record_merge(pr_number, ["apis/brain/data/a.json"], NOW)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_record, range(1, 101)))

    data = json.loads(promotions_path.read_text(encoding="utf-8"))
    assert len(data["merges"]) == 100
    assert gate.clean_merge_count() == 100


def test_atomic_write_keeps_file_parseable(promotions_path: Path) -> None:
    stop = threading.Event()
    seen: list[int] = []

    def _writer() -> None:
        for pr_number in range(1, 60):
            gate.record_merge(pr_number, ["apis/brain/data/a.json"], NOW)
        stop.set()

    def _reader() -> None:
        while not stop.is_set():
            raw = promotions_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            seen.append(len(parsed["merges"]))

    writer = threading.Thread(target=_writer)
    reader = threading.Thread(target=_reader)
    reader.start()
    writer.start()
    writer.join()
    stop.set()
    reader.join()
    assert seen
    assert json.loads(promotions_path.read_text(encoding="utf-8"))["merges"]


def test_malformed_file_raises(promotions_path: Path) -> None:
    promotions_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        gate.current_tier()
    assert os.environ["BRAIN_SELF_MERGE_PROMOTIONS_JSON"] == str(promotions_path)
