"""Tests for Brain pause flag, kill_switch service, and scheduler guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import kill_switch


def test_is_brain_paused_false_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "missing.flag"
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))
    assert kill_switch.is_brain_paused() is False


def test_is_brain_paused_false_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "empty.flag"
    flag.write_text("", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))
    assert kill_switch.is_brain_paused() is False


def test_is_brain_paused_false_whitespace_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = tmp_path / "ws.flag"
    flag.write_text("   \n\t  \n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))
    assert kill_switch.is_brain_paused() is False


def test_is_brain_paused_true_nonempty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "on.flag"
    flag.write_text("2026-04-28T00:00:00Z ops\n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))
    assert kill_switch.is_brain_paused() is True


def test_reason_none_when_not_paused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "off.flag"
    flag.write_text("", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))
    assert kill_switch.reason() is None


def test_reason_first_line_when_paused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "on.flag"
    flag.write_text("line one\nline two\n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))
    assert kill_switch.reason() == "line one"


@pytest.mark.asyncio
async def test_skip_decorator_skips_when_paused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    flag = tmp_path / "paused.flag"
    flag.write_text("2026-04-28T12:00:00Z drain traffic\n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))

    ran: list[str] = []

    @skip_if_brain_paused("test_job")
    async def body() -> str:
        ran.append("x")
        return "done"

    caplog.set_level(logging.INFO)
    out = await body()
    assert out is None
    assert ran == []
    assert any("job test_job skipped (brain paused:" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_skip_decorator_runs_when_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = tmp_path / "active.flag"
    flag.write_text("", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))

    @skip_if_brain_paused("test_job")
    async def body() -> str:
        return "ok"

    assert await body() == "ok"
