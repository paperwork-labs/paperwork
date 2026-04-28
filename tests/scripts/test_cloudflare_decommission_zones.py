"""Unit tests for ``scripts/cloudflare_decommission_zones.py`` (mocked HTTP + dig)."""

from __future__ import annotations

import json
from typing import Any

import cloudflare_decommission_zones as dec
import pytest


def _zones_payload(zones: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "success": True,
        "result": zones,
        "result_info": {"page": 1, "per_page": 50, "count": len(zones), "total_pages": 1},
    }


class _FakeJsonResp:
    def __init__(self, obj: dict[str, Any], status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(obj).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> _FakeJsonResp:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _make_opener(
    *,
    zones: list[dict[str, Any]],
    delete_ok: bool = True,
    log: list[tuple[str, str]] | None = None,
) -> Any:
    """Return opener(req, timeout) suitable for :func:`dec.cf_request_json`."""

    def opener(req: Any, timeout: float = 60.0) -> Any:
        url = req.full_url
        method = req.get_method()
        if log is not None:
            log.append((method, url))
        if method == "GET" and "/zones?" in url and "status=active" in url:
            return _FakeJsonResp(_zones_payload(zones))
        if method == "DELETE" and "/zones/" in url:
            if delete_ok:
                return _FakeJsonResp({"success": True, "result": {"id": "deleted"}})
            return _FakeJsonResp({"success": False, "errors": []}, status=500)
        raise AssertionError(f"unexpected {method} {url!r}")

    return opener


OLD_NS = ("kate.ns.cloudflare.com", "ivan.ns.cloudflare.com")
NEW_NS = ("janet.ns.cloudflare.com", "noel.ns.cloudflare.com")


def _zone(name: str, zid: str, ns: tuple[str, ...]) -> dict[str, Any]:
    return {"id": zid, "name": name, "name_servers": list(ns)}


@pytest.fixture
def five_zones() -> list[dict[str, Any]]:
    return [
        _zone("axiomfolio.com", "z1", OLD_NS),
        _zone("distill.tax", "z2", OLD_NS),
        _zone("filefree.ai", "z3", OLD_NS),
        _zone("launchfree.ai", "z4", OLD_NS),
        _zone("paperworklabs.com", "z5", OLD_NS),
    ]


def test_dry_run_all_pass(five_zones: list[dict[str, Any]]) -> None:
    log: list[tuple[str, str]] = []
    opener = _make_opener(zones=five_zones, log=log)

    def dig(_ip: str, name: str, qtype: str) -> tuple[int, list[str]]:
        if qtype == "NS":
            return 0, list(NEW_NS)
        return 0, ["10 mail.example.com.", "v=spf1 ~all"]

    rc = dec.run(token="tok", apply=False, dig=dig, opener=opener)
    assert rc == 0
    assert any(m == "GET" and "status=active" in u for m, u in log)


def test_precondition_fails_when_ns_still_old(five_zones: list[dict[str, Any]]) -> None:
    opener = _make_opener(zones=five_zones)

    def dig(_ip: str, name: str, qtype: str) -> tuple[int, list[str]]:
        if qtype == "NS":
            return 0, list(OLD_NS)
        return 0, ["x"]

    rc = dec.run(token="tok", apply=False, dig=dig, opener=opener)
    assert rc == 1


def test_apply_deletes_when_all_pass(five_zones: list[dict[str, Any]]) -> None:
    log: list[tuple[str, str]] = []
    opener = _make_opener(zones=five_zones, log=log)

    def dig(_ip: str, name: str, qtype: str) -> tuple[int, list[str]]:
        if qtype == "NS":
            return 0, list(NEW_NS)
        return 0, ["mx 10 mail.", "txt"]

    rc = dec.run(token="tok", apply=True, dig=dig, opener=opener)
    assert rc == 0
    deletes = [u for m, u in log if m == "DELETE"]
    assert len(deletes) == 5


def test_missing_zone_fails() -> None:
    zones = [_zone("paperworklabs.com", "z5", OLD_NS)]
    opener = _make_opener(zones=zones)

    def dig(_ip: str, name: str, qtype: str) -> tuple[int, list[str]]:
        if qtype == "NS":
            return 0, list(NEW_NS)
        return 0, ["ok"]

    rc = dec.run(token="tok", apply=False, dig=dig, opener=opener)
    assert rc == 1


def test_list_all_zones_pagination() -> None:
    z1 = _zone("paperworklabs.com", "a", OLD_NS)
    z2 = _zone("axiomfolio.com", "b", OLD_NS)
    p1 = _zones_payload([z1])
    p1["result_info"] = {"page": 1, "per_page": 1, "count": 2, "total_pages": 2}
    p2 = _zones_payload([z2])
    p2["result_info"] = {"page": 2, "per_page": 1, "count": 2, "total_pages": 2}
    calls: list[str] = []

    def opener(req: Any, timeout: float = 60.0) -> Any:
        calls.append(req.full_url)
        if "page=1" in req.full_url:
            return _FakeJsonResp(p1)
        if "page=2" in req.full_url:
            return _FakeJsonResp(p2)
        raise AssertionError(req.full_url)

    out = dec.list_all_zones(token="x", opener=opener)
    assert len(out) == 2
    assert len(calls) == 2
