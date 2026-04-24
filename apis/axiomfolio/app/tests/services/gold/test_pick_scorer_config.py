"""Config-level tests (no database)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.gold.pick_scorer_config import default_config, sum_weights

pytestmark = pytest.mark.no_db


def test_weights_sum_to_one():
    cfg = default_config()
    assert sum_weights(cfg) == Decimal("1.0")
