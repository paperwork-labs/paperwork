from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services import infra_registry


def _minimal_registry() -> dict[str, object]:
    return {
        "schema": "infra_registry/v1",
        "description": "test",
        "services": [
            {
                "id": "studio",
                "name": "Studio",
                "provider": "vercel",
                "type": "frontend",
                "url": "https://example.com",
                "health_endpoint": None,
            },
            {
                "id": "brain-api",
                "name": "Brain API",
                "provider": "render",
                "type": "backend",
                "url": "https://brain.example.com",
                "health_endpoint": "/health",
            },
        ],
        "vendors": [
            {
                "id": "vercel",
                "name": "Vercel",
                "category": "hosting",
                "pricing_url": "https://vercel.com/pricing",
                "monthly_budget": None,
            },
            {
                "id": "anthropic",
                "name": "Anthropic",
                "category": "ai_provider",
                "pricing_url": "https://anthropic.com/pricing",
                "monthly_budget": None,
            },
        ],
    }


@pytest.fixture
def registry_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "infra_registry.json"
    path.write_text(json.dumps(_minimal_registry()), encoding="utf-8")
    monkeypatch.setenv("BRAIN_INFRA_REGISTRY_JSON", str(path))
    return path


def test_load_registry_validates(registry_file: Path) -> None:
    reg = infra_registry.load_registry()
    assert reg.schema_ == "infra_registry/v1"
    assert [s.id for s in reg.services] == ["studio", "brain-api"]


def test_list_services_filter_by_provider(registry_file: Path) -> None:
    vercel_only = infra_registry.list_services(provider="vercel")
    assert [s.id for s in vercel_only] == ["studio"]
    render_only = infra_registry.list_services(provider="render")
    assert [s.id for s in render_only] == ["brain-api"]


def test_list_services_empty_unknown_provider(registry_file: Path) -> None:
    assert infra_registry.list_services(provider="fly") == []


def test_list_vendors_filter_by_category(registry_file: Path) -> None:
    hosting = infra_registry.list_vendors(category="hosting")
    assert [v.id for v in hosting] == ["vercel"]


def test_get_service_and_vendor(registry_file: Path) -> None:
    assert infra_registry.get_service("studio") is not None
    assert infra_registry.get_service("nope") is None
    assert infra_registry.get_vendor("anthropic") is not None
    assert infra_registry.get_vendor("nope") is None


def test_malformed_json_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "infra_registry.json"
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("BRAIN_INFRA_REGISTRY_JSON", str(path))
    with pytest.raises(json.JSONDecodeError):
        infra_registry.load_registry()


def test_duplicate_service_ids_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _minimal_registry()
    services = list(data["services"])
    services.append(
        {
            "id": "studio",
            "name": "Dup",
            "provider": "vercel",
            "type": "frontend",
            "url": None,
            "health_endpoint": None,
        }
    )
    data["services"] = services
    path = tmp_path / "infra_registry.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("BRAIN_INFRA_REGISTRY_JSON", str(path))
    with pytest.raises(ValidationError):
        infra_registry.load_registry()


def test_bundled_registry_file_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the committed JSON matches the schema."""
    path = Path(__file__).resolve().parent.parent / "data" / "infra_registry.json"
    assert path.is_file()
    monkeypatch.setenv("BRAIN_INFRA_REGISTRY_JSON", str(path))
    reg = infra_registry.load_registry()
    assert len(reg.services) >= 1
    assert len(reg.vendors) >= 1
