"""Run ``scripts/reconcile_clerk_dns.py --check-only`` from Brain (Track WS-37).

The script ships in the Docker image under ``/app/scripts/``. Local dev resolves
``REPO_ROOT`` / walks from this file to the monorepo root when unset.

medallion: ops
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation
from app.utils.paths import brain_scripts_dir

logger = logging.getLogger(__name__)

_JOB_LABEL = "clerk_dns_reconcile_check"


def _resolve_script_path() -> Path | None:
    candidate = brain_scripts_dir() / "reconcile_clerk_dns.py"
    return candidate if candidate.is_file() else None


async def run_clerk_dns_check_only_tick() -> None:
    """Execute check-only reconcile; log + create Brain Conversation on failure."""
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
    detail = (stderr[-3000:] or stdout[-3000:]).strip()
    body_md = (
        f"**Clerk / Cloudflare DNS drift detected** (`reconcile_clerk_dns.py --check-only`)\n\n"
        f"Exit code: `{proc.returncode}`\n\n"
        f"```\n{detail}\n```"
    )
    create_conversation(
        ConversationCreate(
            title="Clerk/Cloudflare DNS Drift Detected",
            body_md=body_md,
            tags=["alert"],
            urgency="high",
            persona="ea",
            needs_founder_action=True,
        )
    )
