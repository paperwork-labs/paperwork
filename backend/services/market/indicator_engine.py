from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd

from backend.config import settings

logger = logging.getLogger(__name__)


def extract_latest_values(indicator_df: pd.DataFrame) -> Dict[str, Any]:
    """Extract latest (most recent) values from indicator series DataFrame.

    Use with compute_full_indicator_series() when you need scalar values
    for the most recent bar.

    Args:
        indicator_df: DataFrame from compute_full_indicator_series()

    Returns:
        Dict[str, float] with column names as keys and latest non-NaN values
    """
    if indicator_df is None or indicator_df.empty:
        return {}

    out: Dict[str, Any] = {}
    for col in indicator_df.columns:
        series = indicator_df[col]
        if series.empty:
            continue
        # Get last non-NaN value
        last_valid_idx = series.last_valid_index()
        if last_valid_idx is not None:
            val = series.loc[last_valid_idx]
            if pd.notna(val):
                out[col] = float(val) if isinstance(val, (int, float, np.number)) else val
    return out


def compute_core_indicators(data_oldest_first: pd.DataFrame) -> Dict[str, Any]:
    """Compute core technical indicators using pandas/numpy only.

    DEPRECATED: Use compute_full_indicator_series() + extract_latest_values() instead.
    This function duplicates ADX computation and is being phased out.

    Input must be oldest->newest DataFrame with columns: Close (required), High/Low (optional for ATR/ADX).
    """
    out: Dict[str, Any] = {}
    closes = data_oldest_first["Close"]

    # SMAs
    # Keep canonical names aligned with our snapshot schema: sma_5, sma_14, sma_21, sma_50, sma_100, sma_150, sma_200.
    # We also keep sma_8 (non-canonical) for MA-bucket logic and backwards compatibility in raw_analysis.
    for n in [5, 8, 10, 14, 21, 50, 100, 150, 200]:
        if len(closes) >= n:
            sma = closes.rolling(n).mean()
            if not sma.empty and not pd.isna(sma.iloc[-1]):
                out[f"sma_{n}"] = float(sma.iloc[-1])

    # EMAs (10 + pine parity 8/21/200)
    for n in [10, 8, 21, 200]:
        if len(closes) >= n:
            ema = closes.ewm(span=n, adjust=False).mean()
            if not ema.empty and not pd.isna(ema.iloc[-1]):
                key = "ema_10" if n == 10 else f"ema_{n}"
                out[key] = float(ema.iloc[-1])

    # RSI(14)
    if len(closes) >= 14:
        rsi = calculate_rsi_series(closes, 14)
        if rsi is not None and not pd.isna(rsi.iloc[-1]):
            out["rsi"] = float(rsi.iloc[-1])

    # ATR(14, 30)
    if (
        set(["High", "Low", "Close"]).issubset(data_oldest_first.columns)
        and len(data_oldest_first) >= 14
    ):
        atr14 = calculate_atr_series(data_oldest_first, 14)
        if atr14 is not None and not pd.isna(atr14.iloc[-1]):
            out["atr_14"] = float(atr14.iloc[-1])
            # Backwards-compat key (will be removed when old schema fields are dropped)
            out["atr"] = float(atr14.iloc[-1])
        if len(data_oldest_first) >= 30:
            atr30 = calculate_atr_series(data_oldest_first, 30)
            if atr30 is not None and not pd.isna(atr30.iloc[-1]):
                out["atr_30"] = float(atr30.iloc[-1])

    # MACD (12,26,9)
    if len(closes) >= 26:
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - signal
        if not macd_line.empty and not pd.isna(macd_line.iloc[-1]):
            out["macd"] = float(macd_line.iloc[-1])
        if not signal.empty and not pd.isna(signal.iloc[-1]):
            out["macd_signal"] = float(signal.iloc[-1])
        if not hist.empty and not pd.isna(hist.iloc[-1]):
            out["macd_histogram"] = float(hist.iloc[-1])

    # DI/ADX (14-period, Wilder's smoothing)
    if set(["High", "Low", "Close"]).issubset(data_oldest_first.columns):
        try:
            period = 14
            up_move = data_oldest_first["High"].diff()
            down_move = -data_oldest_first["Low"].diff()
            plus_dm_s = pd.Series(
                np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
                index=data_oldest_first.index,
            )
            minus_dm_s = pd.Series(
                np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
                index=data_oldest_first.index,
            )
            tr1 = data_oldest_first["High"] - data_oldest_first["Low"]
            tr2 = (data_oldest_first["High"] - data_oldest_first["Close"].shift()).abs()
            tr3 = (data_oldest_first["Low"] - data_oldest_first["Close"].shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            def _ws(s: pd.Series, p: int) -> pd.Series:
                r = pd.Series(np.nan, index=s.index)
                fv = s.first_valid_index()
                if fv is None:
                    return r
                si = s.index.get_loc(fv)
                se = si + p
                if se > len(s):
                    return r
                r.iloc[se - 1] = s.iloc[si:se].sum()
                for k in range(se, len(s)):
                    r.iloc[k] = r.iloc[k - 1] - r.iloc[k - 1] / p + s.iloc[k]
                return r

            s_tr = _ws(tr, period)
            s_pdm = _ws(plus_dm_s, period)
            s_mdm = _ws(minus_dm_s, period)
            plus_di = (100 * s_pdm / s_tr).replace([np.inf, -np.inf], np.nan)
            minus_di = (100 * s_mdm / s_tr).replace([np.inf, -np.inf], np.nan)
            dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace(
                [np.inf, -np.inf], np.nan
            )
            dx_v = dx.dropna()
            adx = pd.Series(np.nan, index=dx.index)
            if len(dx_v) >= period:
                al = dx.index.get_loc(dx_v.index[period - 1])
                adx.iloc[al] = dx_v.iloc[:period].mean()
                for k in range(al + 1, len(dx)):
                    if not np.isnan(dx.iloc[k]) and not np.isnan(adx.iloc[k - 1]):
                        adx.iloc[k] = (adx.iloc[k - 1] * (period - 1) + dx.iloc[k]) / period
            if not plus_di.empty and not pd.isna(plus_di.iloc[-1]):
                out["plus_di"] = float(plus_di.iloc[-1])
            if not minus_di.empty and not pd.isna(minus_di.iloc[-1]):
                out["minus_di"] = float(minus_di.iloc[-1])
            if not adx.empty and not pd.isna(adx.iloc[-1]):
                out["adx"] = float(adx.iloc[-1])
        except Exception as e:
            logger.warning("ADX computation failed: %s", e)

    return out


def compute_core_indicators_series(data_oldest_first: pd.DataFrame) -> pd.DataFrame:
    """Compute core indicator *series* (vectorized) over the full time index.

    DEPRECATED: Use compute_full_indicator_series() instead.
    This function is superseded by compute_full_indicator_series() which includes
    all indicators (ADX, Bollinger, StochRSI, 52w H/L, stage analysis, etc.)

    Returns a DataFrame indexed like `data_oldest_first` with columns aligned to our snapshot schema:
    - SMA: sma_5/8/14/21/50/100/150/200
    - EMA: ema_10/8/21/200
    - RSI: rsi (14)
    - ATR: atr_14/atr_30
    - MACD: macd/macd_signal
    """
    if data_oldest_first is None or data_oldest_first.empty:
        return pd.DataFrame(index=pd.Index([]))
    if "Close" not in data_oldest_first.columns:
        return pd.DataFrame(index=data_oldest_first.index)

    df = data_oldest_first.copy()
    closes = df["Close"]
    out = pd.DataFrame(index=df.index)

    for n in [5, 8, 14, 21, 50, 100, 150, 200]:
        out[f"sma_{n}"] = closes.rolling(n).mean()

    for n in [10, 8, 21, 200]:
        key = "ema_10" if n == 10 else f"ema_{n}"
        out[key] = closes.ewm(span=n, adjust=False).mean()

    rsi = calculate_rsi_series(closes, 14)
    out["rsi"] = rsi if rsi is not None else np.nan

    # ATR windows (needs High/Low)
    if set(["High", "Low", "Close"]).issubset(df.columns):
        out["atr_14"] = calculate_atr_series(df, 14)
        out["atr_30"] = calculate_atr_series(df, 30)
    else:
        out["atr_14"] = np.nan
        out["atr_30"] = np.nan

    # MACD (12,26,9)
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    out["macd"] = macd_line
    out["macd_signal"] = signal
    out["macd_histogram"] = macd_line - signal
    return out


def _compute_td_sequential_series(
    closes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized TD Sequential per-bar setup counts.

    Returns (td_buy_setup, td_sell_setup, td_buy_complete, td_sell_complete)
    as numpy arrays of the same length as *closes*.
    """
    n = len(closes)
    td_buy = np.zeros(n, dtype=np.int64)
    td_sell = np.zeros(n, dtype=np.int64)
    buy_count = 0
    sell_count = 0
    for i in range(4, n):
        if closes[i] < closes[i - 4]:
            buy_count += 1
            sell_count = 0
        elif closes[i] > closes[i - 4]:
            sell_count += 1
            buy_count = 0
        else:
            buy_count = 0
            sell_count = 0
        td_buy[i] = min(buy_count, 9)
        td_sell[i] = min(sell_count, 9)
        if buy_count >= 9:
            buy_count = 0
        if sell_count >= 9:
            sell_count = 0
    return td_buy, td_sell, td_buy >= 9, td_sell >= 9


def compute_full_indicator_series(
    ohlcv: pd.DataFrame,
    spy_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Unified indicator computation producing full per-bar series.

    Replaces the scattered compute paths (compute_core_indicators,
    compute_core_indicators_series, inline derived calcs in
    _snapshot_from_dataframe and snapshot_last_n_days).

    Parameters
    ----------
    ohlcv : pd.DataFrame
        OHLCV DataFrame (oldest-first), datetime index,
        columns: Open, High, Low, Close, Volume.
    spy_df : pd.DataFrame | None
        SPY OHLCV (oldest-first) for Weinstein stage / Mansfield RS.
        If None, stage columns are omitted.

    Returns
    -------
    pd.DataFrame
        Same datetime index as *ohlcv*, columns matching
        MarketSnapshot / MarketSnapshotHistory schema.
    """
    if ohlcv is None or ohlcv.empty or "Close" not in ohlcv.columns:
        return pd.DataFrame(index=ohlcv.index if ohlcv is not None else pd.Index([]))

    close = ohlcv["Close"]
    high = ohlcv["High"] if "High" in ohlcv.columns else close
    low = ohlcv["Low"] if "Low" in ohlcv.columns else close
    volume = ohlcv["Volume"] if "Volume" in ohlcv.columns else pd.Series(np.nan, index=ohlcv.index)
    has_hlc = {"High", "Low", "Close"}.issubset(ohlcv.columns)

    out = pd.DataFrame(index=ohlcv.index)

    # ── 1. Core indicators (same math as compute_core_indicators_series) ──

    for n in [5, 8, 10, 14, 21, 50, 100, 150, 200]:
        out[f"sma_{n}"] = close.rolling(n).mean()

    for n in [8, 10, 21, 200]:
        out[f"ema_{n}"] = close.ewm(span=n, adjust=False).mean()

    rsi = calculate_rsi_series(close, 14)
    out["rsi"] = rsi if rsi is not None else np.nan

    if has_hlc:
        out["atr_14"] = calculate_atr_series(ohlcv, 14)
        out["atr_30"] = calculate_atr_series(ohlcv, 30)
    else:
        out["atr_14"] = np.nan
        out["atr_30"] = np.nan

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    out["macd"] = macd_line
    out["macd_signal"] = signal
    out["macd_histogram"] = macd_line - signal

    # ── 2. ADX / DI (14-period, vectorized) ──

    if has_hlc:
        period = 14
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
            index=ohlcv.index,
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
            index=ohlcv.index,
        )
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        def _wilder_smooth(series: pd.Series, p: int) -> pd.Series:
            result = pd.Series(np.nan, index=series.index)
            fv = series.first_valid_index()
            if fv is None:
                return result
            s = series.index.get_loc(fv)
            se = s + p
            if se > len(series):
                return result
            result.iloc[se - 1] = series.iloc[s:se].sum()
            for j in range(se, len(series)):
                result.iloc[j] = result.iloc[j - 1] - result.iloc[j - 1] / p + series.iloc[j]
            return result

        smooth_tr = _wilder_smooth(tr, period)
        smooth_plus_dm = _wilder_smooth(plus_dm, period)
        smooth_minus_dm = _wilder_smooth(minus_dm, period)

        plus_di = (100 * smooth_plus_dm / smooth_tr).replace([np.inf, -np.inf], np.nan)
        minus_di = (100 * smooth_minus_dm / smooth_tr).replace([np.inf, -np.inf], np.nan)
        dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace(
            [np.inf, -np.inf], np.nan
        )

        adx = pd.Series(np.nan, index=dx.index)
        dx_valid = dx.dropna()
        if len(dx_valid) >= period:
            adx_start = dx_valid.index[period - 1]
            adx_loc = dx.index.get_loc(adx_start)
            adx.iloc[adx_loc] = dx_valid.iloc[:period].mean()
            for j in range(adx_loc + 1, len(dx)):
                if not np.isnan(dx.iloc[j]) and not np.isnan(adx.iloc[j - 1]):
                    adx.iloc[j] = (adx.iloc[j - 1] * (period - 1) + dx.iloc[j]) / period
        out["plus_di"] = plus_di
        out["minus_di"] = minus_di
        out["adx"] = adx
    else:
        out["plus_di"] = np.nan
        out["minus_di"] = np.nan
        out["adx"] = np.nan

    # ── 3. New indicators ──

    sma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std(ddof=0)
    out["bollinger_upper"] = sma_20 + 2 * std_20
    out["bollinger_lower"] = sma_20 - 2 * std_20
    out["bollinger_width"] = (out["bollinger_upper"] - out["bollinger_lower"]).replace(
        [np.inf, -np.inf], np.nan
    )

    # TTM Squeeze: Bollinger Bands inside Keltner Channels indicates low volatility
    # Keltner Channels: EMA(20) +/- 1.5 * ATR(10)
    ema_20 = close.ewm(span=20, adjust=False).mean()
    atr_10 = calculate_atr_series(ohlcv, 10) if has_hlc else pd.Series(np.nan, index=close.index)
    kc_mult = 1.5
    out["keltner_upper"] = ema_20 + kc_mult * atr_10
    out["keltner_lower"] = ema_20 - kc_mult * atr_10

    # Squeeze on when BB is inside KC (low volatility, potential breakout)
    bb_upper = out["bollinger_upper"]
    bb_lower = out["bollinger_lower"]
    kc_upper = out["keltner_upper"]
    kc_lower = out["keltner_lower"]
    out["ttm_squeeze_on"] = (bb_lower > kc_lower) & (bb_upper < kc_upper)

    # Momentum for direction: smoothed deviation from EMA20 (KC midline)
    mom_src = close - ema_20
    out["ttm_momentum"] = mom_src.rolling(12).mean()

    rsi_s = out["rsi"]
    rsi_min = rsi_s.rolling(14).min()
    rsi_max = rsi_s.rolling(14).max()
    out["stoch_rsi"] = ((rsi_s - rsi_min) / (rsi_max - rsi_min)).replace(
        [np.inf, -np.inf], np.nan
    )

    out["high_52w"] = high.rolling(252).max() if has_hlc else close.rolling(252).max()
    out["low_52w"] = low.rolling(252).min() if has_hlc else close.rolling(252).min()

    out["volume_avg_20d"] = volume.rolling(20).mean()

    # ── 4. Derived fields ──

    atr14 = out["atr_14"]

    out["current_price"] = close
    out["atrp_14"] = (atr14 / close * 100).replace([np.inf, -np.inf], np.nan)
    out["atrp_30"] = (out["atr_30"] / close * 100).replace([np.inf, -np.inf], np.nan)
    out["atr_distance"] = ((close - out["sma_50"]) / atr14).replace(
        [np.inf, -np.inf], np.nan
    )
    out["atr_value"] = atr14
    out["atr_percent"] = out["atrp_14"]

    for label, window in [("20d", 20), ("50d", 50), ("52w", 252)]:
        roll_lo = low.rolling(window).min()
        roll_hi = high.rolling(window).max()
        out[f"range_pos_{label}"] = (
            ((close - roll_lo) / (roll_hi - roll_lo)) * 100
        ).replace([np.inf, -np.inf], np.nan)

    for suffix, sma_col in [
        ("sma_21", "sma_21"),
        ("sma_50", "sma_50"),
        ("sma_100", "sma_100"),
        ("sma_150", "sma_150"),
    ]:
        out[f"atrx_{suffix}"] = ((close - out[sma_col]) / atr14).replace(
            [np.inf, -np.inf], np.nan
        )

    for suffix, ema_col in [("ema8", "ema_8"), ("ema21", "ema_21"), ("ema200", "ema_200")]:
        out[f"pct_dist_{suffix}"] = ((close / out[ema_col] - 1) * 100).replace(
            [np.inf, -np.inf], np.nan
        )

    for suffix, ema_col in [("ema8", "ema_8"), ("ema21", "ema_21"), ("ema200", "ema_200")]:
        out[f"atr_dist_{suffix}"] = ((close - out[ema_col]) / atr14).replace(
            [np.inf, -np.inf], np.nan
        )

    # ── 5. MA bucket (per-bar classification) ──

    sma_cols = ["sma_5", "sma_8", "sma_21", "sma_50", "sma_100", "sma_200"]
    sma_stack = pd.concat(
        [close.rename("price")] + [out[c] for c in sma_cols], axis=1
    )
    any_nan = sma_stack.isna().any(axis=1)
    vals = sma_stack.values
    diffs = np.diff(vals, axis=1)
    leading = np.all(diffs < 0, axis=1)
    lagging = np.all(diffs > 0, axis=1)
    ma_bucket = pd.Series("NEUTRAL", index=ohlcv.index)
    ma_bucket[leading] = "LEADING"
    ma_bucket[lagging] = "LAGGING"
    ma_bucket[any_nan] = "UNKNOWN"
    out["ma_bucket"] = ma_bucket

    # ── 6. Performance windows (rolling % change) ──

    for n in [1, 3, 5, 20, 60, 120, 252]:
        out[f"perf_{n}d"] = close.pct_change(n) * 100

    # ── 7. TD Sequential (per-bar setup counts) ──

    td_buy, td_sell, td_buy_c, td_sell_c = _compute_td_sequential_series(close.values)
    out["td_buy_setup"] = td_buy
    out["td_sell_setup"] = td_sell
    out["td_buy_complete"] = td_buy_c
    out["td_sell_complete"] = td_sell_c

    # ── 8. Stage Analysis spec derived fields ──

    out["ext_pct"] = ((close - out["sma_150"]) / out["sma_150"] * 100).replace(
        [np.inf, -np.inf], np.nan
    )
    out["sma150_slope"] = (
        (out["sma_150"] - out["sma_150"].shift(20)) / out["sma_150"].shift(20) * 100
    ).replace([np.inf, -np.inf], np.nan)
    out["sma50_slope"] = (
        (out["sma_50"] - out["sma_50"].shift(10)) / out["sma_50"].shift(10) * 100
    ).replace([np.inf, -np.inf], np.nan)
    out["ema10_dist_pct"] = ((close - out["ema_10"]) / out["ema_10"] * 100).replace(
        [np.inf, -np.inf], np.nan
    )
    out["ema10_dist_n"] = (out["ema10_dist_pct"] / out["atrp_14"]).replace(
        [np.inf, -np.inf], np.nan
    )
    out["vol_ratio"] = (volume / out["volume_avg_20d"]).replace(
        [np.inf, -np.inf], np.nan
    )

    # ── 9. Stage / RS (Stage Analysis spec — SMA150 anchor, 10 sub-stages) ──

    if spy_df is not None and not spy_df.empty:
        ohlcv_newest = ohlcv.iloc[::-1]
        spy_newest = spy_df.iloc[::-1]
        stage_df = compute_weinstein_stage_series_from_daily(ohlcv_newest, spy_newest)
        stage_analysis_cols = [
            "stage_label", "stage_slope_pct", "stage_dist_pct",
            "ext_pct", "sma150_slope", "sma50_slope",
            "ema10_dist_pct", "ema10_dist_n", "vol_ratio",
            "rs_mansfield_pct",
        ]
        for col in stage_analysis_cols:
            if col in stage_df.columns:
                out[col] = stage_df[col]

    # Multi-timeframe stage: 4H uses daily stage until dedicated 4H bars exist.
    if "stage_label" in out.columns:
        out["stage_4h"] = out["stage_label"]
        out["stage_confirmed"] = True
    else:
        out["stage_4h"] = pd.Series("UNKNOWN", index=out.index, dtype=object)
        out["stage_confirmed"] = pd.Series(pd.NA, index=out.index, dtype="boolean")

    return out


def calculate_performance_windows(
    data_newest_first: pd.DataFrame,
) -> Dict[str, Optional[float]]:
    """Compute performance windows from newest-first DataFrame of OHLCV.
    Returns percentage moves for 1/3/5/20/60/120/252d and MTD/QTD/YTD.
    """
    out: Dict[str, Optional[float]] = {
        "perf_1d": None,
        "perf_3d": None,
        "perf_5d": None,
        "perf_20d": None,
        "perf_60d": None,
        "perf_120d": None,
        "perf_252d": None,
        "perf_mtd": None,
        "perf_qtd": None,
        "perf_ytd": None,
    }
    if (
        data_newest_first is None
        or data_newest_first.empty
        or "Close" not in data_newest_first.columns
    ):
        return out

    close = data_newest_first["Close"]

    def pct(n: int) -> Optional[float]:
        if len(close) > n and close.iloc[0] and close.iloc[n]:
            try:
                return float((close.iloc[0] / close.iloc[n] - 1.0) * 100.0)
            except Exception as e:
                logger.warning("Performance window %dd calculation failed: %s", n, e)
                return None
        return None

    out["perf_1d"] = pct(1)
    out["perf_3d"] = pct(3)
    out["perf_5d"] = pct(5)
    out["perf_20d"] = pct(20)
    out["perf_60d"] = pct(60)
    out["perf_120d"] = pct(120)
    out["perf_252d"] = pct(252)

    # MTD/QTD/YTD (approx using calendar boundaries)
    try:
        idx = data_newest_first.index
        ts0 = idx[0]
        # Month start
        mstart = ts0.replace(day=1)
        qstart_month = ((ts0.month - 1) // 3) * 3 + 1
        qstart = ts0.replace(month=qstart_month, day=1)
        ystart = ts0.replace(month=1, day=1)

        def nearest_close_on_or_after(target):
            matches = idx.get_indexer(
                [target], method="nearest", tolerance=pd.Timedelta(days=7)
            )
            pos = matches[0]
            return close.iloc[pos] if pos >= 0 else None

        for key, dt in [
            ("perf_mtd", mstart),
            ("perf_qtd", qstart),
            ("perf_ytd", ystart),
        ]:
            ref = nearest_close_on_or_after(dt)
            if ref and close.iloc[0]:
                out[key] = float((close.iloc[0] / ref - 1.0) * 100.0)
    except Exception as e:
        logger.warning("Calendar performance window calculation failed: %s", e)

    return out


def calculate_rsi_series(closes: pd.Series, period: int = 14) -> Optional[pd.Series]:
    """RSI using Wilder's exponential smoothing (industry standard, matches Bloomberg).

    First `period` bars use SMA to seed, then exponential smoothing:
        avg_gain[i] = (avg_gain[i-1] * (period-1) + gain[i]) / period
    """
    try:
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = pd.Series(np.nan, index=closes.index, dtype="float64")
        avg_loss = pd.Series(np.nan, index=closes.index, dtype="float64")

        first_valid = gain.first_valid_index()
        if first_valid is None:
            return None
        start = closes.index.get_loc(first_valid)
        seed_end = start + period
        if seed_end > len(closes):
            return None

        avg_gain.iloc[seed_end - 1] = gain.iloc[start:seed_end].mean()
        avg_loss.iloc[seed_end - 1] = loss.iloc[start:seed_end].mean()

        for i in range(seed_end, len(closes)):
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.replace([np.inf, -np.inf], np.nan)
        rsi[avg_loss == 0] = 100.0
        return rsi
    except Exception as e:
        logger.warning("RSI(%d) calculation failed: %s", period, e)
        return None


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


# ----------------------------
# Higher-level analyses
# ----------------------------
def compute_atr_matrix_metrics(
    data_oldest_first: pd.DataFrame, indicators: Dict[str, Any]
) -> Dict[str, Any]:
    """Compute ATR Matrix-related metrics (atr_distance, atr_percent, ma_alignment, price_position_20d)."""
    metrics: Dict[str, Any] = {}
    try:
        current_price = indicators.get("current_price") or indicators.get("close")
        if not current_price and len(data_oldest_first) > 0:
            current_price = float(data_oldest_first["Close"].iloc[-1])

        sma_50 = indicators.get("sma_50")
        atr = indicators.get("atr_14") or indicators.get("atr")

        if current_price and sma_50 and atr and atr > 0:
            metrics["atr_distance"] = (current_price - sma_50) / atr
            metrics["atr_percent"] = (atr / current_price) * 100

        # MA alignment (EMA21 > SMA21 > SMA50 > SMA100 > SMA200) — canonical windows
        # Note: we retain backward-compat raw keys elsewhere, but alignment should use canonical windows.
        ema_21 = indicators.get("ema_21")
        sma_21 = indicators.get("sma_21")
        sma_100 = indicators.get("sma_100")
        sma_200 = indicators.get("sma_200")
        mas = [ema_21, sma_21, sma_50, sma_100, sma_200]
        if all(m is not None for m in mas):
            metrics["ma_aligned"] = all(
                mas[i] >= mas[i + 1] for i in range(len(mas) - 1)
            )
            metrics["ma_alignment"] = metrics["ma_aligned"]

        # 20-day price position
        if len(data_oldest_first) >= 20 and current_price is not None:
            recent = data_oldest_first.tail(20)
            hi = recent["High"].max()
            lo = recent["Low"].min()
            if hi > lo:
                metrics["price_position_20d"] = float(
                    (current_price - lo) / (hi - lo) * 100
                )
    except Exception as e:
        logger.warning("Derived metrics calculation failed: %s", e)
    return metrics


def weekly_from_daily(df_daily_newest_first: pd.DataFrame) -> pd.DataFrame:
    """Convert daily OHLCV (newest->first index) to weekly (oldest->newest)."""
    if df_daily_newest_first is None or df_daily_newest_first.empty:
        return pd.DataFrame()
    daily = df_daily_newest_first.iloc[::-1].copy()  # oldest->newest
    weekly = pd.DataFrame()
    weekly["Open"] = daily["Open"].resample("W-FRI").first()
    weekly["High"] = daily["High"].resample("W-FRI").max()
    weekly["Low"] = daily["Low"].resample("W-FRI").min()
    weekly["Close"] = daily["Close"].resample("W-FRI").last()
    weekly["Volume"] = daily["Volume"].resample("W-FRI").sum()
    weekly = weekly.dropna()
    return weekly


def classify_stage_for_timeframe(
    price: float,
    sma150: float,
    sma50: float,
    ema10: float,
    prev_stage: Optional[str] = None,
    *,
    sma21: float = 0.0,
    sma150_slope: Optional[float] = None,
    sma50_slope: Optional[float] = None,
    ext_pct: Optional[float] = None,
    vol_ratio: float = 0.0,
) -> str:
    """Classify stage for any timeframe using core Stage Analysis spec rules (SMA150 anchor).

    Requires *sma150_slope* and *sma50_slope* for classification. *ext_pct* defaults
    to ``(price - sma150) / sma150 * 100`` when omitted. If slopes are missing,
    returns *prev_stage* when set, else ``"UNKNOWN"``.

    ATRE (2A/2B→2C) and Mansfield RS (2B→2B(RS-)) post-steps are applied in
    :func:`classify_stage_series` and :func:`compute_weinstein_stage_from_daily`,
    not in this function.

    Priority order (first match wins): 4C→4B→4A→1A→1B→2A→2B→2C→3A→3B.
    See Stage_Analysis.docx Section 4 for full rules.
    """
    if sma150_slope is None or sma50_slope is None:
        return prev_stage if prev_stage is not None else "UNKNOWN"
    if ext_pct is None:
        if sma150 == 0:
            return prev_stage if prev_stage is not None else "UNKNOWN"
        ext_pct = (price - sma150) / sma150 * 100.0

    SLOPE_T = 0.35  # ±0.35% slope threshold
    above = price > sma150
    below = not above

    slope_strongly_down = sma150_slope < -SLOPE_T
    slope_down_or_flat = sma150_slope <= 0
    slope_flat = abs(sma150_slope) <= SLOPE_T
    slope_up = sma150_slope > SLOPE_T
    slope_positive = sma150_slope > 0

    # 4C: Deep decline — far below SMA150, slope strongly negative
    if below and slope_strongly_down and ext_pct < -15:
        return "4C"
    # 4B: Active decline — below SMA150, slope strongly negative
    if below and slope_strongly_down:
        return "4B"
    # 4A: Early decline — below SMA150, slope non-positive, SMA50 declining
    if below and slope_down_or_flat and sma50_slope < 0:
        return "4A"
    # 1A: Early base — near SMA150, slope flat/stabilizing, still non-positive
    if abs(ext_pct) < 5 and slope_flat and sma150_slope <= 0:
        return "1A"
    # 1B: Late base / breakout watch — near SMA150, slope flat or gently positive
    if abs(ext_pct) < 5 and (slope_flat or (slope_positive and not slope_up)):
        # Breakout override: 1B→2A when volume confirms and MAs are stacked
        if above and vol_ratio > 1.5 and ema10 > sma21 > sma50:
            return "2A"
        return "1B"
    # 2A: Early advance — above SMA150, slope positive, low extension
    if above and slope_positive and ext_pct <= 5:
        return "2A"
    # 2B: Confirmed advance — above SMA150, slope strongly up, moderate extension
    if above and slope_up and ext_pct <= 15:
        return "2B"
    # 2C: Extended advance — above SMA150, slope strongly up, high extension
    if above and slope_up and ext_pct > 15:
        return "2C"
    # 3A: Early distribution — above SMA150 but slope weakening
    if above and not slope_up:
        return "3A"
    # 3B: Late distribution — catch-all for remaining above SMA150 bars
    if above:
        return "3B"
    # 4A fallback: remaining below SMA150 bars get base/accumulation classification
    return "4A"


def classify_stage_scalar(
    close: float,
    sma150: float,
    sma50: float,
    sma21: float,
    ema10: float,
    sma150_slope: float,
    sma50_slope: float,
    ext_pct: float,
    atre_150: float,
    vol_ratio: float,
) -> str:
    """Classify a single bar into one of 10 Stage Analysis spec sub-stages.

    Delegates to :func:`classify_stage_for_timeframe`. *atre_150* is accepted for
    API compatibility; ATRE override is applied in callers after this returns.
    """
    _ = atre_150
    return classify_stage_for_timeframe(
        close,
        sma150,
        sma50,
        ema10,
        sma21=sma21,
        sma150_slope=sma150_slope,
        sma50_slope=sma50_slope,
        ext_pct=ext_pct,
        vol_ratio=vol_ratio,
    )


def classify_stage_series(
    close: pd.Series,
    sma150: pd.Series,
    sma50: pd.Series,
    sma21: pd.Series,
    ema10: pd.Series,
    sma150_slope: pd.Series,
    sma50_slope: pd.Series,
    ext_pct: pd.Series,
    atre_150: pd.Series,
    vol_ratio: pd.Series,
    rs_mansfield: pd.Series,
) -> pd.Series:
    """Vectorized Stage Analysis spec stage classification for full time series.

    Priority order (first match wins): 4C→4B→4A→1A→1B→2A→2B→2C→3A→3B.
    Post-classification: ATRE override (2A/2B + ATRE_150 > 6 → 2C),
    RS modifier (2B + RS < 0 → "2B(RS-)").
    """
    SLOPE_T = 0.35
    stage = pd.Series("UNKNOWN", index=close.index, dtype="object")

    above = close > sma150
    below = ~above
    has_data = sma150.notna() & sma150_slope.notna() & ext_pct.notna() & sma50_slope.notna()

    slope_strongly_down = sma150_slope < -SLOPE_T
    slope_flat = sma150_slope.abs() <= SLOPE_T
    slope_up = sma150_slope > SLOPE_T
    slope_positive = sma150_slope > 0
    slope_down_or_flat = sma150_slope <= 0

    assigned = pd.Series(False, index=close.index)

    def assign(mask: pd.Series, label: str) -> None:
        nonlocal assigned
        hit = has_data & mask & ~assigned
        stage[hit] = label
        assigned = assigned | hit

    # Priority order: 4C→4B→4A→1A→1B→2A→2B→2C→3A→3B→remaining below
    assign(below & slope_strongly_down & (ext_pct < -15), "4C")
    assign(below & slope_strongly_down, "4B")
    assign(below & slope_down_or_flat & (sma50_slope < 0), "4A")
    assign((ext_pct.abs() < 5) & slope_flat & (sma150_slope <= 0), "1A")
    assign((ext_pct.abs() < 5) & (slope_flat | (slope_positive & ~slope_up)), "1B")
    assign(above & slope_positive & (ext_pct <= 5), "2A")
    assign(above & slope_up & (ext_pct <= 15), "2B")
    assign(above & slope_up & (ext_pct > 15), "2C")
    assign(above & ~slope_up, "3A")
    # 3B: Late distribution — above SMA150 but flat/negative slope (catch-all for above)
    assign(above, "3B")
    # 4A fallback: remaining below SMA150 bars get base/accumulation classification
    assign(below, "4A")

    # Post-classification: Breakout override — 1B with volume + stacked MAs → promote to 2A
    breakout = (
        (stage == "1B") & above
        & (vol_ratio > 1.5) & (ema10 > sma21) & (sma21 > sma50)
    )
    stage[breakout] = "2A"

    # Post-classification: ATRE override — 2A/2B with ATRE_150 > 6 → promote to 2C
    atre_override = (stage.isin(["2A", "2B"])) & (atre_150 > 6.0)
    stage[atre_override] = "2C"

    # Post-classification: RS modifier — 2B with RS < 0 → flag
    rs_flag = (stage == "2B") & (rs_mansfield < 0)
    stage[rs_flag] = "2B(RS-)"

    return stage


def compute_weinstein_stage_from_daily(
    daily_sym_newest_first: pd.DataFrame,
    daily_bm_newest_first: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute Stage Analysis (spec) from daily OHLCV (both newest->first).

    Uses SMA150 as primary anchor per Stage_Analysis.docx.
    Returns latest bar's stage + supporting metrics.
    """
    unknown: Dict[str, Any] = {
        "stage": "UNKNOWN",
        "stage_label": "UNKNOWN",
        "stage_slope_pct": None,
        "stage_dist_pct": None,
        "ext_pct": None,
        "sma150_slope": None,
        "sma50_slope": None,
        "ema10_dist_pct": None,
        "ema10_dist_n": None,
        "vol_ratio": None,
        "rs_mansfield_pct": None,
    }
    if (
        daily_sym_newest_first is None
        or daily_sym_newest_first.empty
        or daily_bm_newest_first is None
        or daily_bm_newest_first.empty
    ):
        return dict(unknown)

    sym = daily_sym_newest_first.iloc[::-1]  # oldest→newest
    bm = daily_bm_newest_first.iloc[::-1]

    if len(sym) < 175:
        return dict(unknown)

    close = sym["Close"]
    volume = sym["Volume"] if "Volume" in sym.columns else pd.Series(np.nan, index=sym.index)
    sma150 = close.rolling(150).mean()
    sma50 = close.rolling(50).mean()
    sma21 = close.rolling(21).mean()
    ema10 = close.ewm(span=10, adjust=False).mean()
    vol_avg = volume.rolling(20).mean()

    # Stage Analysis spec metrics
    ext_pct = ((close - sma150) / sma150 * 100).replace([np.inf, -np.inf], np.nan)
    sma150_slope_s = ((sma150 - sma150.shift(20)) / sma150.shift(20) * 100).replace([np.inf, -np.inf], np.nan)
    sma50_slope_s = ((sma50 - sma50.shift(10)) / sma50.shift(10) * 100).replace([np.inf, -np.inf], np.nan)
    vol_ratio_s = (volume / vol_avg).replace([np.inf, -np.inf], np.nan)

    atr14 = calculate_atr_series(sym, 14) if {"High", "Low", "Close"}.issubset(sym.columns) else pd.Series(np.nan, index=sym.index)
    atre_150 = ((close - sma150) / atr14).replace([np.inf, -np.inf], np.nan) if atr14 is not None else pd.Series(np.nan, index=sym.index)
    ema10_dist_pct_s = ((close - ema10) / ema10 * 100).replace([np.inf, -np.inf], np.nan)
    atrp14 = (atr14 / close * 100).replace([np.inf, -np.inf], np.nan) if atr14 is not None else pd.Series(np.nan, index=sym.index)
    ema10_dist_n_s = (ema10_dist_pct_s / atrp14).replace([np.inf, -np.inf], np.nan)

    # RS Mansfield (daily RS vs 252-day SMA of RS)
    bm_close = bm["Close"].reindex(sym.index, method="ffill")
    rs = (close / bm_close.replace(0, np.nan)).astype("float64")
    rs_ma = rs.rolling(252).mean()
    rs_mansfield = ((rs / rs_ma - 1.0) * 100.0).replace([np.inf, -np.inf], np.nan)

    # Get latest valid values
    def last_val(s: pd.Series) -> Optional[float]:
        v = s.iloc[-1] if not s.empty else None
        return float(v) if v is not None and not pd.isna(v) else None

    c = last_val(close)
    s150 = last_val(sma150)
    s50 = last_val(sma50)
    s21 = last_val(sma21)
    e10 = last_val(ema10)
    sl150 = last_val(sma150_slope_s)
    sl50 = last_val(sma50_slope_s)
    ep = last_val(ext_pct)
    at150 = last_val(atre_150)
    vr = last_val(vol_ratio_s)
    rm = last_val(rs_mansfield)

    if c is None or s150 is None or sl150 is None or ep is None or sl50 is None:
        return dict(unknown)

    stage_label = classify_stage_scalar(
        c, s150, s50 or 0, s21 or 0, e10 or 0,
        sl150, sl50, ep, at150 or 0, vr or 0,
    )

    # ATRE override
    if stage_label in ("2A", "2B") and at150 is not None and at150 > 6.0:
        stage_label = "2C"
    # RS modifier
    if stage_label == "2B" and rm is not None and rm < 0:
        stage_label = "2B(RS-)"

    return {
        "stage": f"STAGE_{stage_label}",
        "stage_label": stage_label,
        "price": c,
        "sma150": s150,
        "stage_slope_pct": sl150,
        "stage_dist_pct": ep,
        "ext_pct": ep,
        "sma150_slope": sl150,
        "sma50_slope": sl50,
        "ema10_dist_pct": last_val(ema10_dist_pct_s),
        "ema10_dist_n": last_val(ema10_dist_n_s),
        "vol_ratio": vr,
        "rs_mansfield_pct": rm,
    }


def compute_weinstein_stage_series_from_daily(
    daily_sym_newest_first: pd.DataFrame,
    daily_bm_newest_first: pd.DataFrame,
) -> pd.DataFrame:
    """Compute daily stage/RS series (Stage Analysis spec) using SMA150 as primary anchor.

    Output columns (daily resolution — no weekly forward-fill):
    - stage_label: 1A|1B|2A|2B|2B(RS-)|2C|3A|3B|4A|4B|4C|UNKNOWN
    - ext_pct, sma150_slope, sma50_slope, ema10_dist_pct, ema10_dist_n
    - vol_ratio, rs_mansfield_pct, stage_slope_pct, stage_dist_pct
    """
    if (
        daily_sym_newest_first is None
        or daily_sym_newest_first.empty
        or daily_bm_newest_first is None
        or daily_bm_newest_first.empty
    ):
        return pd.DataFrame(index=pd.Index([]))

    sym = daily_sym_newest_first.iloc[::-1]  # oldest→newest
    bm = daily_bm_newest_first.iloc[::-1]

    close = sym["Close"]
    volume = sym["Volume"] if "Volume" in sym.columns else pd.Series(np.nan, index=sym.index)

    sma150 = close.rolling(150).mean()
    sma50 = close.rolling(50).mean()
    sma21 = close.rolling(21).mean()
    ema10 = close.ewm(span=10, adjust=False).mean()
    vol_avg = volume.rolling(20).mean()

    ext_pct = ((close - sma150) / sma150 * 100).replace([np.inf, -np.inf], np.nan)
    sma150_slope = ((sma150 - sma150.shift(20)) / sma150.shift(20) * 100).replace([np.inf, -np.inf], np.nan)
    sma50_slope = ((sma50 - sma50.shift(10)) / sma50.shift(10) * 100).replace([np.inf, -np.inf], np.nan)
    vol_ratio = (volume / vol_avg).replace([np.inf, -np.inf], np.nan)

    atr14 = calculate_atr_series(sym, 14) if {"High", "Low", "Close"}.issubset(sym.columns) else pd.Series(np.nan, index=sym.index)
    if atr14 is None:
        atr14 = pd.Series(np.nan, index=sym.index)
    atre_150 = ((close - sma150) / atr14).replace([np.inf, -np.inf], np.nan)
    ema10_dist_pct = ((close - ema10) / ema10 * 100).replace([np.inf, -np.inf], np.nan)
    atrp14 = (atr14 / close * 100).replace([np.inf, -np.inf], np.nan)
    ema10_dist_n = (ema10_dist_pct / atrp14).replace([np.inf, -np.inf], np.nan)

    # RS Mansfield (daily)
    bm_close = bm["Close"].reindex(sym.index, method="ffill")
    rs = (close / bm_close.replace(0, np.nan)).astype("float64")
    rs_ma = rs.rolling(252).mean()
    rs_mansfield = ((rs / rs_ma - 1.0) * 100.0).replace([np.inf, -np.inf], np.nan)

    # Vectorized stage classification
    stage_label = classify_stage_series(
        close, sma150, sma50, sma21, ema10,
        sma150_slope, sma50_slope, ext_pct, atre_150,
        vol_ratio, rs_mansfield,
    )

    daily_out = pd.DataFrame(
        {
            "stage_label": stage_label,
            "stage_slope_pct": sma150_slope,
            "stage_dist_pct": ext_pct,
            "ext_pct": ext_pct,
            "sma150_slope": sma150_slope,
            "sma50_slope": sma50_slope,
            "ema10_dist_pct": ema10_dist_pct,
            "ema10_dist_n": ema10_dist_n,
            "vol_ratio": vol_ratio,
            "rs_mansfield_pct": rs_mansfield,
        },
        index=sym.index,
    )
    return daily_out


def classify_ma_bucket_from_ma(ma: Dict[str, Any]) -> Dict[str, Any]:
    """Classify leading/lagging/neutral from moving averages dict (includes price)."""
    seq = [
        ma.get("price"),
        ma.get("sma_5"),
        ma.get("sma_8"),
        ma.get("sma_21"),
        ma.get("sma_50"),
        ma.get("sma_100"),
        ma.get("sma_200"),
    ]
    if all(isinstance(x, (int, float)) for x in seq):
        strictly_desc = all(seq[i] > seq[i + 1] for i in range(len(seq) - 1))
        strictly_asc = all(seq[i] < seq[i + 1] for i in range(len(seq) - 1))
        bucket = (
            "LEADING" if strictly_desc else ("LAGGING" if strictly_asc else "NEUTRAL")
        )
    else:
        bucket = "UNKNOWN"
    return {"bucket": bucket, "data": ma}


# -------------------------------------------------------------
# Chart metrics (TD Sequential, gaps, trendlines)
# -------------------------------------------------------------
def compute_td_sequential_counts(closes: List[float]) -> Dict[str, Optional[int]]:
    """Compute simplified TD Sequential buy/sell setup counts from a close series.

    Expects newest-first closes; returns last observed setup counts.
    """
    if not closes or len(closes) < 5:
        return {"td_buy_setup": None, "td_sell_setup": None}
    buy_setup = 0
    sell_setup = 0
    # Iterate oldest->newest for stability
    for i in range(len(closes) - 1, -1, -1):
        j = i + 4
        if j >= len(closes):
            continue
        if closes[i] < closes[j]:
            buy_setup += 1
            sell_setup = 0
        elif closes[i] > closes[j]:
            sell_setup += 1
            buy_setup = 0
        else:
            buy_setup = 0
            sell_setup = 0
    return {
        "td_buy_setup": int(buy_setup) if buy_setup > 0 else None,
        "td_sell_setup": int(sell_setup) if sell_setup > 0 else None,
    }


def compute_gap_counts(
    data_newest_first: pd.DataFrame,
    min_gap_percent: float = 0.5,
) -> Dict[str, Optional[int]]:
    """Count unfilled gaps up/down over recent window.

    A gap up if Low[t] > High[t+1] and pct gap >= min_gap_percent.
    Consider a gap filled if subsequent bars cross the gap zone.
    """
    out = {"gaps_unfilled_up": None, "gaps_unfilled_down": None}
    if data_newest_first is None or data_newest_first.empty:
        return out
    if not set(["High", "Low"]).issubset(set(data_newest_first.columns)):
        return out
    hi = data_newest_first["High"].tolist()
    lo = data_newest_first["Low"].tolist()
    up_gaps = []  # list of tuples (top, bottom, start_idx)
    down_gaps = []
    pct = min_gap_percent / 100.0
    # iterate newest->older pairs
    for i in range(len(lo) - 1):
        # current bar = i, previous = i+1 (since newest-first ordering)
        # Up gap
        if lo[i] > hi[i + 1] and (lo[i] / hi[i + 1] - 1.0) >= pct:
            up_gaps.append((lo[i], hi[i + 1], i))
        # Down gap
        if hi[i] < lo[i + 1] and (1.0 - hi[i] / lo[i + 1]) >= pct:
            down_gaps.append((lo[i + 1], hi[i], i))

    # determine filled status scanning forward (towards older bars)
    def count_unfilled(gaps, direction: str) -> int:
        count = 0
        for top, bottom, start in gaps:
            filled = False
            for j in range(start + 1, len(lo)):
                if direction == "up":
                    if lo[j] <= bottom:
                        filled = True
                        break
                else:
                    if hi[j] >= top:
                        filled = True
                        break
            if not filled:
                count += 1
        return count

    out["gaps_unfilled_up"] = count_unfilled(up_gaps, "up")
    out["gaps_unfilled_down"] = count_unfilled(down_gaps, "down")
    return out


def compute_trendline_counts(
    data_oldest_first: pd.DataFrame,
    pivot_period: int = 20,
    max_lines: int = 3,
) -> Dict[str, Optional[int]]:
    """Simple trendline counts based on pivot highs/lows over a rolling window.

    Returns number of uptrend lines (connecting rising pivot lows) and
    downtrend lines (connecting falling pivot highs), capped by max_lines.
    """
    out = {"trend_up_count": None, "trend_down_count": None}
    if data_oldest_first is None or data_oldest_first.empty:
        return out
    if not set(["High", "Low"]).issubset(set(data_oldest_first.columns)):
        return out
    highs = data_oldest_first["High"].reset_index(drop=True)
    lows = data_oldest_first["Low"].reset_index(drop=True)
    n = len(highs)
    if n < pivot_period * 2:
        return out
    # find pivot highs/lows: local extrema over window [i-pivot, i+pivot]
    piv_hi = []
    piv_lo = []
    for i in range(pivot_period, n - pivot_period):
        h = highs.iloc[i]
        win_hi = highs.iloc[i - pivot_period : i + pivot_period + 1]
        if h == win_hi.max():
            piv_hi.append((i, float(h)))
        l = lows.iloc[i]
        win_lo = lows.iloc[i - pivot_period : i + pivot_period + 1]
        if l == win_lo.min():
            piv_lo.append((i, float(l)))
    # count lines with monotonic slope constraints
    up = 0
    for a in range(len(piv_lo)):
        for b in range(a + 1, min(a + 6, len(piv_lo))):
            if piv_lo[b][1] > piv_lo[a][1]:
                up += 1
                break
        if up >= max_lines:
            break
    down = 0
    for a in range(len(piv_hi)):
        for b in range(a + 1, min(a + 6, len(piv_hi))):
            if piv_hi[b][1] < piv_hi[a][1]:
                down += 1
                break
        if down >= max_lines:
            break
    out["trend_up_count"] = up
    out["trend_down_count"] = down
    return out
