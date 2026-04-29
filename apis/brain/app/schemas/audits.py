"""Audit registry schemas — adaptive cadence, findings, POS pillar.

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime by Pydantic
from typing import Literal

from pydantic import BaseModel

Severity = Literal["info", "warn", "error"]
AuditCadence = Literal["weekly", "monthly", "quarterly"]


class AuditDef(BaseModel):
    id: str
    name: str
    cadence: AuditCadence
    runner_module: str
    pillar: str
    enabled: bool


class AuditFinding(BaseModel):
    audit_id: str
    severity: Severity
    title: str
    detail: str
    file_path: str | None = None
    line: int | None = None


class AuditRun(BaseModel):
    audit_id: str
    ran_at: datetime
    findings: list[AuditFinding]
    summary: str
    next_cadence: AuditCadence


class CadenceAdjustment(BaseModel):
    audit_id: str
    from_cadence: AuditCadence
    to_cadence: AuditCadence
    reason: str
    adjusted_at: datetime
    manual_override: bool
