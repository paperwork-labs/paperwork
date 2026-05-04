"""Tests for ``brain_user_vault`` repository (T1.4 / D61)."""

from __future__ import annotations

import base64
import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import update
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models.vault import UserVault
from app.repositories import brain_user_vault as vault_repo
from app.security.brain_user_vault_crypto import VaultDecryptionError

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://brain:brain_dev@localhost:5432/brain_test",
)


def _reset_vault_table(sync_conn: Connection) -> None:
    """Create only ``brain_user_vault`` — full ``Base.metadata.create_all`` needs pgvector."""
    UserVault.__table__.drop(sync_conn, checkfirst=True)
    UserVault.__table__.create(sync_conn, checkfirst=True)


@pytest_asyncio.fixture
async def vault_db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(_reset_vault_table)
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


@pytest.fixture(autouse=True)
def _brain_user_vault_aes_key(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = base64.b64encode(os.urandom(32)).decode("ascii")
    monkeypatch.setattr(settings, "BRAIN_USER_VAULT_ENCRYPTION_KEY", raw)


@pytest.fixture
def user_one() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def user_two() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_set_get_roundtrip(vault_db_session: AsyncSession, user_one: str) -> None:
    await vault_repo.set_secret(user_one, "my-key", "payload-one", db=vault_db_session)
    await vault_db_session.flush()
    got = await vault_repo.get_secret(user_one, "my-key", db=vault_db_session)
    assert got == "payload-one"


@pytest.mark.asyncio
async def test_set_updates_existing(vault_db_session: AsyncSession, user_one: str) -> None:
    await vault_repo.set_secret(user_one, "k", "v1", db=vault_db_session)
    await vault_repo.set_secret(user_one, "k", "v2", db=vault_db_session)
    await vault_db_session.flush()
    assert await vault_repo.get_secret(user_one, "k", db=vault_db_session) == "v2"


@pytest.mark.asyncio
async def test_get_missing_returns_none(vault_db_session: AsyncSession, user_one: str) -> None:
    assert await vault_repo.get_secret(user_one, "nope", db=vault_db_session) is None


@pytest.mark.asyncio
async def test_list_keys_only_no_values(vault_db_session: AsyncSession, user_one: str) -> None:
    await vault_repo.set_secret(user_one, "alpha", "secret-alpha", db=vault_db_session)
    await vault_repo.set_secret(user_one, "beta", "secret-beta", db=vault_db_session)
    await vault_db_session.flush()
    entries = await vault_repo.list_secrets(user_one, db=vault_db_session)
    keys = sorted(e.key for e in entries)
    assert keys == ["alpha", "beta"]
    for e in entries:
        dumped = e.model_dump()
        assert "value" not in dumped
        assert set(dumped.keys()) == {"key", "created_at", "updated_at"}


@pytest.mark.asyncio
async def test_delete_returns_bool(vault_db_session: AsyncSession, user_one: str) -> None:
    await vault_repo.set_secret(user_one, "rm", "x", db=vault_db_session)
    await vault_db_session.flush()
    assert await vault_repo.delete_secret(user_one, "rm", db=vault_db_session) is True
    await vault_db_session.flush()
    assert await vault_repo.delete_secret(user_one, "rm", db=vault_db_session) is False


@pytest.mark.asyncio
async def test_cross_user_isolation(
    vault_db_session: AsyncSession, user_one: str, user_two: str
) -> None:
    await vault_repo.set_secret(user_one, "shared-name", "only-u1", db=vault_db_session)
    await vault_db_session.flush()
    assert await vault_repo.get_secret(user_two, "shared-name", db=vault_db_session) is None


@pytest.mark.asyncio
async def test_decrypt_failure_raises_typed_error(
    vault_db_session: AsyncSession, user_one: str
) -> None:
    await vault_repo.set_secret(user_one, "k", "good", db=vault_db_session)
    await vault_db_session.flush()
    await vault_db_session.execute(
        update(UserVault)
        .where(UserVault.user_id == user_one, UserVault.name == "k")
        .values(encrypted_value="bogus")
    )
    await vault_db_session.flush()
    with pytest.raises(VaultDecryptionError):
        await vault_repo.get_secret(user_one, "k", db=vault_db_session)
