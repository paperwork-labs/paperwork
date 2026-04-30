"""JSON ledger mapping Clerk ``sub`` to Brain tenancy rows (WS-76 PR-13).

Persistence: ``apis/brain/data/paperwork_links.json`` (v1).

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from app.schemas.paperwork_link import PaperworkLink

logger = logging.getLogger(__name__)


class PaperworkLinkNotFoundError(KeyError):
    """Raised when a required ledger row is missing for a Clerk user id."""


def _ledger_path() -> Path:
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data" / "paperwork_links.json"
    return Path(__file__).resolve().parents[2] / "data" / "paperwork_links.json"


def load_paperwork_links() -> list[PaperworkLink]:
    path = _ledger_path()
    if not path.exists():
        logger.warning("paperwork_links: ledger missing at %s", path)
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("paperwork_links: failed to read %s: %s", path, exc)
        return []
    if not isinstance(raw, list):
        logger.error("paperwork_links: expected JSON array at %s", path)
        return []
    out: list[PaperworkLink] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            out.append(PaperworkLink.model_validate(row))
        except Exception:
            logger.warning("paperwork_links: skipping invalid row: %s", row)
    return out


def resolve_by_clerk_user_id_optional(clerk_user_id: str) -> PaperworkLink | None:
    needle = clerk_user_id.strip()
    for link in load_paperwork_links():
        if link.clerk_user_id == needle:
            return link
    return None


def resolve_by_clerk_user_id(clerk_user_id: str) -> PaperworkLink:
    link = resolve_by_clerk_user_id_optional(clerk_user_id)
    if link is None:
        raise PaperworkLinkNotFoundError(clerk_user_id)
    return link
