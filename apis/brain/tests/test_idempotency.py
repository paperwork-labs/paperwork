import pytest

from app.services.idempotency import check_and_set


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def set(self, key, value, *, nx=False, ex=None):  # noqa: ARG002
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True


@pytest.mark.asyncio
async def test_first_request_is_not_duplicate():
    redis = FakeRedis()
    assert await check_and_set(redis, "req-1") is False


@pytest.mark.asyncio
async def test_second_request_is_duplicate():
    redis = FakeRedis()
    await check_and_set(redis, "req-1")
    assert await check_and_set(redis, "req-1") is True


@pytest.mark.asyncio
async def test_no_redis_skips_check():
    assert await check_and_set(None, "req-1") is False


@pytest.mark.asyncio
async def test_no_request_id_skips_check():
    redis = FakeRedis()
    assert await check_and_set(redis, "") is False
