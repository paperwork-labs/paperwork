"""Tests for RSS observability fields on the composite /admin/health response."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.services.market.admin_health_service import _RSS_OBSERVABILITY_KEYS, AdminHealthService
from app.services.observability import rss_store


class _MemoryRedis:
    def __init__(self) -> None:
        self.lists: dict[str, list[bytes]] = {}
        self.kv: dict[str, bytes] = {}

    def lrange(self, k: str, a: int, b: int) -> list[bytes]:
        return list(self.lists.get(k, []))

    def get(self, k: str):
        return self.kv.get(k)

    def set(self, k: str, v) -> bool:
        self.kv[k] = str(v).encode() if not isinstance(v, (bytes, bytearray)) else v
        return True


def test_get_rss_health_payload_top_and_percentiles():
    r = _MemoryRedis()
    bucket = datetime.now(UTC).strftime("%Y%m%d%H")
    lkey = rss_store._logkey(bucket)
    ckey = rss_store._countkey(bucket)
    for d in (1024, 2048, 4096, 5120, 10240, 25600, 100000, 200000, 200000, 200000):
        row = json.dumps(
            {"m": "GET", "p": "/api/v1/foo", "d": d}, separators=(",", ":"), sort_keys=True
        )
        r.lists.setdefault(lkey, []).append(row.encode())
    r.set(ckey, 10)

    p = rss_store.get_rss_health_payload(r)
    assert "top_rss_endpoints" in p
    assert "worker_request_count_last_hour" in p
    assert p["worker_request_count_last_hour"] == 10
    assert len(p["top_rss_endpoints"]) >= 1
    e0 = p["top_rss_endpoints"][0]
    assert e0["path"] == "/api/v1/foo"
    assert e0["method"] == "GET"
    assert e0["count"] == 10
    assert e0["p50_rss_kb"] > 0
    assert e0["p99_rss_kb"] > 0


def test_admin_merge_includes_rss_keys(monkeypatch):
    r = _MemoryRedis()
    bucket = datetime.now(UTC).strftime("%Y%m%d%H")
    lkey = rss_store._logkey(bucket)
    r.lists[lkey] = [
        json.dumps(
            {"m": "GET", "p": "/x", "d": 10240},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ]
    r.set(rss_store._countkey(bucket), 1)

    monkeypatch.setattr("app.config.settings.ENABLE_RSS_OBSERVABILITY", True, raising=False)

    svc = AdminHealthService()
    payload = {
        "composite_status": "green",
        "composite_reason": "ok",
        "dimensions": {},
        "task_runs": {},
    }
    svc._merge_rss_observability_fields(payload, r)
    assert "top_rss_endpoints" in payload
    assert "worker_request_count_last_hour" in payload
    assert "rss_observability" in payload
    assert payload["worker_request_count_last_hour"] >= 0


def test_rss_flag_disabled_empties_block(monkeypatch):
    monkeypatch.setattr("app.config.settings.ENABLE_RSS_OBSERVABILITY", False, raising=False)
    svc = AdminHealthService()
    payload = {"composite_status": "green"}
    svc._merge_rss_observability_fields(payload, _MemoryRedis())
    assert payload["top_rss_endpoints"] == []
    assert payload["worker_request_count_last_hour"] == 0
    assert payload["rss_observability"].get("disabled") is True


def test_composite_cache_excludes_rss_keys():
    assert "top_rss_endpoints" in _RSS_OBSERVABILITY_KEYS
    assert "rss_observability" in _RSS_OBSERVABILITY_KEYS
