from backend.services.notifications.alerts import AlertService


class _StubHTTP:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))

        class _Resp:
            def raise_for_status(self):
                return None

        return _Resp()


class _StubBrain:
    def __init__(self):
        self.calls = []
        self.webhook_url = "https://brain.example/hook"

    def notify_sync(self, event, data, user_id=None):
        self.calls.append((event, data, user_id))
        return True


def test_alert_service_send_alert():
    stub_http = _StubHTTP()
    stub_brain = _StubBrain()
    svc = AlertService(http_client=stub_http, brain=stub_brain)
    sent = svc.send_alert("system_status", "Test", "Payload", fields={"Foo": "Bar"})
    assert sent is True
    assert stub_brain.calls[0][0] == "ops_alert"
    assert stub_brain.calls[0][1]["title"] == "Test"
    assert stub_brain.calls[0][1]["fields"]["Foo"] == "Bar"
    assert "system_status" in stub_brain.calls[0][1]["channels"]


def test_alert_service_send_alert_list_descriptor():
    stub_http = _StubHTTP()
    stub_brain = _StubBrain()
    svc = AlertService(http_client=stub_http, brain=stub_brain)
    sent = svc.send_alert(["system_status", "playground"], "List Test", "Desc")
    assert sent is True
    ch = stub_brain.calls[0][1]["channels"]
    assert "system_status" in ch
    assert "playground" in ch


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
