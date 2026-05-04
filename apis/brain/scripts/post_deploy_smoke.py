"""Post-deploy smoke checks for Brain API (T3.7).

Run from repo root or ``apis/brain``; ensures ``app`` is importable via sys.path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Final

import httpx

_BRAIN_ROOT = Path(__file__).resolve().parents[1]
if str(_BRAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_BRAIN_ROOT))

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_S: Final[float] = 10.0
AUTOPILOT_JOB_ID: Final[str] = "brain_autopilot_dispatcher"
CONVERSATIONS_PATH: Final[str] = "/api/v1/admin/conversations"


def _emit_check(record: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
    sys.stdout.flush()


def _join_url(base: str, path: str) -> str:
    base_clean = base.rstrip("/")
    path_clean = path if path.startswith("/") else f"/{path}"
    return f"{base_clean}{path_clean}"


def _resolve_commit_sha() -> str:
    for key in ("GITHUB_SHA", "VERCEL_GIT_COMMIT_SHA", "RENDER_GIT_COMMIT"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val[:7]
    return "unknown"


def _resolve_api_base_url(*, ci_mode: bool) -> str:
    raw = (os.environ.get("BRAIN_API_URL") or "").strip()
    if ci_mode:
        if not raw:
            raise RuntimeError(
                "BRAIN_API_URL must be set when using --ci (non-empty production base URL).",
            )
        return raw.rstrip("/")
    if raw:
        return raw.rstrip("/")
    return "http://localhost:8000"


def probe_health(client: httpx.Client, base_url: str) -> tuple[bool, str]:
    """Required: GET /health returns 200 with operational OK payload."""
    url = _join_url(base_url, "/health")
    try:
        resp = client.get(url)
    except httpx.RequestError as exc:
        logger.warning("post_deploy_smoke: GET /health transport error: %s", exc)
        return False, f"transport_error:{type(exc).__name__}"

    if resp.status_code != 200:
        logger.warning(
            "post_deploy_smoke: GET /health unexpected status=%s",
            resp.status_code,
        )
        return False, f"http_{resp.status_code}"

    try:
        payload = resp.json()
    except json.JSONDecodeError as exc:
        logger.warning("post_deploy_smoke: GET /health invalid JSON: %s", exc)
        return False, "invalid_json"

    data = payload.get("data") if isinstance(payload, dict) else None
    status_val = None
    if isinstance(data, dict):
        status_val = data.get("status")
    ok = isinstance(payload, dict) and payload.get("success") is True and status_val == "ok"
    if not ok:
        logger.warning("post_deploy_smoke: GET /health unexpected body shape")
        return False, "unexpected_body"
    return True, "ok"


def probe_health_deep(client: httpx.Client, base_url: str) -> tuple[bool, bool, str]:
    """Optional deep health. Returns (optional_failed, skipped, detail)."""
    url = _join_url(base_url, "/health/deep")
    try:
        resp = client.get(url)
    except httpx.RequestError as exc:
        logger.warning("post_deploy_smoke: GET /health/deep transport error: %s", exc)
        detail = f"transport_error:{type(exc).__name__}"
        _emit_check({"check": "health_deep", "detail": detail, "ok": False})
        return True, False, detail

    if resp.status_code == 404:
        _emit_check(
            {
                "check": "health_deep",
                "detail": "skipped — route absent",
                "ok": True,
                "skipped": True,
            }
        )
        return False, True, "skipped_route_absent"

    if resp.status_code != 200:
        logger.warning(
            "post_deploy_smoke: GET /health/deep unexpected status=%s",
            resp.status_code,
        )
        detail = f"http_{resp.status_code}"
        _emit_check({"check": "health_deep", "detail": detail, "ok": False})
        return True, False, detail

    try:
        resp.json()
    except json.JSONDecodeError as exc:
        logger.warning("post_deploy_smoke: GET /health/deep invalid JSON: %s", exc)
        _emit_check({"check": "health_deep", "detail": "invalid_json", "ok": False})
        return True, False, "invalid_json"

    _emit_check({"check": "health_deep", "detail": "ok", "ok": True})
    return False, False, "ok"


def probe_schedulers(client: httpx.Client, base_url: str) -> tuple[bool, str]:
    """Optional: GET /internal/schedulers; autopilot absence is warning only."""
    url = _join_url(base_url, "/internal/schedulers")
    try:
        resp = client.get(url)
    except httpx.RequestError as exc:
        logger.warning(
            "post_deploy_smoke: GET /internal/schedulers transport error: %s",
            exc,
        )
        detail = f"transport_error:{type(exc).__name__}"
        _emit_check({"check": "schedulers", "detail": detail, "ok": False})
        return True, detail

    if resp.status_code != 200:
        logger.warning(
            "post_deploy_smoke: GET /internal/schedulers unexpected status=%s",
            resp.status_code,
        )
        detail = f"http_{resp.status_code}"
        _emit_check({"check": "schedulers", "detail": detail, "ok": False})
        return True, detail

    try:
        payload = resp.json()
    except json.JSONDecodeError as exc:
        logger.warning(
            "post_deploy_smoke: GET /internal/schedulers invalid JSON: %s",
            exc,
        )
        _emit_check({"check": "schedulers", "detail": "invalid_json", "ok": False})
        return True, "invalid_json"

    if not isinstance(payload, list):
        logger.warning("post_deploy_smoke: schedulers payload is not a JSON list")
        _emit_check({"check": "schedulers", "detail": "not_a_list", "ok": False})
        return True, "not_a_list"

    job_ids = [row.get("id") for row in payload if isinstance(row, dict)]
    if AUTOPILOT_JOB_ID in job_ids:
        _emit_check({"check": "schedulers", "detail": "autopilot_present", "ok": True})
        return False, "ok"

    logger.warning(
        "post_deploy_smoke: job id %s absent — T1.2 not yet wired or scheduler idle",
        AUTOPILOT_JOB_ID,
    )
    _emit_check(
        {
            "check": "schedulers",
            "detail": f"absent — {AUTOPILOT_JOB_ID} not in job list (informational)",
            "ok": True,
            "warning": True,
        }
    )
    return False, "autopilot_absent_ok"


async def probe_agent_dispatches_table() -> tuple[bool, str]:
    """Required: DB reachable and agent_dispatches table readable."""
    from sqlalchemy import text

    from app.database import async_session_factory

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1 FROM agent_dispatches LIMIT 1"))
    except Exception as exc:
        logger.warning(
            "post_deploy_smoke: agent_dispatches probe failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        return False, f"{type(exc).__name__}"

    return True, "ok"


def sync_probe_agent_dispatches_table() -> tuple[bool, str]:
    return asyncio.run(probe_agent_dispatches_table())


def report_failure_conversation(
    *,
    client: httpx.Client,
    base_url: str,
    admin_token: str,
    commit_sha: str,
    body_lines: list[str],
) -> bool:
    """POST alert Conversation. Returns True if request succeeded."""
    token = admin_token.strip()
    if not token:
        logger.error(
            "post_deploy_smoke: BRAIN_ADMIN_TOKEN unset — cannot post Conversation alert",
        )
        return False

    url = _join_url(base_url, CONVERSATIONS_PATH)
    payload = {
        "title": f"Brain post-deploy smoke FAILED — {commit_sha}",
        "body_md": "\n".join(body_lines),
        "tags": ["alert", "deployment"],
        "urgency": "high",
        "persona": "engineering",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Brain-Secret": token,
    }
    try:
        resp = client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        logger.warning(
            "post_deploy_smoke: Conversation POST transport error: %s",
            exc,
        )
        return False

    if resp.status_code not in (200, 201):
        logger.warning(
            "post_deploy_smoke: Conversation POST failed status=%s body=%s",
            resp.status_code,
            (resp.text or "")[:500],
        )
        return False

    logger.info("post_deploy_smoke: Conversation alert posted successfully")
    return True


def run_smoke(*, ci_mode: bool, report_conversation: bool) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    summary_lines: list[str] = []
    required_failed = False
    optional_failed = False

    base_url = _resolve_api_base_url(ci_mode=ci_mode)

    commit_sha = _resolve_commit_sha()

    timeout = httpx.Timeout(REQUEST_TIMEOUT_S)
    with httpx.Client(timeout=timeout) as client:
        h_ok, h_detail = probe_health(client, base_url)
        _emit_check({"check": "health", "detail": h_detail, "ok": h_ok})
        summary_lines.append(f"/health: {'PASS' if h_ok else 'FAIL'} ({h_detail})")
        if not h_ok:
            required_failed = True

        deep_optional_fail, deep_skipped, deep_detail = probe_health_deep(client, base_url)
        if deep_skipped:
            summary_lines.append(f"/health/deep: SKIP ({deep_detail})")
        else:
            summary_lines.append(f"/health/deep: {'PASS' if not deep_optional_fail else 'FAIL'}")
            if deep_optional_fail:
                optional_failed = True

        sch_fail, sch_detail = probe_schedulers(client, base_url)
        summary_lines.append(
            f"/internal/schedulers: {'PASS' if not sch_fail else 'FAIL'} ({sch_detail})",
        )
        if sch_fail:
            optional_failed = True

        db_ok, db_detail = sync_probe_agent_dispatches_table()
        _emit_check({"check": "database_agent_dispatches", "detail": db_detail, "ok": db_ok})
        summary_lines.append(
            f"database agent_dispatches: {'PASS' if db_ok else 'FAIL'} ({db_detail})",
        )
        if not db_ok:
            required_failed = True

        exit_code = 0
        if required_failed:
            exit_code = 1
        elif optional_failed:
            exit_code = 2

        if report_conversation and exit_code != 0:
            admin_token = (os.environ.get("BRAIN_ADMIN_TOKEN") or "").strip()
            posted = report_failure_conversation(
                client=client,
                base_url=base_url,
                admin_token=admin_token,
                commit_sha=commit_sha,
                body_lines=summary_lines,
            )
            _emit_check(
                {
                    "check": "conversation_alert",
                    "detail": "posted" if posted else "failed_or_skipped",
                    "ok": posted,
                },
            )

        _emit_check(
            {
                "check": "_summary",
                "exit_code": exit_code,
                "required_failed": required_failed,
                "optional_failed": optional_failed,
            },
        )
        return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain API post-deploy smoke checks")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Require BRAIN_API_URL in the environment (no silent localhost default).",
    )
    parser.add_argument(
        "--report-conversation",
        action="store_true",
        help=(
            "On non-success exit, POST an alert Conversation via "
            "/api/v1/admin/conversations using BRAIN_ADMIN_TOKEN as X-Brain-Secret."
        ),
    )
    args = parser.parse_args()

    try:
        return run_smoke(ci_mode=args.ci, report_conversation=args.report_conversation)
    except RuntimeError as exc:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        logger.error("%s", exc)
        return 1
    except Exception as exc:
        logger.exception("post_deploy_smoke: fatal error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
