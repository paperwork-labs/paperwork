"""Shared fixtures for data_engine tests."""

from __future__ import annotations

import pytest

from data_engine import clear_all_caches


@pytest.fixture(autouse=True)
def _isolate_caches() -> None:
    """Wipe per-process caches between tests so order can't hide bugs."""
    clear_all_caches()
