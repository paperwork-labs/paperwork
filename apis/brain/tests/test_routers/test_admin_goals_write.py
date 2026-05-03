"""``/api/v1/admin/goals`` hierarchy CRUD (epics router) + OKR JSON paths where covered."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.main import app as fastapi_app
from tests.conftest import FakeRedis


def _headers(secret: str = "test-goals-secret") -> dict[str, str]:
    return {"X-Brain-Secret": secret}


@pytest_asyncio.fixture
async def goals_client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """ASGI client with in-memory DB — goals routes use SQLAlchemy."""
    import app.main as main_module
    import app.redis as redis_module
    from app.rate_limit import limiter as app_limiter

    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-goals-secret")

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def _noop() -> None:
        pass

    fastapi_app.dependency_overrides[get_db] = _override_get_db

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

    fastapi_app.dependency_overrides.clear()
    redis_module._redis_pool = original_pool
    main_module.init_redis = orig_init
    main_module.close_redis = orig_close


@pytest.mark.asyncio
async def test_goals_requires_secret(
    goals_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-goals-secret")
    for method, path, body in [
        ("GET", "/api/v1/admin/goals", None),
        (
            "POST",
            "/api/v1/admin/goals",
            {
                "id": "t",
                "objective": "a",
                "horizon": "Q2",
                "metric": "m",
                "target": "1",
                "written_at": "2026-01-01T00:00:00+00:00",
            },
        ),
        ("PATCH", "/api/v1/admin/goals/x", {"objective": "a"}),
        ("DELETE", "/api/v1/admin/goals/x", None),
        ("PATCH", "/api/v1/admin/okr/goals/x/key-results/y", {"current_value": 1.0}),
    ]:
        if method == "GET":
            res = await goals_client.get(path)
        elif method == "POST":
            res = await goals_client.post(path, json=body)
        elif method == "DELETE":
            res = await goals_client.delete(path)
        else:
            res = await goals_client.patch(path, json=body or {})
        assert res.status_code == 401, (method, path, res.text)


@pytest.mark.asyncio
async def test_post_put_delete_patch_flow(
    goals_client: AsyncClient,
) -> None:
    post_body = {
        "id": "goal-test-1",
        "objective": "Launch internal API",
        "horizon": "2026-Q2",
        "metric": "endpoints",
        "target": "10 live",
        "status": "active",
        "owner_employee_slug": "founder",
        "written_at": "2026-04-01T12:00:00+00:00",
    }
    res = await goals_client.post("/api/v1/admin/goals", json=post_body, headers=_headers())
    assert res.status_code == 201
    js = res.json()
    assert js["success"] is True
    created = js["data"]
    goal_id = created["id"]
    assert created["objective"] == "Launch internal API"
    assert created["owner_employee_slug"] == "founder"

    res_get = await goals_client.get("/api/v1/admin/goals", headers=_headers())
    assert res_get.status_code == 200
    goals_list = res_get.json()["data"]
    assert isinstance(goals_list, list)
    assert goal_id in [g["id"] for g in goals_list]

    patch_res = await goals_client.patch(
        f"/api/v1/admin/goals/{goal_id}",
        json={"objective": "Launch internal APIs", "owner_employee_slug": "eng"},
        headers=_headers(),
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()["data"]
    assert updated["objective"] == "Launch internal APIs"
    assert updated["owner_employee_slug"] == "eng"

    del_res = await goals_client.delete(f"/api/v1/admin/goals/{goal_id}", headers=_headers())
    assert del_res.status_code == 200
    out = del_res.json()["data"]
    assert out["deleted"] is True
    assert out["id"] == goal_id

    res_list = await goals_client.get("/api/v1/admin/goals", headers=_headers())
    assert res_list.status_code == 200
    assert goal_id not in [g["id"] for g in res_list.json()["data"]]


@pytest.mark.asyncio
async def test_goal_not_found_404(
    goals_client: AsyncClient,
) -> None:
    r1 = await goals_client.patch(
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
        "/api/v1/admin/okr/goals/nonexistent-id/key-results/kr-x",
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
        (
            '{"quarter": "Q", "objectives": ['
            '{"id": "g1", "title": "T", "owner": "o", '
            '"key_results": [{"id": "kr-a", "title": "KR", "target": 10, "current": 0}]}]}'
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_GOALS_JSON", str(gpath))

    r = await goals_client.patch(
        "/api/v1/admin/okr/goals/g1/key-results/bogus-kr",
        json={"current_value": 9.0},
        headers=_headers(),
    )
    assert r.status_code == 404
    assert "key result not found" in r.json()["detail"].lower()
