import json

from app.schemas.base import error_response, success_response


def test_success_response_format() -> None:
    response = success_response({"key": "value"})
    body = json.loads(response.body)
    assert body["success"] is True
    assert body["data"] == {"key": "value"}
    assert "error" not in body
    assert response.status_code == 200


def test_success_response_custom_status() -> None:
    response = success_response({"id": "123"}, status_code=201)
    assert response.status_code == 201
    body = json.loads(response.body)
    assert body["success"] is True


def test_error_response_format() -> None:
    response = error_response("Something went wrong", status_code=400)
    body = json.loads(response.body)
    assert body["success"] is False
    assert body["error"] == "Something went wrong"
    assert response.status_code == 400


def test_error_response_404() -> None:
    response = error_response("Not found", status_code=404)
    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["success"] is False
    assert body["error"] == "Not found"
