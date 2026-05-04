import builtins
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.database as _db_mod
from app.database import get_db
from app.main import app as fastapi_app
from app.models import *  # noqa: F403 — register all models with Base.metadata
from app.models.base import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://brain:brain_dev@localhost:5432/brain_test",
)


class FakeRedis:
    """In-memory Redis substitute for tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._sets: dict[str, builtins.set[str]] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self._store[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)
            self._sets.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self._store.clear()
        self._sets.clear()

    async def smembers(self, key: str) -> builtins.set[str]:
        return self._sets.get(key, builtins.set())

    async def set(
        self,
        key: str,
        value: str,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    async def sadd(self, key: str, *values: str) -> int:
        if key not in self._sets:
            self._sets[key] = builtins.set()
        added = 0
        for v in values:
            if v not in self._sets[key]:
                self._sets[key].add(v)
                added += 1
        return added

    async def expire(self, key: str, _ttl: int) -> bool:
        return key in self._store or key in self._sets


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        await engine.dispose()
        pytest.skip("Database not available")

    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def redis_mock(fake_redis: FakeRedis) -> FakeRedis:
    """Alias for fake_redis for use in integration tests."""
    return fake_redis


@pytest_asyncio.fixture()
async def pg_conv_setup(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None, None]:
    """Redirect Conversations service factory to test DB; skip if Postgres absent.

    Wave T1.0d migrated the conversations service from JSON-on-disk + SQLite FTS
    to a Postgres-canonical store. Tests that exercise the service (directly or
    transitively via the expense pipeline, schedulers, audits, etc.) now require
    Postgres at TEST_DATABASE_URL.

    This fixture is autouse via the ``_pg_conv_autouse`` wrapper below so that
    legacy tests which transitively call ``conversations.create_conversation``
    keep working without per-test fixture wiring. If Postgres is not reachable,
    affected tests skip cleanly (no silent fallback — the service still raises
    in production).
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        await engine.dispose()
        pytest.skip("Test database not available")

    test_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    original_factory = _db_mod.async_session_factory
    monkeypatch.setattr(_db_mod, "async_session_factory", test_factory)

    yield

    monkeypatch.setattr(_db_mod, "async_session_factory", original_factory)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception:
        pass
    await engine.dispose()


@pytest.fixture(autouse=True)
def _pg_conv_autouse(request: pytest.FixtureRequest) -> None:
    """Pull pg_conv_setup into every test that doesn't opt out.

    Tests that don't touch the conversations service skip the fixture cost
    quickly (Postgres reachability check is cheap when up). Tests can opt out
    with ``@pytest.mark.no_pg_conv``.
    """
    if request.node.get_closest_marker("no_pg_conv") is not None:
        return
    request.getfixturevalue("pg_conv_setup")


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, fake_redis: FakeRedis
) -> AsyncGenerator[AsyncClient, None]:
    import app.main as main_module
    import app.redis as redis_module

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
    redis_module._redis_pool = fake_redis  # type: ignore[assignment]

    from app.rate_limit import limiter as app_limiter

    app_limiter._storage.reset()

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()
    redis_module._redis_pool = original_pool
    main_module.init_redis = orig_init
    main_module.close_redis = orig_close
