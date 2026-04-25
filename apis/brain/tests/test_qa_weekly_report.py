"""Track G — regression on the QA weekly digest formatter.

Deterministic readout of the registry. If any persona loses its ceiling,
rate limit, or output cap, the digest must shout about it.

medallion: ops
"""
from __future__ import annotations

from app.schedulers.qa_weekly_report import _build_digest


def test_weekly_digest_lists_persona_count():
    out = _build_digest()
    assert "Personas registered:" in out
    assert "Compliance-flagged:" in out


def test_weekly_digest_links_golden_suite():
    out = _build_digest()
    assert "brain-golden-suite.yaml" in out


def test_weekly_digest_current_state_is_clean():
    """Snapshot of the healthy state — if this trips, a persona regressed."""
    out = _build_digest()
    assert "All personas have ceilings" in out
