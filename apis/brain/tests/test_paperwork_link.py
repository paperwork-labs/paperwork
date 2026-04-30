"""Tests for paperwork link ledger + auth context (WS-76 PR-13).

medallion: ops
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.dependencies.auth import resolve_brain_user_context
from app.services.paperwork_links import (
    PaperworkLinkNotFoundError,
    resolve_by_clerk_user_id,
    resolve_by_clerk_user_id_optional,
)


def _b64url_json(data: dict[str, object]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _fake_jwt(*, sub: str) -> str:
    """Three-segment JWT-shaped string (payload unverified in tests)."""
    return f"{_b64url_json({'alg': 'none'})}.{_b64url_json({'sub': sub})}.sig"


def test_resolve_ledger_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    data = tmp_path / "apis" / "brain" / "data"
    data.mkdir(parents=True)
    row = {
        "id": "pl-test",
        "clerk_user_id": "user_abc",
        "organization_id": "org-xyz",
        "display_name": "Test",
        "role": "admin",
        "created_at": "2026-01-15T12:00:00Z",
    }
    (data / "paperwork_links.json").write_text(json.dumps([row]), encoding="utf-8")

    link = resolve_by_clerk_user_id_optional("user_abc")
    assert link is not None
    assert link.id == "pl-test"
    assert link.organization_id == "org-xyz"
    assert resolve_by_clerk_user_id_optional("missing") is None


def test_resolve_by_clerk_user_id_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    data = tmp_path / "apis" / "brain" / "data"
    data.mkdir(parents=True)
    (data / "paperwork_links.json").write_text("[]", encoding="utf-8")

    with pytest.raises(PaperworkLinkNotFoundError):
        resolve_by_clerk_user_id("nobody")


def test_env_fallback_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_TOOLS_USER_ID", "42")
    monkeypatch.setenv("BRAIN_TOOLS_ORGANIZATION_ID", "acme")
    cfg = Settings()
    ctx = resolve_brain_user_context(bearer_token=None, cfg=cfg)
    assert ctx.auth_source == "env_fallback"
    assert ctx.brain_user_id == "42"
    assert ctx.organization_id == "acme"


def test_jwt_missing_link_returns_403(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    data = tmp_path / "apis" / "brain" / "data"
    data.mkdir(parents=True)
    (data / "paperwork_links.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("BRAIN_ALLOW_UNVERIFIED_CLERK_JWT", "true")

    cfg = Settings(BRAIN_ALLOW_UNVERIFIED_CLERK_JWT=True)
    tok = _fake_jwt(sub="user_unknown")

    with pytest.raises(HTTPException) as excinfo:
        resolve_brain_user_context(bearer_token=tok, cfg=cfg)
    assert excinfo.value.status_code == 403


def test_jwt_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    data = tmp_path / "apis" / "brain" / "data"
    data.mkdir(parents=True)
    row = {
        "id": "pl-zz",
        "clerk_user_id": "user_ok",
        "organization_id": "tenant-a",
        "display_name": "OK User",
        "role": "member",
        "created_at": "2026-02-01T00:00:00Z",
    }
    (data / "paperwork_links.json").write_text(json.dumps([row]), encoding="utf-8")
    monkeypatch.setenv("BRAIN_ALLOW_UNVERIFIED_CLERK_JWT", "true")

    cfg = Settings(BRAIN_ALLOW_UNVERIFIED_CLERK_JWT=True)
    ctx = resolve_brain_user_context(bearer_token=_fake_jwt(sub="user_ok"), cfg=cfg)
    assert ctx.auth_source == "clerk_jwt"
    assert ctx.brain_user_id == "pl-zz"
    assert ctx.organization_id == "tenant-a"
    assert ctx.clerk_user_id == "user_ok"
