"""Brain-owned data deep validator scheduler (Track K / P2.9)."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, data_deep_validator
from app.schedulers.data_deep_validator import (
    _check_dor_match,
    _top_rate_pct,
    install,
    run_data_deep_validator,
)
from app.schedulers.n8n_mirror import N8N_MIRROR_SPECS, install as install_n8n_mirror
from app.schedulers.n8n_mirror import n8n_mirror_env_var_name


def test_flag_off_no_job_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_OWNS_DATA_DEEP_VALIDATOR", raising=False)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    assert len(sched.get_jobs()) == 0


def test_flag_on_registers_one_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from zoneinfo import ZoneInfo

    la = ZoneInfo("America/Los_Angeles")
    monkeypatch.setenv("BRAIN_OWNS_DATA_DEEP_VALIDATOR", "true")
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_data_deep_validator"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    assert str(t.timezone) == "America/Los_Angeles"
    ref = CronTrigger.from_crontab("0 3 1 * *", timezone=la)
    assert t.fields == ref.fields


def test_flag_on_suppresses_matching_n8n_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAIN_OWNS_DATA_DEEP_VALIDATOR", "true")
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    sched = AsyncIOScheduler(timezone="UTC")
    install_n8n_mirror(sched)
    ids = {j.id for j in sched.get_jobs()}
    assert "n8n_shadow_data_deep_validator" not in ids
    assert "n8n_shadow_brain_daily" in ids


def test_top_rate_pct_flat() -> None:
    assert _top_rate_pct({"type": "flat", "flat_rate_bps": 525}) == "5.25"


def test_top_rate_pct_progressive() -> None:
    m = {
        "type": "progressive",
        "brackets": {
            "single": [
                {"rate_bps": 100, "from": 0},
                {"rate_bps": 875, "from": 10000},
            ],
            "joint": [{"rate_bps": 50}],
        },
    }
    assert _top_rate_pct(m) == "8.75"


def test_top_rate_pct_none() -> None:
    assert _top_rate_pct({"type": "none"}) is None


def test_check_dor_match_finds_variants() -> None:
    assert _check_dor_match("The top rate is 5.25% for residents.", "5.25")
    assert _check_dor_match("x 5.25 y", "5.25")
    # JS: "5.20".replace(/0$/, '') => "5.2"
    assert _check_dor_match("rate 5.2 applies to you", "5.20")
    assert not _check_dor_match("x" * 600, "5.25")


@pytest.mark.asyncio
async def test_run_skips_when_slack_token_missing(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context() -> Any:
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "", raising=False)

    await run_data_deep_validator()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_data_deep_validator")
        )
    ).scalar_one()
    assert r.status == "skipped"
    assert r.error_text is None


def _build_source_list(n: int) -> list[dict[str, Any]]:
    return [
        {
            "name": f"s{i}.json",
            "type": "file",
            "download_url": f"https://raw.example.com/s{i}.json",
        }
        for i in range(n)
    ]


def _source_body(i: int, *, with_dor: bool) -> dict[str, Any]:
    base: dict[str, Any] = {
        "state": f"s{i}",
        "state_name": f"State {i}",
    }
    if with_dor:
        base["dor"] = {"url": f"https://dor.example.com/page{i}"}
    return base


class _FakeAsyncClient:
    def __init__(self, handler: Any, *_a: Any, **_k: Any) -> None:
        self._handler = handler

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *a: Any) -> None:
        pass

    async def get(self, url: str, headers: dict[str, str] | None = None, timeout: Any = None) -> Any:
        return await self._handler(url)


class _R:
    __slots__ = ("status_code", "_text", "_j")

    def __init__(self, status_code: int, text: str | None = None, json_data: Any = None) -> None:
        self.status_code = status_code
        if json_data is not None:
            self._text = json.dumps(json_data)
            self._j = json_data
        else:
            self._text = text or ""
            self._j = None

    @property
    def text(self) -> str:
        return self._text

    def json(self) -> Any:
        if self._j is not None:
            return self._j
        return json.loads(self._text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            raise httpx.HTTPStatusError("err", request=request, response=self)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_run_success_no_issues_posts_clean_report(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context() -> Any:
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "gh-test", raising=False)

    tax_none = json.dumps({"income_tax": {"type": "none"}})

    async def _handle(url: str) -> _R:
        u = str(url)
        if "/contents/packages/data/src/sources" in u and "api.github.com" in u:
            return _R(200, json_data=_build_source_list(10))
        if "raw.example.com" in u:
            for i in range(10):
                if f"s{i}.json" in u:
                    return _R(200, text=json.dumps(_source_body(i, with_dor=False)))
        if "/contents/packages/data/src/tax/2026/" in u:
            for i in range(10):
                if f"/s{i}.json" in u:
                    return _R(200, text=tax_none)
        return _R(404, text="nope")

    monkeypatch.setattr(
        data_deep_validator.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncClient(_handle, **kw),
    )
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(data_deep_validator.slack_outbound, "post_message", post)

    await run_data_deep_validator()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_data_deep_validator")
        )
    ).scalar_one()
    assert r.status == "success"
    post.assert_awaited_once()
    text = post.await_args.kwargs.get("text", "")
    assert ":white_check_mark: 10/10" in text
    assert ":warning:" not in text


@pytest.mark.asyncio
async def test_run_with_issues_posts_warning(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context() -> Any:
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "gh-test", raising=False)

    tax_flat = json.dumps({"income_tax": {"type": "flat", "flat_rate_bps": 525}})
    long_no_rate = "x" * 600
    tax_none = json.dumps({"income_tax": {"type": "none"}})

    async def _handle(url: str) -> _R:
        u = str(url)
        if "/contents/packages/data/src/sources" in u and "api.github.com" in u:
            return _R(200, json_data=_build_source_list(10))
        if "raw.example.com" in u:
            for i in range(10):
                if f"s{i}.json" in u:
                    with_dor = i < 3
                    return _R(200, text=json.dumps(_source_body(i, with_dor=with_dor)))
        if "dor.example.com" in u:
            return _R(200, text=f"<html><body>{long_no_rate}</body></html>")
        if "/contents/packages/data/src/tax/2026/" in u:
            for i in range(10):
                if f"/s{i}.json" in u:
                    body = tax_flat if i < 3 else tax_none
                    return _R(200, text=body)
        return _R(404, text="nope")

    monkeypatch.setattr(
        data_deep_validator.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncClient(_handle, **kw),
    )
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(data_deep_validator.slack_outbound, "post_message", post)

    await run_data_deep_validator()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_data_deep_validator")
        )
    ).scalar_one()
    assert r.status == "success"
    text = post.await_args.kwargs.get("text", "")
    assert text and ":warning:" in text
    assert "Investigate flagged states" in text
    assert "7/10" in text
