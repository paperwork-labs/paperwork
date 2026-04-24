"""Indicator computation engine — RSI, ATR, MACD, ADX, Stage Analysis, and more.

DANGER ZONE: This file contains core financial calculations. See .cursor/rules/protected-regions.mdc
Related docs: Stage_Analysis.docx (full specification), docs/KNOWLEDGE.md (decision log)
Related rules: quant-analyst.mdc
IRON LAW: All indicator computation must go through compute_full_indicator_series().
IRON LAW: SMA150 is the primary stage anchor per Stage Analysis spec.

Stage classification is in stage_classifier.py (10 sub-stages: 1A/1B, 2A/2B/2C, 3A/3B, 4A/4B/4C).

Medallion layer: silver. See docs/ARCHITECTURE.md and D127.

medallion: silver
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd

from backend.observability import traced
from backend.services.market.atr_series import calculate_atr_series

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


@traced(
    "compute_full_indicator_series",
    attrs={"component": "market", "subsystem": "indicator_engine"},
)
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
            "atre_promoted", "pass_count", "action_override", "manual_review",
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
        if len(close) > n and pd.notna(close.iloc[0]) and close.iloc[0] != 0 and pd.notna(close.iloc[n]) and close.iloc[n] != 0:
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
            if ref and pd.notna(close.iloc[0]) and close.iloc[0] != 0:
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
        rsi[(avg_gain == 0) & (avg_loss == 0)] = 50.0
        rsi[(avg_gain > 0) & (avg_loss == 0)] = 100.0
        return rsi
    except Exception as e:
        logger.warning("RSI(%d) calculation failed: %s", period, e)
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



# ---------------------------------------------------------------------------
# Stage classification — canonical implementations live in stage_classifier.py.
# Re-exported here for backward compatibility. Many call sites still import these
# names from indicator_engine; see backend/services/market/__init__.py for the
# preferred package-level re-export path once imports are migrated.
# ---------------------------------------------------------------------------
from backend.services.market.stage_classifier import (  # noqa: E402, F401
    weekly_from_daily,
    classify_stage_for_timeframe,
    classify_stage_scalar,
    classify_stage_full,
    classify_stage_series,
    StageResult,
    compute_weinstein_stage_from_daily,
    compute_weinstein_stage_series_from_daily,
)


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
    last_buy = 0
    last_sell = 0
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
        last_buy = min(buy_setup, 9)
        last_sell = min(sell_setup, 9)
        if buy_setup >= 9:
            buy_setup = 0
        if sell_setup >= 9:
            sell_setup = 0
    return {
        "td_buy_setup": last_buy if last_buy > 0 else None,
        "td_sell_setup": last_sell if last_sell > 0 else None,
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

    # determine filled status scanning forward in time (toward newer bars)
    def count_unfilled(gaps, direction: str) -> int:
        count = 0
        for top, bottom, start in gaps:
            filled = False
            for j in range(start - 1, -1, -1):
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


def detect_volume_events(ohlcv: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """Classify each bar for climax volume and dry-up (liquidity) conditions.

    Rules (conservative; tune under Stage_Analysis / Oliver Kell methodology):
    - *climax*: volume >= 1.5 * lookback average volume **and**
      |close - open| / ATR(20) >= 1.5 (wide-bodied bar vs volatility).
    - *dry_up*: volume <= 0.5 * lookback average volume.
    If both could apply, *climax* wins.

    Args:
        ohlcv: DataFrame, **oldest first**, must include Open, High, Low, Close, Volume.
        lookback: Rolling window for volume average (and ATR period).

    Returns:
        DataFrame indexed like ``ohlcv`` with a single column ``volume_event`` whose
        values are ``"climax"``, ``"dry_up"``, or ``None`` (Python ``None``, not NaN).
    """
    empty_idx = ohlcv.index if ohlcv is not None and len(ohlcv.index) else pd.Index([])
    out = pd.DataFrame(index=empty_idx)
    out["volume_event"] = None
    if ohlcv is None or ohlcv.empty:
        return out
    need = {"Open", "Close", "Volume"}
    if not need.issubset(set(ohlcv.columns)):
        return out
    if not set(["High", "Low"]).issubset(set(ohlcv.columns)):
        return out

    vol = pd.to_numeric(ohlcv["Volume"], errors="coerce")
    o = pd.to_numeric(ohlcv["Open"], errors="coerce")
    c = pd.to_numeric(ohlcv["Close"], errors="coerce")
    vol_avg = vol.rolling(lookback, min_periods=lookback).mean()
    atr = calculate_atr_series(ohlcv, lookback)
    body = (c - o).abs()
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = body / atr.replace(0, np.nan)

    climax = (
        (vol >= 1.5 * vol_avg)
        & (rel >= 1.5)
        & vol_avg.notna()
        & atr.notna()
    )
    dry = (vol <= 0.5 * vol_avg) & vol_avg.notna() & (vol > 0)

    ev = np.full(len(ohlcv), None, dtype=object)
    for i in range(len(ohlcv.index)):
        if bool(climax.iloc[i]):
            ev[i] = "climax"
        elif bool(dry.iloc[i]):
            ev[i] = "dry_up"
    out = pd.DataFrame({"volume_event": ev}, index=ohlcv.index)
    return out


def _norm_stage(v: Any) -> Optional[str]:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip().upper()
    return s or None


def detect_kell_patterns(ohlcv: pd.DataFrame, stage_series: pd.Series) -> pd.DataFrame:
    """Detect Oliver Kell style pattern labels (chart signal layer, not a trade entry system).

    Uses explicit conservative rules inspired by Stage Analysis and common Kell lexicon
    (EBC = exhaustion + reclaim, KRC = kicker / gap continuation, PPB = pullback to
    support in a Stage 2 base).  # TODO(methodology): calibrate to Stage_Analysis.docx
    and live cohort feedback; thresholds are intentionally strict to avoid over-tagging.

    Args:
        ohlcv: Daily bars, **oldest first**, with Open, High, Low, Close, Volume.
        stage_series: One row per bar, same index as ``ohlcv`` (e.g. ``stage_label`` from
            snapshot history). Missing values are allowed.

    Returns:
        DataFrame with columns ``pattern`` (``"EBC"``, ``"KRC"``, ``"PPB"`` or ``None``)
        and ``confidence`` (0.0-1.0, ``NaN`` when no pattern).
    """
    n = len(ohlcv.index) if ohlcv is not None else 0
    pat: list[Optional[str]] = [None] * n
    conf = np.full(n, np.nan, dtype=float)
    if ohlcv is None or ohlcv.empty:
        return pd.DataFrame({"pattern": pat, "confidence": conf}, index=ohlcv.index if ohlcv is not None else [])

    need = {"Open", "High", "Low", "Close", "Volume"}
    if not need.issubset(set(ohlcv.columns)):
        return pd.DataFrame({"pattern": pat, "confidence": conf}, index=ohlcv.index)

    st = (
        stage_series.reindex(ohlcv.index)
        if stage_series is not None and len(stage_series) > 0
        else pd.Series(index=ohlcv.index, dtype=object)
    )

    c = pd.to_numeric(ohlcv["Close"], errors="coerce")
    o = pd.to_numeric(ohlcv["Open"], errors="coerce")
    h = pd.to_numeric(ohlcv["High"], errors="coerce")
    l = pd.to_numeric(ohlcv["Low"], errors="coerce")
    v = pd.to_numeric(ohlcv["Volume"], errors="coerce")
    vol_avg = v.rolling(20, min_periods=20).mean()
    atr = calculate_atr_series(ohlcv, 20)
    body = (c - o).abs()
    with np.errstate(divide="ignore", invalid="ignore"):
        rel_body = body / atr.replace(0, np.nan)
    sma20 = c.rolling(20, min_periods=20).mean()

    h_prev = h.shift(1)

    for i in range(n):
        if i < 1:
            continue
        if pat[i] is not None:
            continue
        st_i = _norm_stage(st.iloc[i] if i < len(st) else None)
        st_prev = _norm_stage(st.iloc[i - 1] if (i - 1) < len(st) else None)
        if not (np.isfinite(c.iloc[i]) and np.isfinite(o.iloc[i]) and np.isfinite(h_prev.iloc[i])):
            continue

        # KRC before PPB: gap-up + volume continuation can also touch a MA band on the same bar.
        if (
            float(o.iloc[i]) > float(h_prev.iloc[i])
            and c.iloc[i] > o.iloc[i]
            and v.iloc[i] >= 1.2 * vol_avg.iloc[i]
            and np.isfinite(vol_avg.iloc[i])
            and st_i in ("2A", "2B", "2C", "1A", "1B")
        ):
            cscore = 0.65
            if st_i in ("2A", "2B", "2C"):
                cscore += 0.1
            if v.iloc[i] >= 1.5 * vol_avg.iloc[i]:
                cscore += 0.1
            pat[i] = "KRC"
            conf[i] = min(0.92, cscore)
            continue

        # PPB: Stage 2 early, pullback to ~SMA20, bullish close.  # TODO(methodology)
        st_ok_ppb = st_i in ("2A", "2B") or st_i in ("2C",)  # 2C allowed but lower confidence
        if st_ok_ppb and np.isfinite(sma20.iloc[i]) and i >= 1:
            sm = float(sma20.iloc[i])
            if sm > 0 and np.isfinite(l.iloc[i]) and l.iloc[i] <= sm * 1.01 and l.iloc[i] >= sm * 0.99:
                if c.iloc[i] > o.iloc[i] and c.iloc[i] >= c.iloc[i - 1]:
                    base = 0.55 if st_i in ("2A", "2B") else 0.5
                    pat[i] = "PPB"
                    conf[i] = min(0.85, base + 0.1 * min(1.0, rel_body.iloc[i] if np.isfinite(rel_body.iloc[i]) else 0))
                    continue

        # EBC: wide bearish climax bar, then reclaim the midpoint within 1-2 sessions.
        if i + 1 >= n:
            continue
        selling_climax = (
            c.iloc[i] < o.iloc[i]
            and rel_body.iloc[i] >= 1.5
            and v.iloc[i] >= 1.5 * vol_avg.iloc[i]
            and np.isfinite(vol_avg.iloc[i])
        )
        if selling_climax:
            mid = float((h.iloc[i] + l.iloc[i]) / 2.0)
            for j in (i + 1, i + 2):
                if j >= n:
                    break
                if c.iloc[j] > mid and c.iloc[j] > o.iloc[j]:
                    pat[j] = "EBC"
                    conf[j] = min(0.88, 0.62 + 0.1 * (1.0 if st_prev in ("3A", "3B", "4A", "4B", "4C") else 0.0))
                    break

    return pd.DataFrame({"pattern": pat, "confidence": conf}, index=ohlcv.index)


def compute_rs_mansfield(
    symbol_close: pd.Series,
    benchmark_close: pd.Series,
    ma_window: int = 252,
) -> pd.Series:
    """Mansfield-style relative strength versus a benchmark (percent vs RS moving average).

    For each aligned session:
        RS = (symbol_close / benchmark_close) * 100
        RS_ma = rolling mean of RS over ``ma_window`` sessions
        Mansfield% = (RS / RS_ma - 1) * 100

    Args:
        symbol_close: Session closes (e.g. daily), indexed by time.
        benchmark_close: Benchmark closes on the same index (caller should
            ``reindex(..., method='ffill')`` to the symbol's calendar).
        ma_window: Rolling window for the RS baseline. Default **252** matches
            :mod:`backend.services.market.stage_classifier` / ``MarketSnapshot``
            (approximately 52 trading weeks).

    Returns:
        Mansfield percentage series aligned to ``symbol_close``; NaN where
        inputs are missing or warmup is insufficient.
    """
    if symbol_close is None or benchmark_close is None:
        return pd.Series(dtype=float)
    sym = pd.to_numeric(symbol_close, errors="coerce")
    bench = pd.to_numeric(benchmark_close, errors="coerce")
    if sym.empty:
        return pd.Series(dtype=float)
    rs = (sym / bench.replace(0, np.nan)) * 100.0
    rs_ma = rs.rolling(ma_window, min_periods=ma_window).mean()
    return ((rs / rs_ma - 1.0) * 100.0).replace([np.inf, -np.inf], np.nan)
