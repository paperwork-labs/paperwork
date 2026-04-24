from __future__ import annotations

import pandas as pd
import pytest

from app.services.market.dataframe_utils import ensure_newest_first, ensure_oldest_first
from app.services.market.market_data_service import snapshot_builder

pytestmark = pytest.mark.no_db


def test_ensure_order_helpers_normalize_index_direction():
    df = pd.DataFrame(
        {
            "Close": [100.0, 110.0, 120.0],
            "High": [101.0, 111.0, 121.0],
            "Low": [99.0, 109.0, 119.0],
            "Volume": [1_000, 1_100, 1_200],
        },
        index=pd.to_datetime(["2026-02-10", "2026-02-11", "2026-02-12"]),
    )

    newest = ensure_newest_first(df)
    oldest = ensure_oldest_first(newest)

    assert newest.index[0] == pd.Timestamp("2026-02-12")
    assert newest.index[-1] == pd.Timestamp("2026-02-10")
    assert oldest.index[0] == pd.Timestamp("2026-02-10")
    assert oldest.index[-1] == pd.Timestamp("2026-02-12")


def test_snapshot_from_dataframe_uses_newest_bar_for_current_fields():
    # Intentionally pass oldest->newest to ensure normalization is enforced.
    df = pd.DataFrame(
        {
            "Open": [100.0, 105.0],
            "High": [101.0, 111.0],
            "Low": [99.0, 104.0],
            "Close": [100.0, 110.0],
            "Volume": [1_000, 1_200],
        },
        index=pd.to_datetime(["2026-02-10", "2026-02-11"]),
    )

    snap = snapshot_builder._snapshot_from_dataframe(df)

    assert snap["current_price"] == 110.0
    assert str(snap.get("as_of_timestamp", "")).startswith("2026-02-11")
    # Perf windows must be anchored on the newest close.
    assert snap.get("perf_1d") == pytest.approx(10.0, abs=1e-6)

