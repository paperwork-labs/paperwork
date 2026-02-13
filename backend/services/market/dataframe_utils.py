from __future__ import annotations

from typing import Sequence

import pandas as pd


def ensure_newest_first(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy sorted by index descending (newest->oldest)."""
    if df is None or df.empty:
        return df
    return df.sort_index(ascending=False)


def ensure_oldest_first(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy sorted by index ascending (oldest->newest)."""
    if df is None or df.empty:
        return df
    return df.sort_index(ascending=True)


def price_data_rows_to_dataframe(
    rows: Sequence,
    *,
    ascending: bool = True,
) -> pd.DataFrame:
    """Convert PriceData ORM rows or tuples into an OHLCV DataFrame.

    Accepts rows in either of these forms:
    - ORM objects with attributes: date, open_price, high_price, low_price, close_price, volume
    - Tuples: (date, open, high, low, close, volume)
    """
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    out_rows = []
    for r in rows:
        if isinstance(r, (tuple, list)):
            date, open_p, high_p, low_p, close_p, volume = r
        else:
            date = getattr(r, "date")
            open_p = getattr(r, "open_price")
            high_p = getattr(r, "high_price")
            low_p = getattr(r, "low_price")
            close_p = getattr(r, "close_price")
            volume = getattr(r, "volume")
        close_val = float(close_p or 0)
        out_rows.append(
            {
                "date": date,
                "Open": float(open_p) if open_p is not None else close_val,
                "High": float(high_p) if high_p is not None else close_val,
                "Low": float(low_p) if low_p is not None else close_val,
                "Close": close_val,
                "Volume": int(volume or 0),
            }
        )

    df = pd.DataFrame(out_rows)
    if not df.empty:
        df.set_index("date", inplace=True)
        df = ensure_oldest_first(df) if ascending else ensure_newest_first(df)
    return df
