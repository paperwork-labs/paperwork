"""Tests for admin agent chat validation and inline-only tool routing."""

import os

import pytest
from fastapi.testclient import TestClient

def _test_client_or_skip() -> tuple[TestClient, object]:
    try:
        from app.api.dependencies import get_admin_user
        from app.api.main import app
    except RuntimeError as e:
        if "TEST_DATABASE_URL" in str(e):
            pytest.skip(str(e))
        raise
    return TestClient(app, raise_server_exceptions=False), get_admin_user


def test_agent_chat_whitespace_only_message_returns_422() -> None:
    """Pydantic rejects empty / whitespace-only body before LLM or DB work."""
    client, get_admin_user = _test_client_or_skip()
    app = client.app
    app.dependency_overrides[get_admin_user] = object
    try:
        resp = client.post("/api/v1/admin/agent/chat", json={"message": "   \t  "})
        assert resp.status_code == 422
        detail = resp.json().get("detail")
        assert detail is not None
    finally:
        app.dependency_overrides.pop(get_admin_user, None)


@pytest.mark.asyncio
async def test_execute_tool_read_file_moderate_runs_inline_not_celery(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MODERATE read_file must use _execute_safe_tool, not Celery (no task mapping)."""
    from app.config import settings
    from app.services.agent.brain import AgentBrain

    if db_session is None:
        pytest.skip("requires database")

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(settings, "AGENT_AUTONOMY_LEVEL", "safe")

    brain = AgentBrain(db=db_session)
    celery_calls: list[str] = []

    async def track_celery_dispatch(tool_name: str, _args: dict) -> dict:
        celery_calls.append(tool_name)
        return {"error": "celery should not run for read_file"}

    monkeypatch.setattr(brain, "_dispatch_celery_task", track_celery_dispatch)

    result, action = await brain._execute_tool(
        "read_file",
        {"path": "tests/fixtures/agent_read_file_sample.txt"},
        "unit test",
    )

    assert not celery_calls, "read_file must not dispatch to Celery"
    assert action.status == "completed"
    assert result.get("path") == "tests/fixtures/agent_read_file_sample.txt"
    assert "line1" in (result.get("content") or "")


@pytest.mark.asyncio
async def test_tool_check_broker_uses_singleton_not_missing_get_instance(
    db_session,
) -> None:
    """check_broker_connection must not call IBKRClient.get_instance() (undefined)."""
    from app.services.agent.brain import AgentBrain

    if db_session is None:
        pytest.skip("requires database")

    brain = AgentBrain(db=db_session)
    out = await brain._tool_check_broker("ibkr")
    assert "ibkr" in out
    ibkr = out["ibkr"]
    assert "connected" in ibkr, ibkr
    assert isinstance(ibkr["connected"], bool)
    assert "health_status" in ibkr
