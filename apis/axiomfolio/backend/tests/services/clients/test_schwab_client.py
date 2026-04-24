"""Unit tests for SchwabClient (transaction window, clamps)."""

from __future__ import annotations

from datetime import datetime

import pytest

from backend.services.clients.schwab_client import SchwabClient


def _parse_z(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_get_transactions_clamps_to_540_days() -> None:
    c = SchwabClient()
    c.connected = True
    c._access_token = "t"

    captured: dict = {}

    async def _hash(_: str) -> str:
        return "h"

    async def _req(_m: str, _p: str, params: dict | None = None) -> dict:
        captured["params"] = params
        return {"transactions": []}

    c._resolve_account_hash = _hash
    c._request = _req  # type: ignore[method-assign]

    await c.get_transactions("12345", days=2000)
    p = captured.get("params") or {}
    start = _parse_z(p["startDate"])
    end = _parse_z(p["endDate"])
    delta_days = (end - start).total_seconds() / 86400.0
    assert 539.0 <= delta_days <= 541.0


@pytest.mark.asyncio
async def test_get_transactions_treats_non_positive_days_as_365() -> None:
    c = SchwabClient()
    c.connected = True
    c._access_token = "t"

    captured: dict = {}

    async def _hash(_: str) -> str:
        return "h"

    async def _req(_m: str, _p: str, params: dict | None = None) -> dict:
        captured["params"] = params
        return {"transactions": []}

    c._resolve_account_hash = _hash
    c._request = _req  # type: ignore[method-assign]

    await c.get_transactions("12345", days=0)
    p = captured.get("params") or {}
    start = _parse_z(p["startDate"])
    end = _parse_z(p["endDate"])
    delta_days = (end - start).total_seconds() / 86400.0
    assert 364.0 <= delta_days <= 366.0
