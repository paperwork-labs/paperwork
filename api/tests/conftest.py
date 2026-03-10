import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app as fastapi_app
from app.models.base import Base
from app.models import *  # noqa: F401, F403 — register all models with Base.metadata

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://filefree:filefree_dev@localhost:5432/filefree_test",
)

_db_available = False
test_engine = None
TestSessionFactory = None

try:
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    TestSessionFactory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    _db_available = True
except Exception:
    pass


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_test_schema():
    """Create all tables once per test session. Skips if DB not available."""
    if not _db_available or test_engine is None:
        yield
        return
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass
    yield
    if test_engine is not None:
        await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional session that rolls back after each test."""
    if test_engine is None:
        pytest.skip("Database not available")
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with DB dependency overridden to use the test session."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def sync_client():
    """Sync TestClient for simple tests that don't need DB isolation."""
    from fastapi.testclient import TestClient

    return TestClient(fastapi_app)
