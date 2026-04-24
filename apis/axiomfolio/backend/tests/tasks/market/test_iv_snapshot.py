"""Counter + assertion tests for ``backend.tasks.market.iv.sync_gateway``.

The IV snapshot task is the only way ``HistoricalIV`` grows, so its
counter loop is the integrity gate for every downstream signal (rank,
scan filter, admin health). These tests pin:

1. ``written + skipped_no_data + errors == total`` -- the final assert
   must fire on counter drift.
2. Yahoo fallback is tried when IBKR returns ``None``.
3. ``errors`` counter increments cleanly when a fetcher raises.
"""

from __future__ import annotations

import inspect
from datetime import date
from typing import Any, List, Optional

import pytest

from backend.services.market.historical_iv_service import IVSample
from backend.tasks.market import iv as iv_tasks

pytestmark = pytest.mark.no_db


class _StubSession:
    """No-op session sufficient for sync_gateway's DB surface under tests
    where all DB-touching helpers (compute_hv, persist_iv_sample) are
    monkeypatched.
    """

    closed = False
    commits = 0
    rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def _unwrap(fn: Any) -> Any:
    """Strip celery + task_run decorators so we can call the bare
    function in tests."""
    return inspect.unwrap(fn)


@pytest.fixture
def stub_session(monkeypatch: pytest.MonkeyPatch) -> _StubSession:
    sess = _StubSession()
    monkeypatch.setattr(iv_tasks, "SessionLocal", lambda: sess)
    # Replace the compute_hv / persist_iv_sample touchpoints that run
    # inside the per-symbol loop. These are imported locally inside
    # ``sync_gateway`` via the service module, so patch at the source.
    import backend.services.market.historical_iv_service as svc

    monkeypatch.setattr(svc, "compute_hv", lambda *a, **kw: None)
    monkeypatch.setattr(
        svc,
        "persist_iv_sample",
        lambda sample, hv_20, hv_60, db: None,  # succeed silently
    )
    return sess


def _ibkr_returns(sample: Optional[IVSample]):
    def fn(symbol: str, as_of: date, *, db: Any = None) -> Optional[IVSample]:
        return sample

    return fn


def _yahoo_returns(sample: Optional[IVSample]):
    def fn(symbol: str, as_of: date, *, db: Any = None) -> Optional[IVSample]:
        return sample

    return fn


def _per_symbol_ibkr(mapping: dict[str, Optional[IVSample]]):
    def fn(symbol: str, as_of: date, *, db: Any = None) -> Optional[IVSample]:
        return mapping.get(symbol)

    return fn


def _per_symbol_yahoo(mapping: dict[str, Optional[IVSample]]):
    def fn(symbol: str, as_of: date, *, db: Any = None) -> Optional[IVSample]:
        return mapping.get(symbol)

    return fn


def test_counters_sum_to_total_all_written(stub_session: _StubSession) -> None:
    as_of = date(2026, 4, 22)
    symbols = ["AAPL", "MSFT", "NVDA"]
    sample = IVSample(symbol="X", date=as_of, iv_30d=0.3, iv_60d=0.32, source="ibkr")

    fn = _unwrap(iv_tasks.sync_gateway)
    result = fn(
        symbols_override=symbols,
        as_of_override=as_of,
        ibkr_fetcher=_ibkr_returns(sample),
        yahoo_fetcher=_yahoo_returns(None),
    )
    assert result["status"] == "ok"
    assert result["written"] == 3
    assert result["skipped_no_data"] == 0
    assert result["errors"] == 0
    assert result["total"] == 3
    assert stub_session.commits == 1
    assert stub_session.closed


def test_yahoo_fallback_runs_when_ibkr_returns_none(
    stub_session: _StubSession,
) -> None:
    as_of = date(2026, 4, 22)
    symbols = ["AAPL", "MSFT"]
    # IBKR returns None for both; Yahoo provides AAPL only.
    ibkr_map: dict[str, Optional[IVSample]] = {"AAPL": None, "MSFT": None}
    yahoo_map: dict[str, Optional[IVSample]] = {
        "AAPL": IVSample(
            symbol="AAPL", date=as_of, iv_30d=0.25, iv_60d=0.28, source="yahoo"
        ),
        "MSFT": None,
    }

    fn = _unwrap(iv_tasks.sync_gateway)
    result = fn(
        symbols_override=symbols,
        as_of_override=as_of,
        ibkr_fetcher=_per_symbol_ibkr(ibkr_map),
        yahoo_fetcher=_per_symbol_yahoo(yahoo_map),
    )

    assert result["written"] == 1
    assert result["skipped_no_data"] == 1
    assert result["errors"] == 0
    assert result["total"] == 2
    assert result["source_breakdown"].get("yahoo") == 1


def test_error_counter_increments_on_fetcher_exception(
    stub_session: _StubSession,
) -> None:
    as_of = date(2026, 4, 22)
    symbols = ["AAPL", "BOOM", "MSFT"]

    def ibkr(symbol: str, as_of: date, *, db: Any = None) -> Optional[IVSample]:
        if symbol == "BOOM":
            raise RuntimeError("simulated gateway timeout")
        if symbol == "AAPL":
            return IVSample(
                symbol="AAPL", date=as_of, iv_30d=0.3, iv_60d=0.32, source="ibkr"
            )
        return None

    def yahoo(symbol: str, as_of: date, *, db: Any = None) -> Optional[IVSample]:
        if symbol == "MSFT":
            return IVSample(
                symbol="MSFT", date=as_of, iv_30d=0.22, iv_60d=0.25, source="yahoo"
            )
        return None

    fn = _unwrap(iv_tasks.sync_gateway)
    result = fn(
        symbols_override=symbols,
        as_of_override=as_of,
        ibkr_fetcher=ibkr,
        yahoo_fetcher=yahoo,
    )
    assert result["written"] == 2  # AAPL + MSFT
    assert result["errors"] == 1  # BOOM
    assert result["skipped_no_data"] == 0
    assert result["total"] == 3
    assert result["written"] + result["skipped_no_data"] + result["errors"] == 3


def test_counter_drift_assertion_fires(
    stub_session: _StubSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate a bug where the ``total`` the task reports is larger
    than what we actually iterated over -- i.e. a silent drop. The
    terminal ``assert written + skipped + errors == total`` MUST fire.

    We do this by patching ``len()`` inside the task module to lie about
    the size of the universe while iteration sees the real list.
    """
    as_of = date(2026, 4, 22)
    symbols = ["AAPL"]
    sample = IVSample(symbol="X", date=as_of, iv_30d=0.3, iv_60d=0.32, source="ibkr")

    import builtins

    real_len = builtins.len
    sentinel = object()
    state = {"marker": sentinel}

    def lying_len(x: Any) -> int:
        # Only inflate the count for a very specific list equal to our
        # symbol universe; everything else (redis lists, frames, etc.)
        # stays truthful.
        if isinstance(x, list) and x == symbols and state["marker"] is sentinel:
            # One-shot: inflate on the first call (the ``total = len(symbols)``
            # read inside sync_gateway).
            state["marker"] = None
            return real_len(x) + 2
        return real_len(x)

    monkeypatch.setattr(builtins, "len", lying_len)

    fn = _unwrap(iv_tasks.sync_gateway)
    with pytest.raises(AssertionError, match="counter drift"):
        fn(
            symbols_override=symbols,
            as_of_override=as_of,
            ibkr_fetcher=_ibkr_returns(sample),
            yahoo_fetcher=_yahoo_returns(None),
        )


def test_empty_universe_returns_ok_zero_counters(
    stub_session: _StubSession,
) -> None:
    fn = _unwrap(iv_tasks.sync_gateway)
    result = fn(
        symbols_override=[],
        as_of_override=date(2026, 4, 22),
        ibkr_fetcher=_ibkr_returns(None),
        yahoo_fetcher=_yahoo_returns(None),
    )
    assert result == {
        "status": "ok",
        "written": 0,
        "skipped_no_data": 0,
        "errors": 0,
        "total": 0,
    }
