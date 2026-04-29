"""Runbook completeness audit runner — stub.

TODO: implement by scanning docs/runbooks/ for each on-call scenario and
checking for required sections (trigger, steps, owner, sla).

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.audits import AuditFinding, AuditRun

_AUDIT_ID = "runbook_completeness"


def run() -> AuditRun:
    now = datetime.now(tz=UTC)
    findings = [
        AuditFinding(
            audit_id=_AUDIT_ID,
            severity="info",
            title="Audit runner not yet implemented",
            detail=f"TODO: implement audit runner for {_AUDIT_ID}. "
            "Expected: scan docs/runbooks/ for completeness.",
            file_path=None,
            line=None,
        )
    ]
    return AuditRun(
        audit_id=_AUDIT_ID,
        ran_at=now,
        findings=findings,
        summary=f"{_AUDIT_ID}: stub runner — not yet implemented.",
        next_cadence="weekly",
    )
