"""Response envelope helpers."""

from __future__ import annotations

import json

from starlette.testclient import TestClient

from api_foundation.responses import error_response, success_response


def _body_utf8(payload: bytes | memoryview[int]) -> str:
    return bytes(payload).decode("utf-8")


def test_success_response_envelope_shape() -> None:
    r = success_response({"items": [1]})
    raw = _body_utf8(r.body)
    assert json.loads(raw) == {"success": True, "data": {"items": [1]}}
    assert r.status_code == 200


def test_success_response_custom_status() -> None:
    r = success_response({"a": 1}, status_code=201)
    assert r.status_code == 201


def test_error_response_envelope_shape() -> None:
    r = error_response("X", "oops", status_code=422)
    raw = _body_utf8(r.body)
    parsed = json.loads(raw)
    assert parsed == {"success": False, "error": {"code": "X", "message": "oops"}}
    assert r.status_code == 422


def test_helpers_work_from_fastapi_route() -> None:
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/ok")
    async def ok() -> object:
        return success_response({"ok": True})

    @app.get("/nope")
    async def nope() -> object:
        return error_response("E", "bad", status_code=400)

    client = TestClient(app, raise_server_exceptions=False)
    ok_r = client.get("/ok")
    assert ok_r.json() == {"success": True, "data": {"ok": True}}
    nope_r = client.get("/nope")
    assert nope_r.json() == {
        "success": False,
        "error": {"code": "E", "message": "bad"},
    }
