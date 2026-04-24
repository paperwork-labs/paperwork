"""Tests for PeakRssMiddleware and hottest_endpoints in composite health."""

from __future__ import annotations

from unittest import mock

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.api.middleware import peak_rss
from app.api.middleware.peak_rss import (
    PeakRssMiddleware,
    is_observability_bypass_path,
    should_sample_for_request_id,
)
from app.services.market.admin_health_service import AdminHealthService
from app.services.observability import peak_rss_store
from app.services.observability.peak_rss_store import (
    get_hottest_endpoints_aggregated,
    ru_maxrss_raw_to_kib,
)


def test_bypass_path_health_never_sampled() -> None:
    assert is_observability_bypass_path("/health") is True
    assert is_observability_bypass_path("/docs") is True
    assert is_observability_bypass_path("/api/v1/market-data/admin/health") is True
    assert is_observability_bypass_path("/api/v1/something") is False


def test_10_percent_sampling_stable() -> None:
    rid = "deadbeef-cafe-4242-ffff-00000000abcd"
    assert should_sample_for_request_id(rid) is should_sample_for_request_id(rid)
    flags = {should_sample_for_request_id(f"req-{i}") for i in range(500)}
    assert True in flags and False in flags


def test_darwin_ru_maxrss_bytes_to_kib() -> None:
    with mock.patch("app.services.observability.peak_rss_store.platform", mock.MagicMock()) as p:
        p.system = mock.Mock(return_value="Darwin")
        assert ru_maxrss_raw_to_kib(1_048_576) == 1024  # 1 MiB in bytes -> 1024 KiB

    with mock.patch("app.services.observability.peak_rss_store.platform", mock.MagicMock()) as p2:
        p2.system = mock.Mock(return_value="Linux")
        assert ru_maxrss_raw_to_kib(1_200_000) == 1_200_000


@pytest.mark.asyncio
async def test_high_delta_emits_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ENABLE_PEAK_RSS_MIDDLEWARE", True, raising=False)

    _g_calls: list[int] = []

    def _getrusage(who: int):
        _g_calls.append(1)

        class R:
            pass

        r = R()
        if len(_g_calls) == 1:
            r.ru_maxrss = 1_000
        else:
            r.ru_maxrss = 1_000 + peak_rss_store.PEAK_RSS_WARN_DELTA_KIB + 50_000
        return r

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.1"},
        "http_version": "1.1",
        "server": ("test", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "root_path": "",
        "headers": [],
        "state": {},
        "method": "GET",
        "path": "/api/v1/under-test",
        "raw_path": b"/api/v1/under-test",
        "query_string": b"",
    }
    request = Request(scope)
    with mock.patch.object(peak_rss.logger, "warning") as wmock:
        with mock.patch("app.api.middleware.peak_rss.get_request_id", return_value="x-req-1"):
            with mock.patch(
                "app.api.middleware.peak_rss.should_sample_for_request_id", return_value=True
            ):
                with mock.patch(
                    "app.api.middleware.peak_rss.is_observability_bypass_path", return_value=False
                ):
                    with mock.patch(
                        "app.api.middleware.peak_rss._get_sync_redis", return_value=None
                    ):
                        with mock.patch(
                            "app.api.middleware.peak_rss._path_template_for_metrics",
                            return_value="/api/v1/under-test",
                        ):
                            with mock.patch(
                                "app.services.observability.peak_rss_store.platform",
                                mock.MagicMock(),
                            ) as p_sys:
                                p_sys.system = mock.Mock(return_value="Linux")
                                with mock.patch(
                                    "app.api.middleware.peak_rss.resource.getrusage",
                                    side_effect=_getrusage,
                                ):
                                    tm = mock.MagicMock()
                                    tm.get_traced_memory = mock.Mock(return_value=(0, 0))
                                    with mock.patch("app.api.middleware.peak_rss.tracemalloc", tm):
                                        mw = PeakRssMiddleware(lambda _req: PlainTextResponse("x"))

                                        async def _next(_r) -> PlainTextResponse:
                                            return PlainTextResponse("x")

                                        await mw.dispatch(request, _next)
    assert wmock.call_count >= 1
    joined = " ".join(str(c) for c in wmock.call_args_list)
    assert "500MiB" in joined
    assert len(_g_calls) == 2, _g_calls


def test_hottest_aggregated_percentiles() -> None:
    mredis = mock.MagicMock()
    mredis.scan_iter.return_value = [b"apiv1:obs:peak_rss:GET:/api/v1/foo"]
    mredis.zrange.return_value = [
        b"000000010240\x00aa",
        b"000000020480\x00bb",
        b"000000030000\x00cc",
    ]
    rows, err = get_hottest_endpoints_aggregated(mredis)
    assert err is None
    assert len(rows) == 1
    r0 = rows[0]
    assert r0["route"] == "GET:/api/v1/foo"
    assert r0["samples"] == 3
    assert r0["max_peak_mb"] == round(30000 / 1024.0)
    assert "p50_peak_mb" in r0
    assert "p95_peak_mb" in r0


def test_hottest_redis_unreachable() -> None:
    rows, err = get_hottest_endpoints_aggregated(None)
    assert rows is None
    assert err == "redis_unreachable"

    m = mock.MagicMock()
    m.scan_iter.side_effect = OSError("down")
    rows2, err2 = get_hottest_endpoints_aggregated(m)
    assert rows2 is None
    assert err2 == "redis_unreachable"


def test_composite_merge_hottest_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = AdminHealthService()
    r = mock.MagicMock()
    monkeypatch.setattr("app.config.settings.ENABLE_PEAK_RSS_MIDDLEWARE", True, raising=False)
    with mock.patch(
        "app.services.observability.peak_rss_store.get_hottest_endpoints_aggregated",
        return_value=(
            [
                {
                    "route": "GET:/x",
                    "samples": 2,
                    "p50_peak_mb": 1,
                    "p95_peak_mb": 2,
                    "max_peak_mb": 3,
                }
            ],
            None,
        ),
    ):
        p: dict = {"composite_status": "green", "composite_reason": "ok", "dimensions": {}}
        svc._merge_peak_hottest_endpoints(p, r)
    assert p["hottest_endpoints"] is not None
    assert p["hottest_endpoints_error"] is None
    monkeypatch.setattr("app.config.settings.ENABLE_PEAK_RSS_MIDDLEWARE", True, raising=False)
    with mock.patch(
        "app.services.observability.peak_rss_store.get_hottest_endpoints_aggregated",
        return_value=(None, "redis_unreachable"),
    ):
        p2: dict = {"composite_status": "green"}
        svc._merge_peak_hottest_endpoints(p2, r)
    assert p2["hottest_endpoints"] is None
    assert p2["hottest_endpoints_error"] == "redis_unreachable"
    monkeypatch.setattr("app.config.settings.ENABLE_PEAK_RSS_MIDDLEWARE", False, raising=False)
    p3: dict = {}
    svc._merge_peak_hottest_endpoints(p3, r)
    assert p3["hottest_endpoints"] is None
    assert p3["hottest_endpoints_error"] == "disabled"
