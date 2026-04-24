"""FMP 5m intraday backfill tier gate (no DB)."""

from typing import Optional

import pytest

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize(
    "policy,expect_blocked",
    [
        ("free", "free"),
        ("starter", "starter"),
        ("paid", None),
        ("unlimited", None),
    ],
)
def test_fmp_5m_intraday_backfill_blocked_tier(
    monkeypatch: pytest.MonkeyPatch, policy: str, expect_blocked: Optional[str]
) -> None:
    from backend.services.market import fmp_5m_tier_gate as gate

    monkeypatch.setattr(gate.settings, "MARKET_PROVIDER_POLICY", policy)
    assert gate.fmp_5m_intraday_backfill_blocked_tier() == expect_blocked


def test_unknown_policy_resolves_like_config_to_paid(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.market import fmp_5m_tier_gate as gate

    monkeypatch.setattr(gate.settings, "MARKET_PROVIDER_POLICY", "not-a-real-tier")
    assert gate.fmp_5m_intraday_backfill_blocked_tier() is None
