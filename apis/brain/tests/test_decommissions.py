"""Tests for app.schemas.decommissions + app.services.decommissions (WS-48)."""

from __future__ import annotations

import json
import textwrap

import pytest


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_decommission_entry_required_fields():
    from app.schemas.decommissions import DecommissionEntry

    entry = DecommissionEntry(
        id="test-entry",
        domain="test.example.com",
        reason="No longer needed",
        status="proposed",
    )
    assert entry.id == "test-entry"
    assert entry.domain == "test.example.com"
    assert entry.vercel_project is None
    assert entry.decommissioned_at is None
    assert entry.blockers == []


def test_decommission_entry_status_enum_validation():
    from pydantic import ValidationError

    from app.schemas.decommissions import DecommissionEntry

    with pytest.raises(ValidationError):
        DecommissionEntry(
            id="x",
            domain="x.com",
            reason="r",
            status="invalid-status",  # type: ignore[arg-type]
        )


def test_decommissions_file_schema_alias():
    from app.schemas.decommissions import DecommissionsFile

    raw = {
        "schema": "decommissions/v1",
        "description": "test",
        "entries": [],
    }
    file = DecommissionsFile.model_validate(raw)
    assert file.schema_ == "decommissions/v1"
    assert file.entries == []


def test_decommissions_file_parses_entry():
    from app.schemas.decommissions import DecommissionsFile

    raw = {
        "schema": "decommissions/v1",
        "description": "test",
        "entries": [
            {
                "id": "apps-paperworklabs-com",
                "domain": "apps.paperworklabs.com",
                "vercel_project": "apps",
                "clerk_instance": None,
                "decommissioned_at": None,
                "decommissioned_by": None,
                "reason": "Was for Clerk Account Portal, now hosted natively.",
                "status": "proposed",
                "notes": "WS-48",
                "last_30d_traffic_check": None,
                "blockers": [],
            }
        ],
    }
    file = DecommissionsFile.model_validate(raw)
    assert len(file.entries) == 1
    entry = file.entries[0]
    assert entry.id == "apps-paperworklabs-com"
    assert entry.status == "proposed"
    assert entry.vercel_project == "apps"


# ---------------------------------------------------------------------------
# Service — load_decommissions_file
# ---------------------------------------------------------------------------


def _write_fixture(tmp_path, entries: list[dict]) -> str:
    data = {
        "schema": "decommissions/v1",
        "description": "fixture",
        "entries": entries,
    }
    p = tmp_path / "decommissions.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_load_decommissions_file_reads_disk(tmp_path, monkeypatch):
    path = _write_fixture(
        tmp_path,
        [
            {
                "id": "foo-bar",
                "domain": "foo.bar.com",
                "reason": "test",
                "status": "done",
                "decommissioned_at": None,
                "decommissioned_by": None,
                "vercel_project": None,
                "clerk_instance": None,
                "notes": "",
                "last_30d_traffic_check": None,
                "blockers": [],
            }
        ],
    )
    monkeypatch.setenv("DECOMMISSIONS_DATA_PATH", path)

    from app.services import decommissions as svc

    svc._load_cached.cache_clear()
    file = svc.load_decommissions_file(bypass_cache=True)
    assert len(file.entries) == 1
    assert file.entries[0].id == "foo-bar"


def test_load_decommissions_file_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("DECOMMISSIONS_DATA_PATH", str(tmp_path / "nonexistent.json"))

    from app.services import decommissions as svc

    svc._load_cached.cache_clear()
    file = svc.load_decommissions_file(bypass_cache=True)
    assert file.entries == []


def test_list_entries_no_filter(tmp_path, monkeypatch):
    path = _write_fixture(
        tmp_path,
        [
            {
                "id": "a",
                "domain": "a.com",
                "reason": "r",
                "status": "proposed",
                "decommissioned_at": None,
                "decommissioned_by": None,
                "vercel_project": None,
                "clerk_instance": None,
                "notes": "",
                "last_30d_traffic_check": None,
                "blockers": [],
            },
            {
                "id": "b",
                "domain": "b.com",
                "reason": "r",
                "status": "done",
                "decommissioned_at": None,
                "decommissioned_by": None,
                "vercel_project": None,
                "clerk_instance": None,
                "notes": "",
                "last_30d_traffic_check": None,
                "blockers": [],
            },
        ],
    )
    monkeypatch.setenv("DECOMMISSIONS_DATA_PATH", path)

    from app.services import decommissions as svc

    svc._load_cached.cache_clear()
    entries = svc.list_entries(bypass_cache=True)
    assert len(entries) == 2


def test_list_entries_filter_by_status(tmp_path, monkeypatch):
    path = _write_fixture(
        tmp_path,
        [
            {
                "id": "a",
                "domain": "a.com",
                "reason": "r",
                "status": "proposed",
                "decommissioned_at": None,
                "decommissioned_by": None,
                "vercel_project": None,
                "clerk_instance": None,
                "notes": "",
                "last_30d_traffic_check": None,
                "blockers": [],
            },
            {
                "id": "b",
                "domain": "b.com",
                "reason": "r",
                "status": "done",
                "decommissioned_at": None,
                "decommissioned_by": None,
                "vercel_project": None,
                "clerk_instance": None,
                "notes": "",
                "last_30d_traffic_check": None,
                "blockers": [],
            },
        ],
    )
    monkeypatch.setenv("DECOMMISSIONS_DATA_PATH", path)

    from app.services import decommissions as svc

    svc._load_cached.cache_clear()
    proposed = svc.list_entries(status="proposed", bypass_cache=True)
    assert len(proposed) == 1
    assert proposed[0].id == "a"


def test_get_entry_found(tmp_path, monkeypatch):
    path = _write_fixture(
        tmp_path,
        [
            {
                "id": "apps-paperworklabs-com",
                "domain": "apps.paperworklabs.com",
                "reason": "r",
                "status": "proposed",
                "decommissioned_at": None,
                "decommissioned_by": None,
                "vercel_project": "apps",
                "clerk_instance": None,
                "notes": "",
                "last_30d_traffic_check": None,
                "blockers": [],
            }
        ],
    )
    monkeypatch.setenv("DECOMMISSIONS_DATA_PATH", path)

    from app.services import decommissions as svc

    svc._load_cached.cache_clear()
    entry = svc.get_entry("apps-paperworklabs-com", bypass_cache=True)
    assert entry is not None
    assert entry.domain == "apps.paperworklabs.com"


def test_get_entry_not_found(tmp_path, monkeypatch):
    path = _write_fixture(tmp_path, [])
    monkeypatch.setenv("DECOMMISSIONS_DATA_PATH", path)

    from app.services import decommissions as svc

    svc._load_cached.cache_clear()
    entry = svc.get_entry("does-not-exist", bypass_cache=True)
    assert entry is None


# ---------------------------------------------------------------------------
# Canonical decommissions.json round-trip
# ---------------------------------------------------------------------------


def test_canonical_decommissions_json_parses():
    """The committed decommissions.json file must be valid per the schema."""
    from pathlib import Path

    from app.schemas.decommissions import DecommissionsFile

    data_file = Path(__file__).resolve().parents[1] / "data" / "decommissions.json"
    assert data_file.exists(), f"decommissions.json not found at {data_file}"

    raw = json.loads(data_file.read_text(encoding="utf-8"))
    file = DecommissionsFile.model_validate(raw)
    assert len(file.entries) >= 1

    ids = [e.id for e in file.entries]
    assert "apps-paperworklabs-com" in ids
