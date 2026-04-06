"""Wilder ATR as a standalone series helper (shared by indicator and stage pipelines)."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_atr_series(df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
    """Wilder's ATR: seed with SMA of first *period* TRs, then recursive smoothing."""
    try:
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift()).abs()
        low_close = (df["Low"] - df["Close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        atr = pd.Series(np.nan, index=tr.index)
        first_valid = tr.first_valid_index()
        if first_valid is None:
            return atr
        start = tr.index.get_loc(first_valid)
        seed_end = start + period
        if seed_end > len(tr):
            return atr
        atr.iloc[seed_end - 1] = tr.iloc[start:seed_end].mean()
        for i in range(seed_end, len(tr)):
            atr.iloc[i] = (atr.iloc[i - 1] * (period - 1) + tr.iloc[i]) / period
        return atr
    except Exception as e:
        logger.warning("ATR(%d) calculation failed: %s", period, e)
        return None
