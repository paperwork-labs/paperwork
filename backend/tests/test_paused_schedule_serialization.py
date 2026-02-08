from backend.api.routes import admin_scheduler


def test_paused_payload_requires_name():
    assert admin_scheduler._paused_payload_to_schedule({}) is None


def test_paused_payload_to_schedule_round_trip():
    payload = {
        "name": "admin_coverage_refresh",
        "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
        "schedule": "<crontab: 0 * * * * (m/h/dM/MY/d)>",
        "cron": "0 * * * *",
        "timezone": "UTC",
        "args": [],
        "kwargs": {"foo": "bar"},
        "metadata": {"queue": "market-data", "safety": {"singleflight": True}},
    }

    result = admin_scheduler._paused_payload_to_schedule(payload)
    assert result is not None
    assert result["name"] == payload["name"]
    assert result["cron"] == payload["cron"]
    assert result["timezone"] == payload["timezone"]
    assert result["metadata"]["queue"] == "market-data"
    assert result["status"] == "paused"

