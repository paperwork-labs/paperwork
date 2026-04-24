from app.tasks.utils.task_utils import _emit_alerts, _is_slow_run
from app.tasks.utils.schedule_metadata import HookConfig, ScheduleMetadata, SafetyConfig
from app.services.notifications.alerts import alert_service


class _StubJob:
    def __init__(self, job_id: int = 1):
        self.id = job_id


def test_emit_alerts_sends_discord_when_configured(monkeypatch):
    prom_calls = []
    discord_calls = []

    monkeypatch.setattr(
        alert_service,
        "push_prometheus_metric",
        lambda *args, **kwargs: prom_calls.append((args, kwargs)) or True,
    )
    monkeypatch.setattr(
        alert_service,
        "send_alert",
        lambda descriptor, **kwargs: discord_calls.append((descriptor, kwargs)) or True,
    )

    hooks = HookConfig(discord_channels=["system_status"], alert_on=["failure", "slow"])
    meta = ScheduleMetadata(hooks=hooks)

    _emit_alerts(
        event="failure",
        task_name="market_indices_constituents_refresh",
        job=_StubJob(),
        hooks=hooks,
        duration_s=42.0,
        meta=meta,
        counters={"rows": 10},
        error="boom",
    )

    assert prom_calls
    assert discord_calls
    descriptor, payload = discord_calls[0]
    assert "system_status" in descriptor
    assert payload["fields"]["Error"] == "boom"


def test_emit_alerts_skips_events_not_opted_in(monkeypatch):
    prom_calls = []
    discord_calls = []

    monkeypatch.setattr(
        alert_service,
        "push_prometheus_metric",
        lambda *args, **kwargs: prom_calls.append((args, kwargs)) or True,
    )
    monkeypatch.setattr(
        alert_service,
        "send_alert",
        lambda descriptor, **kwargs: discord_calls.append((descriptor, kwargs)) or True,
    )

    hooks = HookConfig(discord_channels=["system_status"], alert_on=["failure"])
    meta = ScheduleMetadata(hooks=hooks)

    _emit_alerts(
        event="success",
        task_name="market_indices_constituents_refresh",
        job=_StubJob(),
        hooks=hooks,
        duration_s=5.0,
        meta=meta,
    )

    assert prom_calls  # metrics still emitted
    assert discord_calls == []


def test_discord_mentions_appended(monkeypatch):
    discord_calls = []

    monkeypatch.setattr(alert_service, "push_prometheus_metric", lambda *_, **__: True)
    monkeypatch.setattr(
        alert_service,
        "send_alert",
        lambda descriptor, **kwargs: discord_calls.append((descriptor, kwargs)) or True,
    )

    hooks = HookConfig(
        discord_channels=["system_status"],
        discord_mentions=["<@123>", "@ops-team"],
        alert_on=["failure"],
    )
    meta = ScheduleMetadata(hooks=hooks)

    _emit_alerts(
        event="failure",
        task_name="market_universe_tracked_refresh",
        job=_StubJob(),
        hooks=hooks,
        duration_s=12.0,
        meta=meta,
        error="boom",
    )

    _, payload = discord_calls[0]
    assert "<@123>" in payload["description"]
    assert "@ops-team" in payload["description"]


def test_slow_threshold_prefers_hook_override():
    hooks = HookConfig(slow_threshold_s=50.0)
    meta = ScheduleMetadata(
        safety=SafetyConfig(timeout_s=3600),
        hooks=hooks,
    )

    assert _is_slow_run(60.0, meta, hooks) is True
    assert _is_slow_run(40.0, meta, hooks) is False

