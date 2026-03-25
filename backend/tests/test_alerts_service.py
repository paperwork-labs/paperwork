from backend.services.notifications.alerts import AlertService
from backend.config import settings


class _StubHTTP:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))

        class _Resp:
            def raise_for_status(self):
                return None

        return _Resp()


def test_alert_service_resolves_discord_aliases(monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_WEBHOOK_SYSTEM_STATUS", "https://discord/system")
    stub = _StubHTTP()
    svc = AlertService(http_client=stub)
    sent = svc.send_discord("system_status", "Test", "Payload", fields={"Foo": "Bar"})
    assert sent is True
    assert stub.calls[0][0] == "https://discord/system"


def test_alert_service_accepts_list_descriptors(monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_WEBHOOK_SYSTEM_STATUS", "https://discord/system")
    stub = _StubHTTP()
    svc = AlertService(http_client=stub)
    custom_url = "https://discord/custom"
    sent = svc.send_discord(["system_status", custom_url], "List Test", "Desc")
    assert sent is True
    targets = [call[0] for call in stub.calls]
    assert "https://discord/system" in targets
    assert custom_url in targets


def test_alert_service_pushes_prometheus(monkeypatch):
    stub = _StubHTTP()
    svc = AlertService(http_client=stub)
    ok = svc.push_prometheus_metric(
        "https://prom/push",
        "axiomfolio_task_duration_seconds",
        1.5,
        labels={"task": "monitor"},
    )
    assert ok is True
    url, kwargs = stub.calls[0]
    assert url == "https://prom/push"
    assert "axiomfolio_task_duration_seconds" in kwargs["data"]

