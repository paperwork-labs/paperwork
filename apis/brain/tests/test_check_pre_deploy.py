"""Subprocess tests for scripts/check_pre_deploy.py (quota + Vercel env guard)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "check_pre_deploy.py"


class _CombinedHandler(BaseHTTPRequestHandler):
    brain_payload: ClassVar[dict[str, object]] = {}
    vercel_payload: ClassVar[dict[str, object]] = {}

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/v1/admin/vercel-quota":
            body = json.dumps(
                {"success": True, "data": type(self).brain_payload},
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.endswith("/env"):
            body = json.dumps(type(self).vercel_payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)


@pytest.fixture
def mock_server() -> int:
    server = HTTPServer(("127.0.0.1", 0), _CombinedHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _run_script(
    *extra: str,
    env: dict[str, str] | None = None,
    port: int | None = None,
) -> subprocess.CompletedProcess[str]:
    base_env = {
        "BRAIN_ADMIN_TOKEN": "test-brain",
        "VERCEL_API_TOKEN": "test-vercel",
        "VERCEL_PROJECT_ID_AXIOMFOLIO": "prj_test_axiom",
    }
    if env:
        base_env.update(env)
    if port is not None:
        base_env["BRAIN_BASE_URL"] = f"http://127.0.0.1:{port}"
        base_env["VERCEL_API_BASE_URL"] = f"http://127.0.0.1:{port}"
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(SCRIPT),
            "--project",
            "axiomfolio",
            "--target",
            "production",
            *extra,
        ],
        cwd=str(REPO_ROOT),
        env={**os.environ, **base_env},
        capture_output=True,
        text=True,
        check=False,
    )


def test_quota_below_threshold_exits_2(mock_server: int) -> None:
    _CombinedHandler.brain_payload = {
        "snapshots": [
            {
                "window_days": 1,
                "project_name": "axiomfolio",
                "project_id": "prj_x",
                "meta": {"calendar_day_deploy_count_utc": 97, "utc_date": "2026-04-28"},
            },
        ],
    }
    _CombinedHandler.vercel_payload = {"envs": []}
    proc = _run_script(port=mock_server)
    assert proc.returncode == 2
    assert "QUOTA EXHAUSTED" in proc.stderr


def test_missing_env_var_exits_3(mock_server: int) -> None:
    _CombinedHandler.brain_payload = {
        "snapshots": [
            {
                "window_days": 1,
                "project_name": "axiomfolio",
                "project_id": "prj_x",
                "meta": {"calendar_day_deploy_count_utc": 10, "utc_date": "2026-04-28"},
            },
        ],
    }
    _CombinedHandler.vercel_payload = {
        "envs": [
            {"key": "NEXT_PUBLIC_API_URL", "target": ["production"]},
            # NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY intentionally missing
        ],
    }
    proc = _run_script(port=mock_server)
    assert proc.returncode == 3
    assert "MISSING_ENV_VARS" in proc.stderr
    assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" in proc.stderr


def test_all_green_exits_0(mock_server: int) -> None:
    _CombinedHandler.brain_payload = {
        "snapshots": [
            {
                "window_days": 1,
                "project_name": "axiomfolio",
                "project_id": "prj_x",
                "meta": {"calendar_day_deploy_count_utc": 10, "utc_date": "2026-04-28"},
            },
        ],
    }
    _CombinedHandler.vercel_payload = {
        "envs": [
            {"key": "NEXT_PUBLIC_API_URL", "target": ["production"]},
            {"key": "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "target": ["production"]},
        ],
    }
    proc = _run_script(port=mock_server)
    assert proc.returncode == 0
    assert "OK —" in proc.stdout
    assert "axiomfolio:production" in proc.stdout


def test_require_all_checks_with_skip_exits_5() -> None:
    proc = _run_script("--skip-quota", "--skip-env-vars", "--require-all-checks")
    assert proc.returncode == 5
    assert "PRE_DEPLOY_GUARD_BYPASS_USED" in proc.stderr
