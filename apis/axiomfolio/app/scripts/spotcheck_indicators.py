"""Spot-check our indicator calculations against FMP's technical indicators.

Usage:
    python -m app.scripts.spotcheck_indicators --symbol AAPL --indicator rsi
    python -m app.scripts.spotcheck_indicators --symbol SPY --indicator sma --period 50

Compares our indicator_engine output against FMP /v3/technical_indicator/{interval}/{symbol}
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

import pandas as pd
import requests

from app.config import settings
from app.database import SessionLocal
from app.models.market_data import PriceData
from app.services.market.indicator_engine import compute_full_indicator_series

logger = logging.getLogger(__name__)

# Periods emitted by compute_full_indicator_series (indicator_engine.py)
_OUR_RSI_PERIOD = 14
_OUR_SMA_PERIODS = frozenset([5, 8, 10, 14, 21, 50, 100, 150, 200])
_OUR_EMA_PERIODS = frozenset([8, 10, 21, 200])


def fetch_fmp_indicator(symbol: str, indicator: str, period: int = 14) -> pd.DataFrame:
    """Fetch FMP technical indicator for comparison."""
    url = f"https://financialmodelingprep.com/api/v3/technical_indicator/daily/{symbol}"
    params = {
        "type": indicator,
        "period": period,
        "apikey": settings.FMP_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _our_column(indicator: str, period: int) -> Optional[str]:
    if indicator == "rsi":
        if period != _OUR_RSI_PERIOD:
            logger.warning(
                "Our engine uses RSI period %s; comparing to FMP period=%s",
                _OUR_RSI_PERIOD,
                period,
            )
        return "rsi"
    if indicator == "sma":
        if period not in _OUR_SMA_PERIODS:
            logger.error(
                "No sma_%s in our engine; allowed: %s",
                period,
                sorted(_OUR_SMA_PERIODS),
            )
            return None
        return f"sma_{period}"
    if indicator == "ema":
        if period not in _OUR_EMA_PERIODS:
            logger.error(
                "No ema_%s in our engine; allowed: %s",
                period,
                sorted(_OUR_EMA_PERIODS),
            )
            return None
        return f"ema_{period}"
    return None


def _fmp_value(row: pd.Series, indicator: str) -> Optional[float]:
    if indicator in row.index and pd.notna(row[indicator]):
        return float(row[indicator])
    if "technicalIndicator" in row.index and pd.notna(row["technicalIndicator"]):
        return float(row["technicalIndicator"])
    return None


def compare_indicators(
    symbol: str, indicator: str, period: int = 14, lookback_days: int = 30
) -> None:
    """Compare our engine vs FMP for the last N days."""
    if not settings.FMP_API_KEY:
        print("FMP_API_KEY is not set; cannot call FMP.", file=sys.stderr)
        return

    our_col = _our_column(indicator, period)
    if our_col is None:
        return

    db = SessionLocal()
    try:
        bars = (
            db.query(PriceData)
            .filter(PriceData.symbol == symbol.upper(), PriceData.interval == "1d")
            .order_by(PriceData.date.asc())
            .all()
        )

        if not bars:
            print(f"No price data for {symbol}")
            return

        index_list: list[pd.Timestamp] = []
        opens: list[float] = []
        highs: list[float] = []
        lows: list[float] = []
        closes: list[float] = []
        volumes: list[int] = []
        for b in bars:
            d = b.date
            if getattr(d, "tzinfo", None) is not None:
                d = d.replace(tzinfo=None)
            index_list.append(pd.Timestamp(d))
            c = float(b.close_price)
            o = float(b.open_price) if b.open_price is not None else c
            h = float(b.high_price) if b.high_price is not None else c
            low_v = float(b.low_price) if b.low_price is not None else c
            opens.append(o)
            highs.append(h)
            lows.append(low_v)
            closes.append(c)
            volumes.append(int(b.volume or 0))

        ohlcv = pd.DataFrame(
            {
                "Open": opens,
                "High": highs,
                "Low": lows,
                "Close": closes,
                "Volume": volumes,
            },
            index=pd.DatetimeIndex(index_list),
        )

        result = compute_full_indicator_series(ohlcv, spy_df=None)
        if our_col not in result.columns:
            print(f"Column {our_col!r} missing from indicator output.")
            return

        our_values = result.tail(lookback_days).copy()
        our_values["_d"] = pd.DatetimeIndex(our_values.index).normalize().date

        fmp_df = fetch_fmp_indicator(symbol, indicator, period)
        if fmp_df.empty:
            print(f"No FMP data for {symbol} {indicator}")
            return

        fmp_recent = fmp_df.tail(lookback_days)

        print(f"\n{'=' * 60}")
        print(f"Spot Check: {symbol} {indicator.upper()}(period={period})")
        print(f"{'=' * 60}")
        print(f"{'Date':>12}  {'Ours':>10}  {'FMP':>10}  {'Diff':>10}  {'Diff%':>8}")
        print(f"{'-' * 60}")

        for _, fmp_row in fmp_recent.iterrows():
            raw = fmp_row["date"]
            fmp_date = raw.date() if hasattr(raw, "date") else pd.Timestamp(raw).date()
            our_match = our_values[our_values["_d"] == fmp_date]
            if our_match.empty:
                continue

            our_val = our_match[our_col].iloc[0]
            fmp_val = _fmp_value(fmp_row, indicator)
            if fmp_val is None or pd.isna(our_val):
                continue

            our_f = float(our_val)
            diff = our_f - fmp_val
            diff_pct = (diff / fmp_val) * 100 if fmp_val != 0 else float("nan")
            flag = " !!!" if abs(diff_pct) > 5 else ""
            dp = f"{diff_pct:>7.2f}%" if fmp_val != 0 else "   n/a "
            print(
                f"{str(fmp_date):>12}  {our_f:>10.2f}  {fmp_val:>10.2f}  "
                f"{diff:>10.4f}  {dp}{flag}"
            )

        print()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Spot-check indicators vs FMP")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--indicator", default="rsi", choices=["rsi", "sma", "ema"])
    parser.add_argument("--period", type=int, default=14)
    parser.add_argument("--lookback", type=int, default=30)
    args = parser.parse_args()

    compare_indicators(args.symbol, args.indicator, args.period, args.lookback)
