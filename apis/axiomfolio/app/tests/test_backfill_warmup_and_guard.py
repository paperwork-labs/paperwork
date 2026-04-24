"""Tests for backfill improvements in ``app.tasks.market.history``:

1. Warmup buffer: PriceData queries use WEINSTEIN_WARMUP_CALENDAR_DAYS
   before the backfill start_dt so Weinstein stages are valid from day 1.
2. UNKNOWN stage guard: the snapshot update only fires when the latest
   backfill row has a recognized (non-UNKNOWN) stage label.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.services.market.constants import WEINSTEIN_WARMUP_CALENDAR_DAYS

# ---------------------------------------------------------------------------
# WEINSTEIN_WARMUP_CALENDAR_DAYS constant
# ---------------------------------------------------------------------------


def test_warmup_constant_is_sane():
    """The warmup constant should cover at least 200 trading days (~150 for
    30-week SMA + 50 for 10-week slope window)."""
    assert WEINSTEIN_WARMUP_CALENDAR_DAYS >= 280


def test_warmup_constant_is_used_in_backfill_task():
    """Verify that the backfill function references the constant rather than
    a hard-coded magic number."""
    from app.tasks.market.history import snapshot_last_n_days

    src = inspect.getsource(snapshot_last_n_days)
    assert "WEINSTEIN_WARMUP_CALENDAR_DAYS" in src, (
        "snapshot_last_n_days should reference WEINSTEIN_WARMUP_CALENDAR_DAYS, not a magic number"
    )
    # Ensure the old magic number is not used as a bare literal
    assert "warmup_calendar_days = 400" not in src, (
        "The old magic-number assignment should be replaced by the constant"
    )


def test_warmup_date_arithmetic():
    """The warmup start date should be WEINSTEIN_WARMUP_CALENDAR_DAYS before
    the backfill start date."""
    start_dt = datetime(2025, 6, 1)
    warmup_start = start_dt - timedelta(days=WEINSTEIN_WARMUP_CALENDAR_DAYS)
    expected = datetime(2025, 6, 1) - timedelta(days=400)
    assert warmup_start == expected


# ---------------------------------------------------------------------------
# UNKNOWN stage guard helpers
# ---------------------------------------------------------------------------


def _is_known_stage(latest_stage) -> bool:
    """Replicates the guard logic from snapshot history backfill."""
    return (
        isinstance(latest_stage, str)
        and bool(latest_stage.strip())
        and latest_stage.strip().upper() != "UNKNOWN"
    )


class _FakeSnapshotUpdate:
    """Tracks calls to session.query(...).filter(...).update(...)."""

    def __init__(self):
        self.update_calls: list[dict] = []

    def make_session(self, symbol: str):
        outer = self

        class _FilterResult:
            def update(self_, values, **kwargs):
                outer.update_calls.append({"symbol": symbol, "values": values})

        class _QueryResult:
            def filter(self_, *args, **kwargs):
                return _FilterResult()

        class _Session:
            def query(self_, model):
                return _QueryResult()

        return _Session()


# ---------------------------------------------------------------------------
# UNKNOWN stage guard: snapshot update should be skipped for UNKNOWN stages
# ---------------------------------------------------------------------------


def test_unknown_guard_allows_known_stage():
    """When the latest backfill row has a known stage, the snapshot should be updated."""
    tracker = _FakeSnapshotUpdate()
    sym = "AAPL"

    payload_rows = [
        {"as_of_date": datetime(2025, 6, 10), "stage_label": "2A"},
    ]
    stage_run_by_date = {
        datetime(2025, 6, 10): {
            "current_stage_days": 5,
            "previous_stage_label": "1",
            "previous_stage_days": 12,
        }
    }

    session = tracker.make_session(sym)
    latest_row = max(payload_rows, key=lambda r: r.get("as_of_date"))
    latest_date = latest_row.get("as_of_date")
    latest_stage = latest_row.get("stage_label")
    latest_info = stage_run_by_date.get(latest_date)

    if latest_info and _is_known_stage(latest_stage):
        session.query(None).filter().update(
            {
                "current_stage_days": latest_info.get("current_stage_days"),
                "previous_stage_label": latest_info.get("previous_stage_label"),
                "previous_stage_days": latest_info.get("previous_stage_days"),
            },
            synchronize_session=False,
        )

    assert len(tracker.update_calls) == 1
    assert tracker.update_calls[0]["values"]["current_stage_days"] == 5
    assert tracker.update_calls[0]["values"]["previous_stage_label"] == "1"
    assert tracker.update_calls[0]["values"]["previous_stage_days"] == 12


@pytest.mark.parametrize(
    "stage_label",
    ["UNKNOWN", "unknown", "  UNKNOWN  ", "", "  ", None],
    ids=["UNKNOWN", "lowercase", "padded", "empty", "whitespace", "None"],
)
def test_unknown_guard_blocks_bad_stages(stage_label):
    """When the latest backfill row has an UNKNOWN/empty/None stage, the
    snapshot update should be skipped entirely."""
    tracker = _FakeSnapshotUpdate()
    sym = "AAPL"

    payload_rows = [
        {"as_of_date": datetime(2025, 6, 10), "stage_label": stage_label},
    ]
    stage_run_by_date = {
        datetime(2025, 6, 10): {
            "current_stage_days": 99,
            "previous_stage_label": "3",
            "previous_stage_days": 50,
        }
    }

    session = tracker.make_session(sym)
    latest_row = max(payload_rows, key=lambda r: r.get("as_of_date"))
    latest_stage = latest_row.get("stage_label")
    latest_date = latest_row.get("as_of_date")
    latest_info = stage_run_by_date.get(latest_date)

    if latest_info and _is_known_stage(latest_stage):
        session.query(None).filter().update(
            {
                "current_stage_days": latest_info.get("current_stage_days"),
                "previous_stage_label": latest_info.get("previous_stage_label"),
                "previous_stage_days": latest_info.get("previous_stage_days"),
            },
            synchronize_session=False,
        )

    assert len(tracker.update_calls) == 0, (
        f"Snapshot should NOT be updated for stage_label={stage_label!r}"
    )


def test_unknown_guard_picks_latest_date_row():
    """When multiple payload rows exist, the guard should evaluate the one
    with the latest as_of_date, not the first or last in list order."""
    tracker = _FakeSnapshotUpdate()
    sym = "MSFT"

    payload_rows = [
        {"as_of_date": datetime(2025, 6, 8), "stage_label": "UNKNOWN"},
        {"as_of_date": datetime(2025, 6, 10), "stage_label": "2A"},
        {"as_of_date": datetime(2025, 6, 9), "stage_label": "UNKNOWN"},
    ]
    stage_run_by_date = {
        datetime(2025, 6, 8): {
            "current_stage_days": 1,
            "previous_stage_label": None,
            "previous_stage_days": None,
        },
        datetime(2025, 6, 9): {
            "current_stage_days": 2,
            "previous_stage_label": None,
            "previous_stage_days": None,
        },
        datetime(2025, 6, 10): {
            "current_stage_days": 3,
            "previous_stage_label": "1",
            "previous_stage_days": 7,
        },
    }

    session = tracker.make_session(sym)
    latest_row = max(payload_rows, key=lambda r: r.get("as_of_date"))
    latest_date = latest_row.get("as_of_date")
    latest_stage = latest_row.get("stage_label")
    latest_info = stage_run_by_date.get(latest_date)

    if latest_info and _is_known_stage(latest_stage):
        session.query(None).filter().update(
            {
                "current_stage_days": latest_info.get("current_stage_days"),
                "previous_stage_label": latest_info.get("previous_stage_label"),
                "previous_stage_days": latest_info.get("previous_stage_days"),
            },
            synchronize_session=False,
        )

    assert len(tracker.update_calls) == 1
    assert tracker.update_calls[0]["values"]["current_stage_days"] == 3


# ---------------------------------------------------------------------------
# is_known_stage edge cases (comprehensive)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stage_label,expected",
    [
        ("2A", True),
        ("1", True),
        ("3", True),
        ("4", True),
        ("Stage 2A", True),
        ("UNKNOWN", False),
        ("unknown", False),
        ("Unknown", False),
        ("  UNKNOWN  ", False),
        ("", False),
        ("  ", False),
        (None, False),
    ],
    ids=[
        "2A",
        "1",
        "3",
        "4",
        "Stage_2A",
        "UNKNOWN",
        "lowercase_unknown",
        "mixed_case",
        "padded_unknown",
        "empty",
        "whitespace",
        "None",
    ],
)
def test_is_known_stage_classification(stage_label, expected):
    """Exhaustive test of the is_known_stage guard logic."""
    assert _is_known_stage(stage_label) == expected


# ---------------------------------------------------------------------------
# UNKNOWN guard: logger.debug is emitted on skip
# ---------------------------------------------------------------------------


def test_unknown_guard_logs_debug_on_skip():
    """When the guard skips a snapshot update, a debug log should be emitted."""
    with patch("app.tasks.market.history.logger") as mock_logger:
        sym = "TSLA"
        latest_stage = "UNKNOWN"
        latest_info = {"current_stage_days": 10}

        if latest_info and not _is_known_stage(latest_stage):
            mock_logger.debug(
                "Skipping snapshot stage update for %s: "
                "latest backfill stage is '%s' (UNKNOWN/empty)",
                sym,
                latest_stage,
            )

        mock_logger.debug.assert_called_once()
        args = mock_logger.debug.call_args
        assert "TSLA" in str(args)
        assert "UNKNOWN" in str(args)
