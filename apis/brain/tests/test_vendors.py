"""Tests for WS-76 PR-25 — Vendor model + vendors API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.main import app as fastapi_app


def _seed_vendors_file(path: Path, vendors: list[dict]) -> None:
    payload = {"schema": "brain_vendors/v1", "vendors": vendors}
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def vendors_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    vf = tmp_path / "vendors.json"
    _seed_vendors_file(
        vf,
        [
            {
                "id": "vercel",
                "name": "Vercel",
                "domain": "vercel.com",
                "category": "hosting",
                "monthly_estimate_usd": None,
                "contract_url": "https://vercel.com/pricing",
                "owner_persona": None,
                "organization_id": None,
            },
            {
                "id": "anthropic",
                "name": "Anthropic",
                "domain": "anthropic.com",
                "category": "ai_provider",
                "monthly_estimate_usd": None,
                "contract_url": "https://www.anthropic.com/pricing",
                "owner_persona": None,
                "organization_id": None,
            },
        ],
    )
    monkeypatch.setenv("BRAIN_VENDORS_JSON", str(vf))
    return vf


@pytest.fixture
async def client_vendors(request: pytest.FixtureRequest) -> AsyncClient:
    request.getfixturevalue("vendors_env")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_list_and_get_vendor(client_vendors: AsyncClient) -> None:
    res = await client_vendors.get("/api/v1/vendors")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    ids = sorted(v["id"] for v in body["data"]["vendors"])
    assert ids == ["anthropic", "vercel"]

    res_one = await client_vendors.get("/api/v1/vendors/vercel")
    assert res_one.status_code == 200
    assert res_one.json()["data"]["vendor"]["name"] == "Vercel"

    missing = await client_vendors.get("/api/v1/vendors/nope")
    assert missing.status_code == 404


async def test_list_vendors_category_filter(client_vendors: AsyncClient) -> None:
    res = await client_vendors.get("/api/v1/vendors", params={"category": "hosting"})
    assert res.status_code == 200
    vendors = res.json()["data"]["vendors"]
    assert len(vendors) == 1
    assert vendors[0]["id"] == "vercel"


async def test_create_vendor(client_vendors: AsyncClient, vendors_env: Path) -> None:
    payload = {
        "id": "stripe",
        "name": "Stripe",
        "domain": "stripe.com",
        "category": "payments",
        "monthly_estimate_usd": None,
        "contract_url": "https://stripe.com/pricing",
        "owner_persona": None,
        "organization_id": None,
    }
    res = await client_vendors.post("/api/v1/vendors", json=payload)
    assert res.status_code == 201
    assert res.json()["data"]["vendor"]["id"] == "stripe"

    raw = json.loads(vendors_env.read_text(encoding="utf-8"))
    assert len(raw["vendors"]) == 3

    dup = await client_vendors.post("/api/v1/vendors", json=payload)
    assert dup.status_code == 409


async def test_update_vendor(client_vendors: AsyncClient, vendors_env: Path) -> None:
    body = {
        "name": "Vercel Inc",
        "domain": "vercel.com",
        "category": "hosting",
        "monthly_estimate_usd": 100.5,
        "contract_url": "https://vercel.com/pricing",
        "owner_persona": "cfo",
        "organization_id": "org_demo",
    }
    res = await client_vendors.put("/api/v1/vendors/vercel", json=body)
    assert res.status_code == 200
    vendor = res.json()["data"]["vendor"]
    assert vendor["name"] == "Vercel Inc"
    assert vendor["monthly_estimate_usd"] == 100.5
    assert vendor["owner_persona"] == "cfo"

    raw = json.loads(vendors_env.read_text(encoding="utf-8"))
    vercel = next(v for v in raw["vendors"] if v["id"] == "vercel")
    assert vercel["name"] == "Vercel Inc"

    missing = await client_vendors.put(
        "/api/v1/vendors/nope",
        json={**body, "name": "X"},
    )
    assert missing.status_code == 404


def test_bundled_vendors_json_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path(__file__).resolve().parent.parent / "data" / "vendors.json"
    assert path.is_file()
    monkeypatch.setenv("BRAIN_VENDORS_JSON", str(path))
    from app.services import vendors as svc

    root = svc.load_vendors()
    assert root.schema_.startswith("brain_vendors/")
    assert len(root.vendors) == 10
    ids = {v.id for v in root.vendors}
    expected = {
        "vercel",
        "render",
        "cloudflare",
        "github",
        "anthropic",
        "openai",
        "stripe",
        "google",
        "hetzner",
        "clerk",
    }
    assert ids == expected


def test_service_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vf = tmp_path / "v.json"
    _seed_vendors_file(vf, [])
    monkeypatch.setenv("BRAIN_VENDORS_JSON", str(vf))

    import importlib

    import app.services.vendors as svc

    importlib.reload(svc)

    from app.schemas.vendor import VendorCreate, VendorUpdate

    created = svc.create_vendor(
        VendorCreate(
            id="acme",
            name="Acme",
            domain="acme.example",
            category="other",
            contract_url="https://acme.example/pricing",
        )
    )
    assert created.id == "acme"

    svc.update_vendor(
        "acme",
        VendorUpdate(
            name="Acme Corp",
            domain="acme.example",
            category="other",
            contract_url="https://acme.example/pricing",
        ),
    )
    loaded = svc.get_vendor("acme")
    assert loaded is not None
    assert loaded.name == "Acme Corp"


def test_duplicate_vendor_ids_rejected_in_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vf = tmp_path / "bad.json"
    vf.write_text(
        json.dumps(
            {
                "schema": "brain_vendors/v1",
                "vendors": [
                    {
                        "id": "dup",
                        "name": "A",
                        "domain": "a.com",
                        "category": "x",
                        "contract_url": "https://a.com",
                    },
                    {
                        "id": "dup",
                        "name": "B",
                        "domain": "b.com",
                        "category": "x",
                        "contract_url": "https://b.com",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_VENDORS_JSON", str(vf))
    import importlib

    import app.services.vendors as svc

    importlib.reload(svc)

    with pytest.raises(ValidationError):
        svc.load_vendors()
