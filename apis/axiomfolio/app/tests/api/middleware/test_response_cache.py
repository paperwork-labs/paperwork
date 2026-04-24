"""Tests for Redis-backed portfolio response cache decorator."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.api.middleware import response_cache as rc_mod
from app.api.middleware.response_cache import redis_response_cache
from app.models.user import User, UserRole
from app.services.market.market_data_service import infra


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def setex(self, key: str, _ttl: int, value: Any) -> None:
        self.store[key] = value

    def incr(self, key: str) -> int:
        cur = int(self.store.get(key, 0))
        cur += 1
        self.store[key] = cur
        return cur


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    fr = _FakeRedis()
    # ``MarketInfra.redis_client`` is a property; swap the backing client.
    monkeypatch.setattr(infra, "_redis_sync", fr, raising=False)
    return fr


@pytest.fixture
def db_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"rcache_{suffix}@example.com",
        username=f"rcache_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def db_user_b(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"rcache_b_{suffix}@example.com",
        username=f"rcache_b_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_cache_hit_returns_cached_body(fake_redis: _FakeRedis, db_user):
    app = FastAPI()
    calls = {"n": 0}

    def _user_dep() -> User:
        return db_user

    @app.get("/api/v1/portfolio/z")
    @redis_response_cache(ttl_seconds=30)
    async def _route(request: Request, user: User = Depends(_user_dep)):
        calls["n"] += 1
        return {"n": calls["n"]}

    c = TestClient(app)
    assert c.get("/api/v1/portfolio/z").json() == {"n": 1}
    assert c.get("/api/v1/portfolio/z").json() == {"n": 1}
    assert calls["n"] == 1


def test_different_users_get_different_keys(fake_redis: _FakeRedis, db_user, db_user_b):
    app = FastAPI()
    current = {"user": db_user}

    def _user_dep() -> User:
        return current["user"]

    @app.get("/api/v1/portfolio/shared")
    @redis_response_cache(ttl_seconds=30)
    async def _route(request: Request, user: User = Depends(_user_dep)):
        return {"who": user.id}

    c = TestClient(app)
    assert c.get("/api/v1/portfolio/shared").json() == {"who": db_user.id}
    current["user"] = db_user_b
    assert c.get("/api/v1/portfolio/shared").json() == {"who": db_user_b.id}
    assert len(fake_redis.store) == 2


def test_auth_failure_bypasses_cache(fake_redis: _FakeRedis):
    app = FastAPI()

    def _must_fail():
        raise HTTPException(status_code=401, detail="nope")

    @app.get("/api/v1/portfolio/protected")
    @redis_response_cache(ttl_seconds=30)
    async def _route(
        request: Request,
        _: None = Depends(_must_fail),
        user: User = Depends(lambda: MagicMock()),
    ):
        return {"ok": True}

    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/api/v1/portfolio/protected")
    assert r.status_code == 401
    assert fake_redis.store == {}


def test_redis_down_increments_bypass_counter(monkeypatch: pytest.MonkeyPatch, db_user):
    class _BadRedis:
        def get(self, *_a, **_kw):
            raise OSError("redis down")

        def setex(self, *_a, **_kw):
            raise OSError("redis down")

        def incr(self, *_a, **_kw):
            raise OSError("redis down")

    monkeypatch.setattr(infra, "_redis_sync", _BadRedis(), raising=False)
    inc = MagicMock(side_effect=rc_mod._inc_redis_bypass)
    monkeypatch.setattr(rc_mod, "_inc_redis_bypass", inc)

    app = FastAPI()

    def _user_dep() -> User:
        return db_user

    @app.get("/api/v1/portfolio/noredis")
    @redis_response_cache(ttl_seconds=30)
    async def _route(request: Request, user: User = Depends(_user_dep)):
        return {"live": True}

    c = TestClient(app)
    r = c.get("/api/v1/portfolio/noredis")
    assert r.status_code == 200
    assert r.json() == {"live": True}
    assert inc.call_count >= 1
