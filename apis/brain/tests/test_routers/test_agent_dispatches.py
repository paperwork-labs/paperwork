"""Tests for /api/v1/agents/dispatches endpoints.

Tests run against an in-memory SQLite (via the db_session fixture or
direct model validation) — no live Postgres required for the unit tests.
Integration tests use the db_session fixture and are skipped if the DB is
unavailable.

medallion: ops
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app as fastapi_app
from app.models.agent_dispatch import MODEL_TO_SIZE, SIZE_COST_CENTS
from app.models.dispatch import DispatchEntry, DispatchResult, derive_t_shirt_size
from tests.conftest import FakeRedis

HEADERS = {"X-Brain-Secret": "test-dispatch-secret"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def dispatch_client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """ASGI client with a stubbed DB session."""
    import app.main as main_module
    import app.redis as redis_module
    from app.rate_limit import limiter as app_limiter

    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-dispatch-secret")
    monkeypatch.setattr(settings, "BRAIN_INTERNAL_TOKEN", "test-dispatch-secret")

    async def _noop() -> None:
        pass

    main_module.init_redis = _noop  # type: ignore[assignment]
    main_module.close_redis = _noop  # type: ignore[assignment]
    redis_module._redis_pool = FakeRedis()  # type: ignore[assignment]
    app_limiter._storage.reset()

    mock_session = MagicMock()

    async def _mock_flush() -> None:
        pass

    async def _mock_refresh(obj: Any) -> None:
        if not hasattr(obj, "id") or obj.id is None:
            object.__setattr__(obj, "id", uuid.uuid4())
        if not hasattr(obj, "dispatched_at") or obj.dispatched_at is None:
            object.__setattr__(obj, "dispatched_at", datetime.now(UTC))
        if not hasattr(obj, "organization_id"):
            object.__setattr__(obj, "organization_id", "paperwork-labs")

    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock(side_effect=_mock_flush)
    mock_session.refresh = AsyncMock(side_effect=_mock_refresh)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    async def _mock_execute(stmt: Any) -> MagicMock:
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute = AsyncMock(side_effect=_mock_execute)

    async def _override_get_db() -> AsyncGenerator[Any, None]:
        yield mock_session

    from app.database import get_db

    app_copy = fastapi_app
    app_copy.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app_copy)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app_copy.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unit tests: Pydantic model validation
# ---------------------------------------------------------------------------


def test_derive_t_shirt_size_xs() -> None:
    assert derive_t_shirt_size("composer-1.5") == "XS"


def test_derive_t_shirt_size_s() -> None:
    assert derive_t_shirt_size("composer-2-fast") == "S"


def test_derive_t_shirt_size_m() -> None:
    assert derive_t_shirt_size("gpt-5.5-medium") == "M"


def test_derive_t_shirt_size_l() -> None:
    assert derive_t_shirt_size("claude-4.6-sonnet-medium-thinking") == "L"


def test_derive_t_shirt_size_opus_raises() -> None:
    with pytest.raises(ValueError, match=r"opus.*FORBIDDEN"):
        derive_t_shirt_size("claude-4.5-opus-high-thinking")


def test_derive_t_shirt_size_unknown_raises() -> None:
    with pytest.raises(ValueError, match="allow-list"):
        derive_t_shirt_size("gpt-4o-random")


def test_dispatch_entry_derives_size() -> None:
    entry = DispatchEntry(
        task_id="test-1",
        source="manual",
        agent_model="composer-1.5",
    )
    assert entry.t_shirt_size == "XS"


def test_dispatch_entry_l_model() -> None:
    entry = DispatchEntry(
        task_id="test-2",
        source="goal",
        agent_model="claude-4.6-sonnet-medium-thinking",
    )
    assert entry.t_shirt_size == "L"


def test_dispatch_result_derives_size() -> None:
    result = DispatchResult(
        task_id="test-3",
        persona_id="ops-engineer",
        agent_model="gpt-5.5-medium",
    )
    assert result.t_shirt_size == "M"


def test_dispatch_result_legacy_cheap_model() -> None:
    result = DispatchResult(
        task_id="test-4",
        persona_id="ops-engineer",
        agent_model="cheap",
    )
    assert result.t_shirt_size == "S"


def test_model_to_size_bijection() -> None:
    assert set(MODEL_TO_SIZE.values()) == {"XS", "S", "M", "L"}
    assert len(MODEL_TO_SIZE) == len(set(MODEL_TO_SIZE.values()))


def test_size_cost_cents_all_sizes() -> None:
    for size in ("XS", "S", "M", "L"):
        assert SIZE_COST_CENTS[size] > 0


# ---------------------------------------------------------------------------
# HTTP tests (stubbed DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_dispatch_missing_model_returns_400(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.post(
        "/api/v1/agents/dispatches",
        json={"dispatched_by": "opus-orchestrator"},
        headers=HEADERS,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_dispatch_opus_model_returns_422(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.post(
        "/api/v1/agents/dispatches",
        json={
            "model_used": "claude-4.5-opus-high-thinking",
            "dispatched_by": "opus-orchestrator",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 422
    detail = resp.json()
    assert "opus" in str(detail).lower() or "forbidden" in str(detail).lower()


@pytest.mark.asyncio
async def test_post_dispatch_valid_model_derives_size(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.post(
        "/api/v1/agents/dispatches",
        json={
            "model_used": "composer-1.5",
            "dispatched_by": "opus-orchestrator",
            "task_summary": "Generate README stub",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["t_shirt_size"] == "XS"
    assert data["model_used"] == "composer-1.5"
    assert data["estimated_cost_cents"] == SIZE_COST_CENTS["XS"]


@pytest.mark.asyncio
async def test_post_dispatch_l_model(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.post(
        "/api/v1/agents/dispatches",
        json={
            "model_used": "claude-4.6-sonnet-medium-thinking",
            "dispatched_by": "opus-orchestrator",
            "workstream_id": "WS-42",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["t_shirt_size"] == "L"
    assert data["estimated_cost_cents"] == SIZE_COST_CENTS["L"]


@pytest.mark.asyncio
async def test_get_dispatches_returns_list(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.get(
        "/api/v1/agents/dispatches",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_dispatches_size_filter(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.get(
        "/api/v1/agents/dispatches?t_shirt_size=XS",
        headers=HEADERS,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_patch_dispatch_invalid_id_returns_422(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.patch(
        "/api/v1/agents/dispatches/not-a-uuid",
        json={"outcome": "success"},
        headers=HEADERS,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_dispatch_not_found_returns_404(
    dispatch_client: AsyncClient,
) -> None:
    fake_id = str(uuid.uuid4())
    resp = await dispatch_client.patch(
        f"/api/v1/agents/dispatches/{fake_id}",
        json={"outcome": "success"},
        headers=HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cost_summary_returns_expected_shape(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.get(
        "/api/v1/agents/dispatches/cost-summary",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "by_size" in data
    assert "by_workstream" in data
    assert "by_day" in data
    assert "calibration_delta" in data


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(
    dispatch_client: AsyncClient,
) -> None:
    resp = await dispatch_client.get("/api/v1/agents/dispatches")
    assert resp.status_code == 401
