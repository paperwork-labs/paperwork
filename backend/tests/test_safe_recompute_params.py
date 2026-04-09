"""Verify safe_recompute passes the correct kwargs to its sub-tasks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_safe_recompute_passes_force_true_and_config_days():
    """safe_recompute must call recompute_universe(force=True) and use
    RECOMPUTE_HISTORY_MAX_DAYS from config for snapshot_last_n_days."""
    from backend.config import settings

    captured_recompute = {}
    captured_history = {}

    def fake_recompute(**kwargs):
        captured_recompute.update(kwargs)
        return {"status": "ok", "processed_ok": 0, "skipped_fresh": 0}

    def fake_snapshot_last_n(**kwargs):
        captured_history.update(kwargs)
        return {"status": "ok"}

    def fake_health():
        return {"status": "ok"}

    with (
        patch("backend.tasks.market.backfill._set_task_status"),
        patch("backend.tasks.market.indicators.recompute_universe", side_effect=fake_recompute) as mock_rc,
        patch("backend.tasks.market.history.snapshot_last_n_days", side_effect=fake_snapshot_last_n) as mock_sn,
        patch("backend.tasks.market.coverage.health_check", side_effect=fake_health),
    ):
        from backend.tasks.market.backfill import safe_recompute

        result = safe_recompute.__wrapped__(since_date="1993-01-29", batch_size=10, history_batch_size=5)

    assert mock_rc.called
    call_kwargs = mock_rc.call_args
    assert call_kwargs[1].get("force") is True or (len(call_kwargs[0]) >= 2 and call_kwargs[0][1] is True), \
        "recompute_universe must be called with force=True"

    assert mock_sn.called
    sn_kwargs = mock_sn.call_args[1] if mock_sn.call_args[1] else {}
    sn_args = mock_sn.call_args[0] if mock_sn.call_args[0] else ()
    days_arg = sn_kwargs.get("days") or (sn_args[0] if sn_args else None)
    assert days_arg == settings.RECOMPUTE_HISTORY_MAX_DAYS, \
        f"Expected days={settings.RECOMPUTE_HISTORY_MAX_DAYS}, got {days_arg}"

    assert result["status"] == "ok"
