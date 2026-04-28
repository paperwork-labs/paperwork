"""Tests for ``scripts/cloudflare_issue_readonly_tokens.py`` (HTTP via ``opener``)."""

from __future__ import annotations

import json
from typing import Any

import cloudflare_issue_readonly_tokens as tok
import pytest


class _Resp:
    def __init__(self, obj: dict[str, Any], status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(obj).encode()

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        return None


def test_fetch_dns_read_permission_group_id() -> None:
    payload = {
        "success": True,
        "result": [
            {"id": "x", "name": "Account Settings Read"},
            {"id": "dns-read-id", "name": "DNS Read"},
        ],
    }

    def opener(req: Any, timeout: float = 60.0) -> Any:
        assert "permission_groups" in req.full_url
        return _Resp(payload)

    gid = tok.fetch_dns_read_permission_group_id(admin_token="t", opener=opener)
    assert gid == "dns-read-id"


def test_find_token_id_by_name() -> None:
    listed = {
        "success": True,
        "result": [{"id": "tid", "name": tok.ZONES[0].token_name, "status": "active"}],
        "result_info": {"page": 1, "total_pages": 1},
    }

    def opener(req: Any, timeout: float = 60.0) -> Any:
        if "/user/tokens" in req.full_url and req.get_method() == "GET":
            return _Resp(listed)
        raise AssertionError(req.full_url)

    found = tok.find_token_id_by_name(tok.ZONES[0].token_name, admin_token="t", opener=opener)
    assert found == "tid"


def test_run_issue_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing token + not rotate → no create / vault calls."""
    calls: list[tuple[str, str]] = []

    def opener(req: Any, timeout: float = 60.0) -> Any:
        url = req.full_url
        method = req.get_method()
        calls.append((method, url))
        if "permission_groups" in url:
            return _Resp({"success": True, "result": [{"id": "pg", "name": "DNS Read"}]})
        if method == "GET" and "/zones?name=" in url:
            return _Resp({"success": True, "result": [{"id": "zid", "name": "paperworklabs.com"}]})
        if method == "GET" and "/user/tokens" in url:
            return _Resp(
                {
                    "success": True,
                    "result": [{"id": "existing", "name": tok.ZONES[0].token_name}],
                    "result_info": {"page": 1, "total_pages": 1},
                }
            )
        raise AssertionError((method, url))

    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "admin")
    monkeypatch.delenv("SECRETS_API_KEY", raising=False)

    # Only first zone short-circuits; others still need tokens — patch ZONES to one entry
    monkeypatch.setattr(tok, "ZONES", (tok.ZONES[0],))

    rc = tok.run_issue(
        admin_token="admin",
        rotate=False,
        studio_url="https://example.test",
        dry_run_vault=True,
        opener=opener,
    )
    assert rc == 0
    posts = [c for c in calls if c[0] == "POST"]
    assert not any("user/tokens" in u for _, u in posts)


def test_run_issue_creates_with_dry_run_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def opener(req: Any, timeout: float = 60.0) -> Any:
        url = req.full_url
        method = req.get_method()
        calls.append((method, url))
        if "permission_groups" in url:
            return _Resp({"success": True, "result": [{"id": "pg", "name": "DNS Read"}]})
        if method == "GET" and "/zones?name=" in url:
            return _Resp({"success": True, "result": [{"id": "zid", "name": "paperworklabs.com"}]})
        if method == "GET" and "/user/tokens" in url:
            return _Resp(
                {"success": True, "result": [], "result_info": {"page": 1, "total_pages": 1}}
            )
        if method == "POST" and "/user/tokens" in url:
            return _Resp({"success": True, "result": {"id": "new", "value": "secret-value"}})
        raise AssertionError((method, url))

    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "admin")
    monkeypatch.setattr(tok, "ZONES", (tok.ZONES[0],))

    rc = tok.run_issue(
        admin_token="admin",
        rotate=False,
        studio_url="https://example.test",
        dry_run_vault=True,
        opener=opener,
    )
    assert rc == 0
    posts = [u for m, u in calls if m == "POST" and "/user/tokens" in u]
    assert len(posts) == 1
