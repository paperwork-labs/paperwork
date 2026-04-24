"""Tests for RegimeMonitor."""

from datetime import datetime
from unittest.mock import MagicMock

from backend.models.market_data import MarketRegime
from backend.services.market.regime_monitor import RegimeMonitor


def test_check_vix_absolute_critical_once_per_day() -> None:
    db = MagicMock()
    monitor = RegimeMonitor(db)
    first = monitor.check_vix(40.0)
    assert len(first) == 1
    assert first[0].alert_type == "vix_absolute"
    assert first[0].severity == "critical"
    second = monitor.check_vix(40.0)
    assert second == []


def test_check_vix_intraday_spike_with_open() -> None:
    db = MagicMock()
    monitor = RegimeMonitor(db)
    monitor.set_vix_open(10.0)
    # 10 -> 13 = 30% change -> critical spike
    alerts = monitor.check_vix(13.0)
    assert len(alerts) >= 1
    spike = next(a for a in alerts if a.alert_type == "vix_spike")
    assert spike.severity == "critical"
    assert spike.current_value >= 25.0


def test_check_regime_shift_critical_to_r5() -> None:
    db = MagicMock()
    current = MagicMock(spec=MarketRegime, regime_state="R5")
    previous = MagicMock(spec=MarketRegime, regime_state="R2")
    chain = MagicMock()
    db.query.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    chain.all.return_value = [current, previous]

    monitor = RegimeMonitor(db)
    alert = monitor.check_regime_shift()
    assert alert is not None
    assert alert.alert_type == "regime_shift"
    assert alert.severity == "critical"
