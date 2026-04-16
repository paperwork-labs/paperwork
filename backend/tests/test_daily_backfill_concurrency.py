"""Tests for daily backfill concurrency vs DB pool safety."""

from backend.config import settings
from backend.tasks.utils.task_utils import _daily_backfill_concurrency


def test_daily_backfill_concurrency_capped_for_pool_safety(monkeypatch):
    """Paid tier wants 50 concurrent L2 sessions; cap at pool_safe (20)."""
    monkeypatch.setattr(settings, "MARKET_PROVIDER_POLICY", "paid", raising=False)
    assert _daily_backfill_concurrency() == 20


def test_daily_backfill_concurrency_respects_lower_tier(monkeypatch):
    """Free tier stays at 5."""
    monkeypatch.setattr(settings, "MARKET_PROVIDER_POLICY", "free", raising=False)
    assert _daily_backfill_concurrency() == 5
