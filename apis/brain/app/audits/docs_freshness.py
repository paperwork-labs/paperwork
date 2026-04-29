"""docs_freshness audit runner — stub.

TODO: implement audit runner for docs_freshness.

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.audits import AuditFinding, AuditRun

_AUDIT_ID = "docs_freshness"


def run() -> AuditRun:
    now = datetime.now(tz=UTC)
    findings = [
        AuditFinding(
            audit_id=_AUDIT_ID,
            severity="info",
            title="Audit runner not yet implemented",
            detail=f"TODO: implement audit runner for {_AUDIT_ID}.",
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
