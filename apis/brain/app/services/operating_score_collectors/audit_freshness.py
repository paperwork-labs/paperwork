"""Audit freshness POS pillar — % of enabled audits run within 1.5x cadence period.

medallion: ops
"""

from __future__ import annotations

from app.services.audits import audit_freshness as _compute


def collect() -> tuple[float, bool, str]:
    return _compute()
