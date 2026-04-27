"""Unit tests for secrets intelligence (drift fingerprints, rotation due)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.secrets_intelligence import (
    SecretsIntelligence,
    compute_fingerprint,
    fingerprints_match,
)


def test_compute_fingerprint_stable() -> None:
    a = compute_fingerprint("hello-world")
    b = compute_fingerprint("hello-world")
    assert a.length == len("hello-world".encode("utf-8"))
    assert a.sha256_hex == b.sha256_hex
    assert a.prefix8 == "hello-wo"


def test_fingerprints_match() -> None:
    x = compute_fingerprint("abc")
    y = compute_fingerprint("abc")
    assert fingerprints_match(x, y)
    z = compute_fingerprint("abd")
    assert not fingerprints_match(x, z)


@pytest.mark.asyncio
async def test_rotations_due_threshold(db_session: AsyncSession) -> None:
    intel = SecretsIntelligence(db_session)
    now = datetime.now(UTC)
    last = now - timedelta(days=29)
    await intel.upsert_registry_entry(
        "ROT_TEST",
        service="test",
        rotation_cadence_days=30,
        last_rotated_at=last,
    )
    await db_session.commit()
    due = await intel.rotations_due(threshold_days=7)
    names = [d.name for d in due]
    assert "ROT_TEST" in names


@pytest.mark.asyncio
async def test_rotations_due_skips_zero_cadence(db_session: AsyncSession) -> None:
    intel = SecretsIntelligence(db_session)
    await intel.upsert_registry_entry(
        "NOCAD",
        service="test",
        rotation_cadence_days=0,
    )
    await db_session.commit()
    due = await intel.rotations_due()
    assert all(d.name != "NOCAD" for d in due)


@pytest.mark.asyncio
async def test_audit_drift_vault_in_sync_with_vercel(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    secret_value = "super-secret-value-xyz"
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    monkeypatch.setattr(settings, "STUDIO_URL", "https://studio.example.com")
    monkeypatch.setattr(settings, "SECRETS_API_KEY", "k")
    monkeypatch.setattr(settings, "VERCEL_API_TOKEN", "vt")
    monkeypatch.setattr(settings, "VERCEL_TEAM_ID", "team1")
    monkeypatch.setattr(
        settings,
        "BRAIN_SECRETS_VERCEL_APP_PROJECTS",
        '{"studio":"prj_studio"}',
    )

    intel = SecretsIntelligence(db_session)
    await intel.upsert_registry_entry(
        "MYS",
        service="test",
        depends_in_apps=["studio"],
        depends_in_services=[],
    )
    await db_session.commit()

    list_resp = MagicMock()
    list_resp.status_code = 200
    list_resp.json = MagicMock(
        return_value={"success": True, "data": [{"id": sid, "name": "MYS"}]}
    )
    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json = MagicMock(
        return_value={"success": True, "data": {"value": secret_value}}
    )
    vercel_resp = MagicMock()
    vercel_resp.status_code = 200
    vercel_resp.json = MagicMock(
        return_value=[{"key": "MYS", "value": secret_value, "id": "e1", "type": "encrypted"}]
    )

    mock_inner = MagicMock()
    mock_inner.get = AsyncMock(side_effect=[list_resp, get_resp, vercel_resp])
    ac = MagicMock()
    ac.return_value.__aenter__ = AsyncMock(return_value=mock_inner)
    ac.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.secrets_intelligence.httpx.AsyncClient", ac):
        rep = await intel.audit_drift("MYS")

    assert not rep.has_drift
    vercel_t = [t for t in rep.targets if t.kind == "vercel" and t.status not in ("skipped",)]
    assert vercel_t and vercel_t[0].status == "in_sync"


@pytest.mark.asyncio
async def test_audit_drift_detects_mismatch(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    sid = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
    monkeypatch.setattr(settings, "STUDIO_URL", "https://studio.example.com")
    monkeypatch.setattr(settings, "SECRETS_API_KEY", "k")
    monkeypatch.setattr(settings, "VERCEL_API_TOKEN", "vt")
    monkeypatch.setattr(
        settings,
        "BRAIN_SECRETS_VERCEL_APP_PROJECTS",
        '{"studio":"prj_studio"}',
    )

    intel = SecretsIntelligence(db_session)
    await intel.upsert_registry_entry(
        "MYS2",
        service="test",
        depends_in_apps=["studio"],
        depends_in_services=[],
    )
    await db_session.commit()

    list_resp = MagicMock()
    list_resp.status_code = 200
    list_resp.json = MagicMock(
        return_value={"success": True, "data": [{"id": sid, "name": "MYS2"}]}
    )
    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json = MagicMock(
        return_value={"success": True, "data": {"value": "aaaa"}}
    )
    vercel_resp = MagicMock()
    vercel_resp.status_code = 200
    vercel_resp.json = MagicMock(
        return_value=[{"key": "MYS2", "value": "bbbb", "id": "e1", "type": "encrypted"}]
    )

    mock_inner = MagicMock()
    mock_inner.get = AsyncMock(side_effect=[list_resp, get_resp, vercel_resp])
    ac = MagicMock()
    ac.return_value.__aenter__ = AsyncMock(return_value=mock_inner)
    ac.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.secrets_intelligence.httpx.AsyncClient", ac):
        rep = await intel.audit_drift("MYS2")

    assert rep.has_drift
    assert any(t.status == "drift" for t in rep.targets)
