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
    "postgresql+asyncpg://brain:brain_dev@localhost:5432/brain_test",
)


class FakeRedis:
    """In-memory Redis substitute for tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

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

    async def smembers(self, key: str) -> set[str]:
        return self._sets.get(key, set())

    async def sadd(self, key: str, *values: str) -> int:
        if key not in self._sets:
            self._sets[key] = set()
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
