"""Tests for ConnectJobStore (Redis-backed connect job status)."""

import json
from unittest.mock import MagicMock


def test_connect_job_store_set_get():
    """ConnectJobStore set/get round-trips correctly."""
    store = {}

    def setex(key, ttl, value):
        store[key] = value

    def get(key):
        return store.get(key)

    mock_client = MagicMock()
    mock_client.setex = setex
    mock_client.get = get

    from app.services.security.connect_job_store import ConnectJobStore

    store_instance = ConnectJobStore(ttl_seconds=600)
    store_instance._redis = mock_client

    job_id = "abc123"
    data = {"state": "success", "finished_at": 123.45, "broker": "tastytrade"}
    store_instance.set(job_id, data)

    # set() does json.dumps, so store has the JSON string
    stored = store.get("connect_job:abc123")
    assert stored is not None
    parsed = json.loads(stored)
    assert parsed["state"] == "success"

    result = store_instance.get(job_id)
    assert result is not None
    assert result["state"] == "success"
    assert result["broker"] == "tastytrade"


def test_connect_job_store_get_missing_returns_none():
    """ConnectJobStore get returns None for unknown job_id."""
    mock_client = MagicMock()
    mock_client.get.return_value = None

    from app.services.security.connect_job_store import ConnectJobStore

    store_instance = ConnectJobStore(ttl_seconds=600)
    store_instance._redis = mock_client

    result = store_instance.get("nonexistent")
    assert result is None
