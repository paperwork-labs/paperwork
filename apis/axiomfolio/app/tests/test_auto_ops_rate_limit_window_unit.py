"""Unit tests for AutoOps explainer window constants (no database)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.services.agent.anomaly_explainer.persistence import (
    DEFAULT_RATE_LIMIT_WINDOW,
    MAX_RATE_LIMIT_WINDOW,
    MIN_RATE_LIMIT_WINDOW,
    clamp_rate_limit_window,
)

pytestmark = pytest.mark.no_db


def test_default_rate_limit_window_is_one_hour() -> None:
    assert timedelta(hours=1) == DEFAULT_RATE_LIMIT_WINDOW


def test_clamp_rate_limit_window() -> None:
    assert clamp_rate_limit_window(timedelta(seconds=0)) == MIN_RATE_LIMIT_WINDOW
    assert clamp_rate_limit_window(timedelta(days=2)) == MAX_RATE_LIMIT_WINDOW
    mid = timedelta(minutes=30)
    assert clamp_rate_limit_window(mid) == mid
