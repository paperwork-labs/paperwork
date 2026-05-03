"""Branch coverage for :mod:`rate_limit.storage_failopen`."""

from __future__ import annotations

import pytest
from limits.storage import storage_from_string

from rate_limit import create_limiter
from rate_limit.storage_failopen import FailOpenRedisStorage, _inner_redis_uri


def test_inner_redis_uri_failopen_rediss() -> None:
    assert _inner_redis_uri("failopen-rediss://x:6380/0").startswith("rediss://")


def test_inner_redis_uri_invalid_scheme() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        _inner_redis_uri("http://localhost")


def test_storage_base_exceptions_delegates() -> None:
    limiter = create_limiter(redis_url="redis://127.0.0.1:6379/0")
    storage = limiter._storage
    assert isinstance(storage, FailOpenRedisStorage)
    assert storage.base_exceptions == storage._inner.base_exceptions


def test_record_skips_when_no_degradation_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = storage_from_string(
        "failopen-redis://127.0.0.1:6379/0",
        socket_connect_timeout=0.01,
    )
    assert isinstance(storage, FailOpenRedisStorage)
    storage._degradation = None

    def boom(*_a: object, **_k: object) -> int:
        raise OSError("ignored for degradation")

    monkeypatch.setattr(storage._inner, "incr", boom)
    assert storage.incr("k", 60) == 0


def test_fail_open_each_inner_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limiter = create_limiter(redis_url="redis://127.0.0.1:6379/0")
    storage = limiter._storage
    assert isinstance(storage, FailOpenRedisStorage)
    inner = storage._inner

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("inner boom")

    monkeypatch.setattr(inner, "get", boom)
    assert storage.get("k") == 0

    monkeypatch.setattr(inner, "get_expiry", boom)
    out = storage.get_expiry("k")
    assert isinstance(out, float)

    monkeypatch.setattr(inner, "clear", boom)
    storage.clear("k")

    monkeypatch.setattr(inner, "check", boom)
    assert storage.check() is False

    monkeypatch.setattr(inner, "reset", boom)
    assert storage.reset() is None

    monkeypatch.setattr(inner, "get_moving_window", boom)
    start, n = storage.get_moving_window("k", 3, 60)
    assert isinstance(start, float)
    assert n == 0

    monkeypatch.setattr(inner, "acquire_entry", boom)
    assert storage.acquire_entry("k", 3, 60) is True

    monkeypatch.setattr(inner, "get_sliding_window", boom)
    tup = storage.get_sliding_window("k", 60)
    assert tup == (0, 0.0, 0, 0.0)

    monkeypatch.setattr(inner, "acquire_sliding_window_entry", boom)
    assert storage.acquire_sliding_window_entry("k", 3, 60) is True

    monkeypatch.setattr(inner, "clear_sliding_window", boom)
    storage.clear_sliding_window("k", 60)

    monkeypatch.setattr(inner, "incr", boom)
    assert storage.incr("k2", 60) == 0

    snap = limiter.degradation_snapshot()
    assert snap["count"] >= 1
    assert "inner boom" in (snap["last_error"] or "")


def test_record_inner_try_swallows_mutation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limiter = create_limiter(redis_url="redis://127.0.0.1:6379/0")
    storage = limiter._storage
    assert isinstance(storage, FailOpenRedisStorage)

    class BadDegradation(dict[str, object]):
        def __getitem__(self, key: str) -> object:  # type: ignore[override]
            if key == "count":
                raise RuntimeError("no mutate")
            return super().__getitem__(key)

    storage._degradation = BadDegradation(
        {"count": 0, "last_error": None, "last_at": None}
    )

    def boom(*_a: object, **_k: object) -> int:
        raise OSError("boom")

    monkeypatch.setattr(storage._inner, "incr", boom)
    assert storage.incr("k", 60) == 0
