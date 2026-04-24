from app.tasks.utils.schedule_metadata import (
    HookConfig,
    ScheduleMetadata,
    ScheduleMetadataPatch,
    delete_schedule_metadata,
    load_schedule_metadata,
    metadata_to_options,
    save_schedule_metadata,
)


class _DummyRedis:
    def __init__(self) -> None:
        self.store = {}

    def set(self, name: str, value: str) -> None:
        self.store[name] = value

    def get(self, name: str):
        return self.store.get(name)

    def delete(self, name: str) -> None:
        self.store.pop(name, None)


def test_metadata_roundtrip():
    client = _DummyRedis()
    meta = ScheduleMetadata(queue="market_data_high", priority=7)
    save_schedule_metadata("foo", meta, client=client)
    loaded = load_schedule_metadata("foo", client=client)
    assert loaded is not None
    assert loaded.queue == "market_data_high"
    assert loaded.priority == 7
    delete_schedule_metadata("foo", client=client)
    assert load_schedule_metadata("foo", client=client) is None


def test_metadata_to_options_sets_queue_and_headers():
    meta = ScheduleMetadata(queue="critical", priority=2)
    options = metadata_to_options(meta)
    assert options["queue"] == "critical"
    assert options["priority"] == 2
    assert options["headers"]["schedule_metadata"]["queue"] == "critical"


def test_metadata_patch_can_clear_queue():
    base = ScheduleMetadata(queue="legacy-queue", priority=1)
    patch = ScheduleMetadataPatch(queue=None, priority=None)
    updated = patch.apply(base)
    assert updated.queue is None
    assert updated.priority is None


def test_metadata_patch_updates_hooks():
    base = ScheduleMetadata(hooks=HookConfig(discord_webhook="system_status", alert_on=["failure"]))
    patch = ScheduleMetadataPatch(
        hooks=HookConfig(
            discord_webhook="signals",
            discord_channels=["system_status", "playground"],
            prometheus_endpoint="https://push.example.com/job/test",
            alert_on=["failure", "slow"],
        )
    )
    updated = patch.apply(base)
    assert updated.hooks.discord_webhook == "signals"
    assert updated.hooks.discord_channels == ["system_status", "playground"]
    assert "slow" in updated.hooks.alert_on
