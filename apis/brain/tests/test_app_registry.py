from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services import app_registry


def _entry(
    name: str, app_type: str, score: float, missing: list[str] | None = None
) -> dict[str, object]:
    return {
        "name": name,
        "path": f"apis/{name}",
        "type": app_type,
        "framework": "FastAPI",
        "language": "python",
        "language_version": "3.13",
        "package_manager": "uv",
        "test_runner": "pytest",
        "linter": "ruff",
        "formatter": "ruff format",
        "deploy_target": "render",
        "service_name": f"{name}-api",
        "owner_persona": "ops-engineer",
        "conformance": {"score": score, "missing_markers": missing or []},
        "size_signals": {"py_files": 1, "ts_files": 0, "lines_of_code_approx": 10},
        "last_modified": "2026-04-28T00:00:00Z",
        "depends_on_services": ["postgres"],
    }


def _registry(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "app_registry/v1",
        "description": "test registry",
        "version": 1,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "pwl registry-build",
        "apps": entries,
    }


@pytest.fixture
def registry_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "app_registry.json"
    path.write_text(
        json.dumps(
            _registry(
                [
                    _entry("brain", "python-api", 0.95),
                    _entry("studio", "next-app", 0.75, ["README.md"]),
                    _entry("worker", "python-api", 0.5, ["Dockerfile"]),
                ]
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_APP_REGISTRY_JSON", str(path))
    return path


def test_load_registry_returns_valid_pydantic_object(registry_file: Path) -> None:
    registry = app_registry.load_registry()

    assert registry.version == 1
    assert [app.name for app in registry.apps] == ["brain", "studio", "worker"]


def test_apps_by_type_filters_correctly(registry_file: Path) -> None:
    apps = app_registry.apps_by_type("python-api")

    assert [app.name for app in apps] == ["brain", "worker"]


def test_conformance_summary_computes_p95_and_low_conformance(registry_file: Path) -> None:
    summary = app_registry.conformance_summary()

    assert summary["total"] == 3
    assert summary["by_type"] == {"next-app": 1, "python-api": 2}
    assert summary["p95_score"] == 0.93
    assert [app["name"] for app in summary["low_conformance"]] == ["studio", "worker"]


def test_atomic_file_lock_allows_concurrent_reads(registry_file: Path) -> None:
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: app_registry.load_registry().version, range(12)))

    assert results == [1] * 12


def test_malformed_json_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "app_registry.json"
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("BRAIN_APP_REGISTRY_JSON", str(path))

    with pytest.raises(json.JSONDecodeError):
        app_registry.load_registry()
