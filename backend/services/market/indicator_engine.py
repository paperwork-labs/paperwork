from __future__ import annotations

from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from backend.config import settings


def compute_core_indicators(data_oldest_first: pd.DataFrame) -> Dict[str, Any]:
    """Compute core technical indicators using pandas/numpy only.

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

    # DI/ADX (approx)
    try:
        if set(["High", "Low", "Close"]).issubset(data_oldest_first.columns):
            period = 14
            up_move = data_oldest_first["High"].diff()
            down_move = -data_oldest_first["Low"].diff()
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
            tr1 = data_oldest_first["High"] - data_oldest_first["Low"]
            tr2 = (data_oldest_first["High"] - data_oldest_first["Close"].shift()).abs()
            tr3 = (data_oldest_first["Low"] - data_oldest_first["Close"].shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            plus_di = 100 * pd.Series(plus_dm).rolling(window=period).sum() / atr
            minus_di = 100 * pd.Series(minus_dm).rolling(window=period).sum() / atr
            dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace(
                [np.inf, -np.inf], np.nan
            )
            adx = dx.rolling(window=period).mean()
            if not plus_di.empty and not pd.isna(plus_di.iloc[-1]):
                out["plus_di"] = float(plus_di.iloc[-1])
            if not minus_di.empty and not pd.isna(minus_di.iloc[-1]):
                out["minus_di"] = float(minus_di.iloc[-1])
            if not adx.empty and not pd.isna(adx.iloc[-1]):
                out["adx"] = float(adx.iloc[-1])
    except Exception:
        pass

    return out


def compute_core_indicators_series(data_oldest_first: pd.DataFrame) -> pd.DataFrame:
    """Compute core indicator *series* (vectorized) over the full time index.

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
        td_buy[i] = buy_count
        td_sell[i] = sell_count
    return td_buy, td_sell, td_buy >= 9, td_sell >= 9


def compute_full_indicator_series(
    ohlcv: pd.DataFrame,
    spy_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Unified indicator computation producing full per-bar series.

    Replaces the scattered compute paths (compute_core_indicators,
    compute_core_indicators_series, inline derived calcs in
    _snapshot_from_dataframe and backfill_snapshot_history_last_n_days).

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
        atr_di = tr.rolling(window=period).mean()
        plus_di = 100 * plus_dm.rolling(window=period).sum() / atr_di
        minus_di = 100 * minus_dm.rolling(window=period).sum() / atr_di
        dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace(
            [np.inf, -np.inf], np.nan
        )
        adx = dx.rolling(window=period).mean()
        out["plus_di"] = plus_di
        out["minus_di"] = minus_di
        out["adx"] = adx
    else:
        out["plus_di"] = np.nan
        out["minus_di"] = np.nan
        out["adx"] = np.nan

    # ── 3. New indicators ──

    sma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std()
    out["bollinger_upper"] = sma_20 + 2 * std_20
    out["bollinger_lower"] = sma_20 - 2 * std_20
    out["bollinger_width"] = (out["bollinger_upper"] - out["bollinger_lower"]).replace(
        [np.inf, -np.inf], np.nan
    )

    rsi_s = out["rsi"]
    rsi_min = rsi_s.rolling(14).min()
    rsi_max = rsi_s.rolling(14).max()
    out["stoch_rsi"] = ((rsi_s - rsi_min) / (rsi_max - rsi_min)).replace(
        [np.inf, -np.inf], np.nan
    )

    out["high_52w"] = close.rolling(252).max()
    out["low_52w"] = close.rolling(252).min()

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

    # ── 8. Stage / RS (only if spy_df provided) ──

    if spy_df is not None and not spy_df.empty:
        ohlcv_newest = ohlcv.iloc[::-1]
        spy_newest = spy_df.iloc[::-1]
        stage_df = compute_weinstein_stage_series_from_daily(ohlcv_newest, spy_newest)
        for col in ["stage_label", "stage_slope_pct", "stage_dist_pct", "rs_mansfield_pct"]:
            if col in stage_df.columns:
                out[col] = stage_df[col]

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
            except Exception:
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
    except Exception:
        pass

    return out


def calculate_rsi_series(closes: pd.Series, period: int = 14) -> Optional[pd.Series]:
    try:
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except Exception:
        return None


def calculate_atr_series(df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
    try:
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift()).abs()
        low_close = (df["Low"] - df["Close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    except Exception:
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
    except Exception:
        pass
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


def compute_weinstein_stage_from_daily(
    daily_sym_newest_first: pd.DataFrame,
    daily_bm_newest_first: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute Weinstein stage from daily OHLCV of symbol and benchmark (both newest->first)."""
    unknown = {
        "stage": "UNKNOWN",
        "stage_label": "UNKNOWN",
        "stage_slope_pct": None,
        "stage_dist_pct": None,
        "rs_mansfield_pct": None,
    }
    if (
        daily_sym_newest_first is None
        or daily_sym_newest_first.empty
        or daily_bm_newest_first is None
        or daily_bm_newest_first.empty
    ):
        return dict(unknown)

    w_sym = weekly_from_daily(daily_sym_newest_first)
    w_bm = weekly_from_daily(daily_bm_newest_first)
    if w_sym.empty or w_bm.empty:
        return dict(unknown)

    # Align indexes
    idx = w_sym.index.intersection(w_bm.index)
    w_sym = w_sym.loc[idx]
    w_bm = w_bm.loc[idx]
    # Need enough weekly bars for 30W SMA + stable slope. Mansfield RS needs 52W; stage can still compute without it.
    if len(w_sym) < 35:
        return dict(unknown)

    close = w_sym["Close"]
    sma30 = close.rolling(30).mean()
    vol50 = w_sym["Volume"].rolling(50).mean()

    # Relative strength vs benchmark (weekly)
    rs = (close / w_bm["Close"].replace(0, pd.NA)).dropna()

    def slope(series: pd.Series, window: int = 10) -> float:
        last = series.tail(window)
        if len(last) < 2:
            return 0.0
        return float(last.iloc[-1] - last.iloc[0]) / max(1.0, len(last) - 1)

    price = float(close.iloc[-1])
    sma30_now = float(sma30.iloc[-1]) if not pd.isna(sma30.iloc[-1]) else None
    sma30_slope = slope(sma30)
    rs_slope = slope(rs)
    vol_ratio = None
    if not pd.isna(vol50.iloc[-1]) and vol50.iloc[-1] > 0:
        vol_ratio = float(w_sym["Volume"].iloc[-1] / vol50.iloc[-1])

    stage = "UNKNOWN"
    stage_label = "UNKNOWN"
    stage_dist_pct = None
    stage_slope_pct = None
    if sma30_now:
        try:
            stage_dist_pct = float((price / sma30_now - 1.0) * 100.0) if sma30_now else None
        except Exception:
            stage_dist_pct = None
        try:
            prev = sma30.iloc[-6] if len(sma30) >= 6 and not pd.isna(sma30.iloc[-6]) else None
            stage_slope_pct = float((sma30_now / prev - 1.0) * 100.0) if (prev and sma30_now) else None
        except Exception:
            stage_slope_pct = None

        slope_up = float(getattr(settings, "STAGE_SLOPE_PCT_UP", 0.05))
        slope_down = float(getattr(settings, "STAGE_SLOPE_PCT_DOWN", -0.05))
        slope_flat = float(getattr(settings, "STAGE_SLOPE_PCT_FLAT", 0.05))
        dist_flat = float(getattr(settings, "STAGE_DIST_PCT_FLAT", 5.0))
        dist_2a = float(getattr(settings, "STAGE_DIST_PCT_STAGE2_A", 5.0))
        dist_2b = float(getattr(settings, "STAGE_DIST_PCT_STAGE2_B", 15.0))

        slope_ok = stage_slope_pct is not None
        dist_ok = stage_dist_pct is not None
        if slope_ok and dist_ok:
            if stage_slope_pct > slope_up and stage_dist_pct > 0:
                stage = "STAGE_2_UPTREND"
                stage_label = "2"
            elif stage_slope_pct < slope_down and stage_dist_pct < 0:
                stage = "STAGE_4_DOWNTREND"
                stage_label = "4"
            elif abs(stage_slope_pct) <= slope_flat and abs(stage_dist_pct) <= dist_flat:
                stage = "STAGE_1_BASE"
                stage_label = "1"
            else:
                stage = "STAGE_3_DISTRIBUTION"
                stage_label = "3"

            # Stage 2 refinement (2A/2B/2C) based on distance from 30W SMA.
            if stage_label == "2":
                if stage_dist_pct <= dist_2a:
                    stage_label = "2A"
                elif stage_dist_pct <= dist_2b:
                    stage_label = "2B"
                else:
                    stage_label = "2C"

    # Mansfield Relative Strength (weekly RS vs 52-week SMA of RS), expressed as %
    rs_mansfield_pct = None
    try:
        if len(rs) >= 52:
            rs_ma = rs.rolling(52).mean()
            rs_now = rs.iloc[-1]
            rs_ma_now = rs_ma.iloc[-1]
            if rs_ma_now and not pd.isna(rs_ma_now):
                rs_mansfield_pct = float((rs_now / rs_ma_now - 1.0) * 100.0)
    except Exception:
        rs_mansfield_pct = None

    return {
        "stage": stage,
        "stage_label": stage_label,
        "price": price,
        "sma30w": sma30_now,
        "sma30w_slope": sma30_slope,
        "stage_slope_pct": stage_slope_pct,
        "stage_dist_pct": stage_dist_pct,
        "rs_slope": rs_slope,
        "rs_mansfield_pct": rs_mansfield_pct,
        "vol_ratio_50w": vol_ratio,
        "as_of": idx[-1].isoformat() if len(idx) else None,
    }


def compute_weinstein_stage_series_from_daily(
    daily_sym_newest_first: pd.DataFrame,
    daily_bm_newest_first: pd.DataFrame,
) -> pd.DataFrame:
    """Compute a *daily* stage/RS series (approx) by computing weekly stage and forward-filling to days.

    Output columns:
    - stage_label: "1"|"2"|"3"|"4"|"UNKNOWN"
    - stage_slope_pct, stage_dist_pct, rs_mansfield_pct
    """
    if (
        daily_sym_newest_first is None
        or daily_sym_newest_first.empty
        or daily_bm_newest_first is None
        or daily_bm_newest_first.empty
    ):
        return pd.DataFrame(index=pd.Index([]))

    # Weekly bars (oldest->newest)
    w_sym = weekly_from_daily(daily_sym_newest_first)
    w_bm = weekly_from_daily(daily_bm_newest_first)
    if w_sym.empty or w_bm.empty:
        return pd.DataFrame(index=daily_sym_newest_first.iloc[::-1].index)

    idx = w_sym.index.intersection(w_bm.index)
    w_sym = w_sym.loc[idx]
    w_bm = w_bm.loc[idx]
    if w_sym.empty:
        return pd.DataFrame(index=daily_sym_newest_first.iloc[::-1].index)

    close = w_sym["Close"]
    sma30 = close.rolling(30).mean()

    def slope_series(series: pd.Series, window: int = 10) -> pd.Series:
        # Similar to (last-first)/(n-1) over a trailing window.
        return (series - series.shift(window - 1)) / max(1.0, window - 1)

    sma30_slope = slope_series(sma30, window=10)

    rs = (close / w_bm["Close"].replace(0, pd.NA)).astype("float64")
    rs_slope = slope_series(rs, window=10)

    # Stage slope/dist metrics
    stage_dist_pct = (close / sma30 - 1.0) * 100.0
    stage_slope_pct = (sma30 / sma30.shift(5) - 1.0) * 100.0

    # Mansfield RS % (weekly RS vs 52-week SMA of RS)
    rs_mansfield_pct = (rs / rs.rolling(52).mean() - 1.0) * 100.0

    # Stage label classification
    stage_label = pd.Series(index=idx, dtype="object")
    stage_label[:] = "UNKNOWN"
    has_sma = ~sma30.isna()

    slope_up = float(getattr(settings, "STAGE_SLOPE_PCT_UP", 0.05))
    slope_down = float(getattr(settings, "STAGE_SLOPE_PCT_DOWN", -0.05))
    slope_flat = float(getattr(settings, "STAGE_SLOPE_PCT_FLAT", 0.05))
    dist_flat = float(getattr(settings, "STAGE_DIST_PCT_FLAT", 5.0))
    dist_2a = float(getattr(settings, "STAGE_DIST_PCT_STAGE2_A", 5.0))
    dist_2b = float(getattr(settings, "STAGE_DIST_PCT_STAGE2_B", 15.0))

    up = has_sma & (stage_slope_pct > slope_up) & (stage_dist_pct > 0)
    down = has_sma & (stage_slope_pct < slope_down) & (stage_dist_pct < 0)
    stage_label[up] = "2"
    stage_label[down] = "4"

    # Remaining: base/distribution
    remaining = has_sma & ~(up | down)
    flat = remaining & (stage_slope_pct.abs() <= slope_flat)
    near = remaining & (stage_dist_pct.abs() <= dist_flat)
    base = flat & near
    stage_label[base] = "1"
    stage_label[remaining & ~base] = "3"

    # Stage 2 refinement (2A/2B/2C) based on distance from 30W SMA.
    is_stage2 = stage_label == "2"
    dist = stage_dist_pct.reindex(idx)
    stage_label[is_stage2 & (dist <= dist_2a)] = "2A"
    stage_label[is_stage2 & (dist > dist_2a) & (dist <= dist_2b)] = "2B"
    stage_label[is_stage2 & (dist > dist_2b)] = "2C"

    weekly_out = pd.DataFrame(
        {
            "stage_label": stage_label,
            "stage_slope_pct": stage_slope_pct,
            "stage_dist_pct": stage_dist_pct,
            "rs_mansfield_pct": rs_mansfield_pct,
        },
        index=idx,
    )

    # Expand weekly -> daily (oldest->newest daily index)
    daily_idx = daily_sym_newest_first.iloc[::-1].index
    daily_out = weekly_out.reindex(daily_idx, method="ffill")
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
