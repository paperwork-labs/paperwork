"""Unit tests for :class:`backend.services.deploys.render_client.RenderDeployClient`.

We monkeypatch ``httpx.get`` so these tests have no network dep and do not
require a new test library (``respx`` is not used elsewhere in the repo).

Covered:

* normal list-of-dicts response shape
* ``[{"deploy": {...}, "cursor": "..."}]`` wrapper shape
* ``{"deploys": [...]}`` wrapper shape
* 401 auth failure -> ``RenderDeployClientError``
* network failure -> ``RenderDeployClientError``
* disabled client (no API key) -> raises on call, ``enabled == False``
* ``DeployRecord`` derived properties (``short_sha``, ``is_live``,
  ``is_failure``, ``is_terminal``)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
import pytest

pytestmark = pytest.mark.no_db

from backend.services.deploys.render_client import (
    RENDER_API_BASE,
    DeployRecord,
    RenderDeployClient,
    RenderDeployClientError,
)


class _StubResponse:
    def __init__(self, *, status_code: int, payload: Any, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ""

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _deploy_payload(
    deploy_id: str,
    status: str,
    *,
    sha: str = "deadbeefdeadbeef",
    created: str = "2026-04-21T04:11:05Z",
    finished: str = "2026-04-21T04:12:50Z",
) -> Dict[str, Any]:
    return {
        "id": deploy_id,
        "status": status,
        "trigger": "new_commit",
        "commit": {"id": sha, "message": "feat: xyz"},
        "createdAt": created,
        "finishedAt": finished,
    }


@pytest.fixture
def stub_httpx(monkeypatch):
    calls: List[Dict[str, Any]] = []
    next_response: Dict[str, Any] = {"response": None, "error": None}

    def fake_get(url, *, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        if next_response["error"] is not None:
            raise next_response["error"]
        response = next_response["response"]
        assert response is not None, "test did not configure a response"
        return response

    monkeypatch.setattr(httpx, "get", fake_get)

    class Stub:
        def set_response(self, *, status_code: int, payload: Any, text: str = ""):
            next_response["error"] = None
            next_response["response"] = _StubResponse(
                status_code=status_code, payload=payload, text=text
            )

        def set_error(self, exc: Exception):
            next_response["error"] = exc
            next_response["response"] = None

        @property
        def calls(self) -> List[Dict[str, Any]]:
            return calls

    return Stub()


def test_client_disabled_when_api_key_missing():
    client = RenderDeployClient(api_key=None)
    assert client.enabled is False
    with pytest.raises(RenderDeployClientError):
        client.list_deploys("srv-x")


def test_list_deploys_bare_list(stub_httpx):
    stub_httpx.set_response(
        status_code=200,
        payload=[
            _deploy_payload("d1", "live"),
            _deploy_payload("d2", "build_failed"),
        ],
    )
    client = RenderDeployClient(api_key="sekret")
    out = client.list_deploys("srv-x", limit=5)
    assert len(out) == 2
    assert isinstance(out[0], DeployRecord)
    assert out[0].is_live and not out[0].is_failure
    assert out[1].is_failure and not out[1].is_live
    assert out[0].service_id == "srv-x"
    assert out[0].duration_seconds is not None and out[0].duration_seconds > 0

    call = stub_httpx.calls[-1]
    assert call["url"] == f"{RENDER_API_BASE}/services/srv-x/deploys"
    assert call["headers"]["Authorization"] == "Bearer sekret"
    assert call["params"] == {"limit": "5"}


def test_list_deploys_wrapped_deploy_objects(stub_httpx):
    stub_httpx.set_response(
        status_code=200,
        payload=[
            {"deploy": _deploy_payload("d1", "live"), "cursor": "abc"},
            {"deploy": _deploy_payload("d2", "build_failed"), "cursor": "def"},
        ],
    )
    client = RenderDeployClient(api_key="sekret")
    out = client.list_deploys("srv-x")
    assert [d.deploy_id for d in out] == ["d1", "d2"]


def test_list_deploys_dict_shape(stub_httpx):
    stub_httpx.set_response(
        status_code=200,
        payload={"deploys": [_deploy_payload("d1", "live")]},
    )
    client = RenderDeployClient(api_key="sekret")
    out = client.list_deploys("srv-x")
    assert len(out) == 1 and out[0].deploy_id == "d1"


def test_list_deploys_401_raises(stub_httpx):
    stub_httpx.set_response(status_code=401, payload={"error": "no"}, text='{"error":"no"}')
    client = RenderDeployClient(api_key="sekret")
    with pytest.raises(RenderDeployClientError) as excinfo:
        client.list_deploys("srv-x")
    assert "401" in str(excinfo.value)


def test_list_deploys_network_error_raises(stub_httpx):
    stub_httpx.set_error(httpx.ConnectError("boom"))
    client = RenderDeployClient(api_key="sekret")
    with pytest.raises(RenderDeployClientError) as excinfo:
        client.list_deploys("srv-x")
    assert "network error" in str(excinfo.value).lower()


def test_list_deploys_invalid_json_raises(stub_httpx):
    stub_httpx.set_response(status_code=200, payload=ValueError("bad"))
    client = RenderDeployClient(api_key="sekret")
    with pytest.raises(RenderDeployClientError):
        client.list_deploys("srv-x")


def test_list_deploys_limit_clamped(stub_httpx):
    stub_httpx.set_response(status_code=200, payload=[])
    client = RenderDeployClient(api_key="sekret")
    client.list_deploys("srv-x", limit=999)
    assert stub_httpx.calls[-1]["params"] == {"limit": "50"}
    client.list_deploys("srv-x", limit=-3)
    assert stub_httpx.calls[-1]["params"] == {"limit": "1"}


def test_deploy_record_short_sha_and_states():
    live = DeployRecord(
        service_id="s",
        deploy_id="d",
        status="live",
        trigger=None,
        commit_sha="abcdef1234567890",
        commit_message="msg",
        created_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        finished_at=datetime(2026, 4, 21, 0, 2, tzinfo=timezone.utc),
        duration_seconds=120.0,
    )
    assert live.short_sha == "abcdef12"
    assert live.is_terminal and live.is_live
    assert not live.is_failure and not live.is_superseded

    failed = DeployRecord(
        service_id="s",
        deploy_id="d2",
        status="build_failed",
        trigger=None,
        commit_sha=None,
        commit_message=None,
        created_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        finished_at=datetime(2026, 4, 21, 0, 0, 1, tzinfo=timezone.utc),
        duration_seconds=1.0,
    )
    assert failed.is_failure and not failed.is_live
    assert failed.short_sha == ""

    superseded = DeployRecord(
        service_id="s",
        deploy_id="d3",
        status="deactivated",
        trigger=None,
        commit_sha="c" * 40,
        commit_message=None,
        created_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        finished_at=None,
        duration_seconds=None,
    )
    assert superseded.is_superseded and superseded.is_terminal


def test_get_service_happy_path(stub_httpx):
    stub_httpx.set_response(
        status_code=200,
        payload={"id": "srv-x", "slug": "axiomfolio-api", "type": "web_service"},
    )
    client = RenderDeployClient(api_key="sekret")
    payload = client.get_service("srv-x")
    assert payload["slug"] == "axiomfolio-api"


def test_get_service_disabled_raises():
    client = RenderDeployClient(api_key=None)
    with pytest.raises(RenderDeployClientError):
        client.get_service("srv-x")
