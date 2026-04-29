"""Stack audit runner — wraps stack_modernity POS collector logic.

Parses docs/STACK_AUDIT_2026-Q2.md for KEEP/UPGRADE/REPLACE counts and
surfaces stale or replace-heavy results as findings.

medallion: ops
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.audits import AuditFinding, AuditRun

_KEEP_RE = re.compile(r"(?mi)^\s*[-*]?\s*KEEP:\s*(\d+)")
_UPGRADE_RE = re.compile(r"(?mi)^\s*[-*]?\s*UPGRADE:\s*(\d+)")
_REPLACE_RE = re.compile(r"(?mi)^\s*[-*]?\s*REPLACE:\s*(\d+)")
_AUDIT_DATE_RE = re.compile(r"\*\*Audit date:\*\*\s*(\d{4}-\d{2}-\d{2})")


def _find_audit_doc() -> Path | None:
    env = os.environ.get("BRAIN_STACK_AUDIT_MD", "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "apps").is_dir() and (anc / "docs").is_dir():
            return anc / "docs" / "STACK_AUDIT_2026-Q2.md"
    return None


def run() -> AuditRun:
    audit_id = "stack"
    now = datetime.now(tz=UTC)
    findings: list[AuditFinding] = []

    doc = _find_audit_doc()
    if doc is None or not doc.is_file():
        findings.append(
            AuditFinding(
                audit_id=audit_id,
                severity="warn",
                title="Stack audit document not found",
                detail="docs/STACK_AUDIT_2026-Q2.md is missing — run WS-49 to generate it.",
                file_path=None,
                line=None,
            )
        )
        return AuditRun(
            audit_id=audit_id,
            ran_at=now,
            findings=findings,
            summary="Stack audit doc missing.",
            next_cadence="weekly",
        )

    body = doc.read_text(encoding="utf-8")
    mk = _KEEP_RE.search(body)
    mu = _UPGRADE_RE.search(body)
    mr = _REPLACE_RE.search(body)

    if not all([mk, mu, mr]):
        findings.append(
            AuditFinding(
                audit_id=audit_id,
                severity="warn",
                title="Stack audit doc missing KEEP/UPGRADE/REPLACE counts",
                detail=f"Could not parse counts from {doc.name}.",
                file_path=str(doc),
                line=None,
            )
        )
        return AuditRun(
            audit_id=audit_id,
            ran_at=now,
            findings=findings,
            summary="Stack audit doc parse failure.",
            next_cadence="weekly",
        )

    keep = int(mk.group(1))  # type: ignore[union-attr]
    upgrade = int(mu.group(1))  # type: ignore[union-attr]
    replace = int(mr.group(1))  # type: ignore[union-attr]
    total = keep + upgrade + replace

    mtime_dt = datetime.fromtimestamp(doc.stat().st_mtime, tz=UTC)
    stale_days = int((now - mtime_dt).total_seconds() // 86400)

    if stale_days > 90:
        findings.append(
            AuditFinding(
                audit_id=audit_id,
                severity="warn",
                title=f"Stack audit doc stale ({stale_days} days)",
                detail="Audit doc not updated in over 90 days — trigger refresh.",
                file_path=str(doc),
                line=None,
            )
        )

    if total > 0 and replace / total > 0.15:
        findings.append(
            AuditFinding(
                audit_id=audit_id,
                severity="warn",
                title=f"High REPLACE ratio ({replace}/{total})",
                detail=(
                    f"{replace} items flagged REPLACE out of {total} total."
                    " Investigate migration plan."
                ),
                file_path=str(doc),
                line=None,
            )
        )

    if not findings:
        findings.append(
            AuditFinding(
                audit_id=audit_id,
                severity="info",
                title="Stack audit clean",
                detail=f"{keep} KEEP / {upgrade} UPGRADE / {replace} REPLACE — no issues.",
                file_path=str(doc),
                line=None,
            )
        )

    severity_counts = {"error": 0, "warn": 0, "info": 0}
    for f in findings:
        severity_counts[f.severity] += 1

    next_cadence: str
    if severity_counts["error"] > 0 or severity_counts["warn"] > 0:
        next_cadence = "weekly"
    else:
        next_cadence = "weekly"

    summary = (
        f"Stack audit: {keep} KEEP / {upgrade} UPGRADE / {replace} REPLACE; "
        f"{severity_counts['warn']} warn, {severity_counts['error']} error."
    )
    return AuditRun(
        audit_id=audit_id,
        ran_at=now,
        findings=findings,
        summary=summary,
        next_cadence=next_cadence,  # type: ignore[arg-type]
    )
