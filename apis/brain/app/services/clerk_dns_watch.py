"""Run ``scripts/reconcile_clerk_dns.py --check-only`` from Brain (Track WS-37).

The script ships in the Docker image under ``/app/scripts/``. Local dev resolves
``REPO_ROOT`` / walks from this file to the monorepo root when unset.

medallion: ops
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from app.config import settings
from app.services import slack_outbound

logger = logging.getLogger(__name__)

_SLACK_CHANNEL_ID = "C0ALVM4PAE7"  # same engineering channel as infra_health
_JOB_LABEL = "clerk_dns_reconcile_check"


def _resolve_script_path() -> Path | None:
    env_root = (os.environ.get("REPO_ROOT") or "").strip()
    if env_root:
        p = Path(env_root) / "scripts" / "reconcile_clerk_dns.py"
        if p.is_file():
            return p
    docker = Path("/app/scripts/reconcile_clerk_dns.py")
    if docker.is_file():
        return docker
    here = Path(__file__).resolve()
    # .../paperwork/apis/brain/app/services/clerk_dns_watch.py → repo root
    try:
        candidate = here.parents[4] / "scripts" / "reconcile_clerk_dns.py"
    except IndexError:
        return None
    if candidate.is_file():
        return candidate
    return None


async def run_clerk_dns_check_only_tick() -> None:
    """Execute check-only reconcile; log + Slack on failure."""
    script = _resolve_script_path()
    if script is None:
        logger.warning(
            "%s: reconcile_clerk_dns.py not found (set REPO_ROOT or rebuild image)",
            _JOB_LABEL,
        )
        return

    ck = (os.environ.get("CLERK_SECRET_KEY") or "").strip()
    cf = (os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_TOKEN") or "").strip()
    if not ck or not cf:
        logger.info(
            "%s: CLERK_SECRET_KEY and CLOUDFLARE_API_TOKEN (or CF_TOKEN) required — skipping",
            _JOB_LABEL,
        )
        return

    proc = await asyncio.create_subprocess_exec(
        "python3",
        str(script),
        "--check-only",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(script.parent.parent),
        env=os.environ.copy(),
    )
    out_b, err_b = await proc.communicate()
    stdout = (out_b or b"").decode("utf-8", errors="replace")
    stderr = (err_b or b"").decode("utf-8", errors="replace")
    if proc.returncode == 0:
        logger.info("%s: OK\n%s", _JOB_LABEL, stdout[-2000:] if stdout else "")
        return

    logger.error(
        "%s failed exit=%s\nstdout=%s\nstderr=%s",
        _JOB_LABEL,
        proc.returncode,
        stdout[-4000:],
        stderr[-4000:],
    )
    eng = (settings.SLACK_ENGINEERING_CHANNEL_ID or "").strip() or _SLACK_CHANNEL_ID
    text = (
        f":rotating_light: *Clerk / Cloudflare DNS drift* (`reconcile_clerk_dns.py --check-only`)\n"
        f"*exit* `{proc.returncode}`\n"
        f"```{stderr[-3500:] or stdout[-3500:]}```"
    )
    result = await slack_outbound.post_message(
        channel_id=eng,
        text=text,
        username="Brain DNS watch",
        icon_emoji=":earth_africa:",
    )
    if not result.get("ok"):
        logger.warning("Slack notify failed: %s", result.get("error"))
