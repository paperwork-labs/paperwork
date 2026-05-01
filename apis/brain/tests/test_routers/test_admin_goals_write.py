"""``/api/v1/admin/goals`` JSON-backed read/write (PB-2)."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app as fastapi_app
from tests.conftest import FakeRedis


def _headers(secret: str = "test-goals-secret") -> dict[str, str]:
    return {"X-Brain-Secret": secret}


@pytest_asyncio.fixture
async def goals_client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """ASGI client without Postgres — goals routes only touch JSON on disk."""
    import app.main as main_module
    import app.redis as redis_module
    from app.rate_limit import limiter as app_limiter

    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-goals-secret")

    async def _noop() -> None:
        pass

    orig_init = main_module.init_redis
    orig_close = main_module.close_redis
    main_module.init_redis = _noop  # type: ignore[assignment]
    main_module.close_redis = _noop  # type: ignore[assignment]

    original_pool = redis_module._redis_pool
    redis_module._redis_pool = FakeRedis()  # type: ignore[assignment]

    app_limiter._storage.reset()

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    redis_module._redis_pool = original_pool
    main_module.init_redis = orig_init
    main_module.close_redis = orig_close


@pytest.mark.asyncio
async def test_goals_requires_secret(
    goals_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-goals-secret")
    for method, path in [
        ("GET", "/api/v1/admin/goals"),
        ("POST", "/api/v1/admin/goals"),
        ("PUT", "/api/v1/admin/goals/x"),
        ("DELETE", "/api/v1/admin/goals/x"),
        ("PATCH", "/api/v1/admin/goals/x/key-results/y"),
    ]:
        if method == "GET":
            res = await goals_client.get(path)
        elif method == "POST":
            res = await goals_client.post(
                path, json={"objective": "a", "owner": "u", "quarter": "Q1"}
            )
        elif method == "PUT":
            res = await goals_client.put(path, json={})
        elif method == "DELETE":
            res = await goals_client.delete(path)
        else:
            res = await goals_client.patch(path, json={"current_value": 1.0})
        assert res.status_code == 401, (method, path, res.text)


@pytest.mark.asyncio
async def test_post_put_delete_patch_flow(
    goals_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    gpath = tmp_path / "goals.json"
    gpath.write_text(json.dumps({"quarter": "", "objectives": []}), encoding="utf-8")
    monkeypatch.setenv("BRAIN_GOALS_JSON", str(gpath))

    post_body = {
        "objective": "Launch internal API",
        "owner": "founder",
        "quarter": "2026-Q2",
        "key_results": [{"title": "Endpoints live", "target": 10.0, "current": 2.0, "unit": "ep"}],
    }
    res = await goals_client.post("/api/v1/admin/goals", json=post_body, headers=_headers())
    assert res.status_code == 200
    js = res.json()
    assert js["success"] is True
    created = js["data"]
    goal_id = created["id"]
    assert created["title"] == "Launch internal API"
    assert len(created["key_results"]) == 1
    kr_id = created["key_results"][0]["id"]
    assert created["key_results"][0]["current"] == 2.0

    res_get = await goals_client.get("/api/v1/admin/goals", headers=_headers())
    assert res_get.status_code == 200
    envelope = res_get.json()["data"]
    ids = [o["id"] for o in envelope["objectives"]]
    assert goal_id in ids

    put_res = await goals_client.put(
        f"/api/v1/admin/goals/{goal_id}",
        json={"objective": "Launch internal APIs", "owner": "eng"},
        headers=_headers(),
    )
    assert put_res.status_code == 200
    updated = put_res.json()["data"]
    assert updated["title"] == "Launch internal APIs"
    assert updated["owner"] == "eng"

    patch_res = await goals_client.patch(
        f"/api/v1/admin/goals/{goal_id}/key-results/{kr_id}",
        json={"current_value": 5.0, "note": "halfway"},
        headers=_headers(),
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()["data"]
    assert patched["current"] == 5.0
    assert patched["progress_pct"] == 50.0
    assert patched["note"] == "halfway"

    del_res = await goals_client.delete(f"/api/v1/admin/goals/{goal_id}", headers=_headers())
    assert del_res.status_code == 200
    arch = del_res.json()["data"]
    assert arch["id"] == goal_id
    assert arch.get("archived_at")

    res_list = await goals_client.get("/api/v1/admin/goals", headers=_headers())
    goals = res_list.json()["data"]["objectives"]
    archived = next(g for g in goals if g["id"] == goal_id)
    assert archived.get("archived_at") == arch["archived_at"]


@pytest.mark.asyncio
async def test_goal_not_found_404(
    goals_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    gpath = tmp_path / "goals.json"
    gpath.write_text(json.dumps({"quarter": "Q", "objectives": []}), encoding="utf-8")
    monkeypatch.setenv("BRAIN_GOALS_JSON", str(gpath))

    r1 = await goals_client.put(
        "/api/v1/admin/goals/nonexistent-id",
        json={"objective": "x"},
        headers=_headers(),
    )
    assert r1.status_code == 404
    assert "not found" in r1.json()["detail"].lower()

    r2 = await goals_client.delete("/api/v1/admin/goals/nonexistent-id", headers=_headers())
    assert r2.status_code == 404
    assert "not found" in r2.json()["detail"].lower()

    r3 = await goals_client.patch(
        "/api/v1/admin/goals/nonexistent-id/key-results/kr-x",
        json={"current_value": 1.0},
        headers=_headers(),
    )
    assert r3.status_code == 404
    assert "not found" in r3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_key_result_not_found_404(
    goals_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    gpath = tmp_path / "goals.json"
    gpath.write_text(
        json.dumps(
            {
                "quarter": "Q",
                "objectives": [
                    {
                        "id": "g1",
                        "title": "T",
                        "owner": "o",
                        "key_results": [{"id": "kr-a", "title": "KR", "target": 10, "current": 0}],
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_GOALS_JSON", str(gpath))

    r = await goals_client.patch(
        "/api/v1/admin/goals/g1/key-results/bogus-kr",
        json={"current_value": 9.0},
        headers=_headers(),
    )
    assert r.status_code == 404
    assert "key result not found" in r.json()["detail"].lower()
