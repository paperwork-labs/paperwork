"""Unit tests for ``scripts/post_deploy_smoke.py`` (T3.7).

Loads the script module by path so ``sys.path`` bootstrap matches CLI execution.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

_BRAIN_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "post_deploy_smoke_under_test",
    _BRAIN_ROOT / "scripts" / "post_deploy_smoke.py",
)
assert _SPEC and _SPEC.loader
smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(smoke)


def _client_cm(fake_inner: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value = fake_inner
    cm.__exit__.return_value = None
    return cm


@pytest.mark.no_pg_conv
def test_all_green_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_API_URL", "https://brain.example.test")

    fake_inner = MagicMock()
    fake_inner.get.side_effect = [
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "ok"}},
        ),
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "healthy"}},
        ),
        httpx.Response(200, json=[{"id": smoke.AUTOPILOT_JOB_ID}]),
    ]
    fake_inner.post = MagicMock()

    with (
        patch.object(smoke.httpx, "Client", return_value=_client_cm(fake_inner)),
        patch.object(
            smoke,
            "sync_probe_agent_dispatches_table",
            return_value=(True, "ok"),
        ),
    ):
        code = smoke.run_smoke(ci_mode=True, report_conversation=False)

    assert code == 0
    fake_inner.post.assert_not_called()


@pytest.mark.no_pg_conv
def test_health_500_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_API_URL", "https://brain.example.test")

    fake_inner = MagicMock()
    fake_inner.get.side_effect = [
        httpx.Response(500, json={}),
        httpx.Response(404),
        httpx.Response(200, json=[]),
    ]

    with (
        patch.object(smoke.httpx, "Client", return_value=_client_cm(fake_inner)),
        patch.object(
            smoke,
            "sync_probe_agent_dispatches_table",
            return_value=(True, "ok"),
        ),
    ):
        code = smoke.run_smoke(ci_mode=True, report_conversation=False)

    assert code == 1


@pytest.mark.no_pg_conv
def test_health_deep_404_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_API_URL", "https://brain.example.test")

    fake_inner = MagicMock()
    fake_inner.get.side_effect = [
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "ok"}},
        ),
        httpx.Response(404),
        httpx.Response(200, json=[{"id": smoke.AUTOPILOT_JOB_ID}]),
    ]

    with (
        patch.object(smoke.httpx, "Client", return_value=_client_cm(fake_inner)),
        patch.object(
            smoke,
            "sync_probe_agent_dispatches_table",
            return_value=(True, "ok"),
        ),
    ):
        code = smoke.run_smoke(ci_mode=True, report_conversation=False)

    assert code == 0


@pytest.mark.no_pg_conv
def test_db_unreachable_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_API_URL", "https://brain.example.test")

    fake_inner = MagicMock()
    fake_inner.get.side_effect = [
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "ok"}},
        ),
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "healthy"}},
        ),
        httpx.Response(200, json=[{"id": smoke.AUTOPILOT_JOB_ID}]),
    ]

    with (
        patch.object(smoke.httpx, "Client", return_value=_client_cm(fake_inner)),
        patch.object(
            smoke,
            "sync_probe_agent_dispatches_table",
            return_value=(False, "ConnectionRefusedError"),
        ),
    ):
        code = smoke.run_smoke(ci_mode=True, report_conversation=False)

    assert code == 1


@pytest.mark.no_pg_conv
def test_schedulers_no_autopilot_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_API_URL", "https://brain.example.test")

    fake_inner = MagicMock()
    fake_inner.get.side_effect = [
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "ok"}},
        ),
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "healthy"}},
        ),
        httpx.Response(200, json=[{"id": "brain_daily_briefing"}]),
    ]

    with (
        patch.object(smoke.httpx, "Client", return_value=_client_cm(fake_inner)),
        patch.object(
            smoke,
            "sync_probe_agent_dispatches_table",
            return_value=(True, "ok"),
        ),
    ):
        code = smoke.run_smoke(ci_mode=True, report_conversation=False)

    assert code == 0


@pytest.mark.no_pg_conv
def test_report_conversation_on_failure_posts_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAIN_API_URL", "https://brain.example.test")
    monkeypatch.setenv("BRAIN_ADMIN_TOKEN", "test-admin-secret")

    fake_inner = MagicMock()
    fake_inner.get.side_effect = [
        httpx.Response(500, json={}),
        httpx.Response(404),
        httpx.Response(200, json=[]),
    ]
    fake_inner.post.return_value = httpx.Response(201, json={"success": True})

    with (
        patch.object(smoke.httpx, "Client", return_value=_client_cm(fake_inner)),
        patch.object(
            smoke,
            "sync_probe_agent_dispatches_table",
            return_value=(True, "ok"),
        ),
    ):
        code = smoke.run_smoke(ci_mode=True, report_conversation=True)

    assert code == 1
    assert fake_inner.post.call_count == 1
    kwargs = fake_inner.post.call_args.kwargs
    hdrs = kwargs["headers"]
    assert hdrs["X-Brain-Secret"] == "test-admin-secret"
    posted_url = fake_inner.post.call_args[0][0]
    assert smoke.CONVERSATIONS_PATH in posted_url


@pytest.mark.no_pg_conv
def test_ci_requires_brain_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_API_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["post_deploy_smoke.py", "--ci"])
    assert smoke.main() == 1


@pytest.mark.no_pg_conv
def test_schedulers_http_error_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_API_URL", "https://brain.example.test")

    fake_inner = MagicMock()
    fake_inner.get.side_effect = [
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "ok"}},
        ),
        httpx.Response(
            200,
            json={"success": True, "data": {"status": "healthy"}},
        ),
        httpx.Response(503, json={"error": "upstream"}),
    ]

    with (
        patch.object(smoke.httpx, "Client", return_value=_client_cm(fake_inner)),
        patch.object(
            smoke,
            "sync_probe_agent_dispatches_table",
            return_value=(True, "ok"),
        ),
    ):
        code = smoke.run_smoke(ci_mode=True, report_conversation=False)

    assert code == 2
