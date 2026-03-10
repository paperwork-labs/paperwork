import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import get_db
from app.main import app as fastapi_app
from app.models import *  # noqa: F403 — register all models with Base.metadata
from app.models.base import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://filefree:filefree_dev@localhost:5432/filefree_test",
)


class FakeRedis:
    """In-memory Redis substitute for tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value
        self._ttls[key] = ttl

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)
            self._ttls.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self._store.clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional session that rolls back after each test.
    Creates a fresh engine per test to avoid event-loop issues."""
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


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, fake_redis: FakeRedis
) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with DB and Redis dependencies overridden."""
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
    app_limiter._storage.reset()  # no public API; slowapi exposes storage only via _storage

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()
    redis_module._redis_pool = original_pool
    main_module.init_redis = orig_init
    main_module.close_redis = orig_close


@pytest.fixture
def sync_client():
    """Sync TestClient for simple tests that don't need DB isolation."""
    from fastapi.testclient import TestClient

    return TestClient(fastapi_app)
