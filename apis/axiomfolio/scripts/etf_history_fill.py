#!/usr/bin/env python3
"""Surgical ETF snapshot history fill.

This script fills ONLY the ETFs with gaps in market_snapshot_history,
avoiding the 6+ hour full universe scan.

Usage:
    python scripts/etf_history_fill.py --db-url "postgresql://..."
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import indicator computation from the app
sys.path.insert(0, "/Users/axiomfolio/development/axiomfolio")
from app.services.market.indicator_engine import (
    compute_core_indicators_series,
    compute_weinstein_stage_series_from_daily,
)
from app.services.market.constants import WEINSTEIN_WARMUP_CALENDAR_DAYS


ETF_SYMBOLS = [
    "QQQ", "IWM", "RSP", "VOO", "VTI", "XLRE",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLB", "XLU", "XLP", "XLY", "XLC",
]


def get_missing_dates(session, symbol: str) -> List[datetime]:
    """Get dates where we have OHLCV but no snapshot history."""
    result = session.execute(text("""
        SELECT p.date
        FROM price_data p
        LEFT JOIN market_snapshot_history h 
            ON p.symbol = h.symbol AND p.date = h.as_of_date
        WHERE p.symbol = :sym
            AND p.interval = '1d'
            AND h.id IS NULL
        ORDER BY p.date ASC
    """), {"sym": symbol})
    return [row[0] for row in result.fetchall()]


def get_price_data(session, symbol: str, start_date: datetime) -> pd.DataFrame:
    """Fetch OHLCV for a symbol from start_date onwards."""
    result = session.execute(text("""
        SELECT date, open_price, high_price, low_price, close_price, volume
        FROM price_data
        WHERE symbol = :sym AND interval = '1d' AND date >= :start
        ORDER BY date ASC
    """), {"sym": symbol, "start": start_date})
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "Open", "High", "Low", "Close", "Volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def get_spy_data(session, start_date: datetime) -> pd.DataFrame:
    """Fetch SPY for RS calculations."""
    result = session.execute(text("""
        SELECT date, close_price
        FROM price_data
        WHERE symbol = 'SPY' AND interval = '1d' AND date >= :start
        ORDER BY date ASC
    """), {"start": start_date})
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "Close"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def compute_and_insert(session, symbol: str, missing_dates: List[datetime], dry_run: bool = False):
    """Compute indicators for missing dates and insert into snapshot history."""
    if not missing_dates:
        return 0
    
    # Need warmup period before first missing date
    earliest = min(missing_dates)
    warmup_start = earliest - timedelta(days=WEINSTEIN_WARMUP_CALENDAR_DAYS + 50)
    
    # Fetch price data with warmup
    df = get_price_data(session, symbol, warmup_start)
    if df.empty or len(df) < 200:
        print(f"  {symbol}: Not enough data ({len(df)} bars)")
        return 0
    
    spy_df = get_spy_data(session, warmup_start)
    
    # Compute indicators
    try:
        indicators = compute_core_indicators_series(df)
        stage_info = compute_weinstein_stage_series_from_daily(df)
    except Exception as e:
        print(f"  {symbol}: Indicator computation failed: {e}")
        return 0
    
    # Compute RS if SPY available
    rs_line = None
    if not spy_df.empty and "Close" in df.columns:
        aligned = df["Close"].reindex(spy_df.index, method="ffill")
        spy_aligned = spy_df["Close"].reindex(df.index, method="ffill")
        if len(spy_aligned) > 0:
            rs_line = (df["Close"] / spy_aligned.values) * 100
    
    # Filter to missing dates only
    missing_set = set(pd.to_datetime(d).normalize() for d in missing_dates)
    
    inserted = 0
    for idx in df.index:
        norm_idx = pd.to_datetime(idx).normalize()
        if norm_idx not in missing_set:
            continue
        
        # Build row
        row_data = {
            "symbol": symbol,
            "as_of_date": idx.to_pydatetime(),
            "close": float(df.loc[idx, "Close"]) if "Close" in df.columns else None,
            "volume": int(df.loc[idx, "Volume"]) if "Volume" in df.columns and pd.notna(df.loc[idx, "Volume"]) else None,
            "sma_50": float(indicators.get("sma_50", pd.Series()).get(idx)) if idx in indicators.get("sma_50", pd.Series()).index else None,
            "sma_150": float(indicators.get("sma_150", pd.Series()).get(idx)) if idx in indicators.get("sma_150", pd.Series()).index else None,
            "sma_200": float(indicators.get("sma_200", pd.Series()).get(idx)) if idx in indicators.get("sma_200", pd.Series()).index else None,
            "rsi_14": float(indicators.get("rsi_14", pd.Series()).get(idx)) if idx in indicators.get("rsi_14", pd.Series()).index else None,
            "atr_14": float(indicators.get("atr_14", pd.Series()).get(idx)) if idx in indicators.get("atr_14", pd.Series()).index else None,
            "stage": stage_info.get("stage", pd.Series()).get(idx) if idx in stage_info.get("stage", pd.Series()).index else "UNKNOWN",
            "rs_line": float(rs_line.get(idx)) if rs_line is not None and idx in rs_line.index and pd.notna(rs_line.get(idx)) else None,
            "created_at": datetime.utcnow(),
        }
        
        # Clean None values for numeric fields
        for key in ["sma_50", "sma_150", "sma_200", "rsi_14", "atr_14", "rs_line"]:
            if row_data[key] is not None and (pd.isna(row_data[key]) or np.isinf(row_data[key])):
                row_data[key] = None
        
        if dry_run:
            inserted += 1
            continue
        
        # Insert
        try:
            session.execute(text("""
                INSERT INTO market_snapshot_history 
                    (symbol, as_of_date, close, volume, sma_50, sma_150, sma_200, rsi_14, atr_14, stage, rs_line, created_at)
                VALUES 
                    (:symbol, :as_of_date, :close, :volume, :sma_50, :sma_150, :sma_200, :rsi_14, :atr_14, :stage, :rs_line, :created_at)
                ON CONFLICT (symbol, as_of_date) DO UPDATE SET
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    sma_50 = EXCLUDED.sma_50,
                    sma_150 = EXCLUDED.sma_150,
                    sma_200 = EXCLUDED.sma_200,
                    rsi_14 = EXCLUDED.rsi_14,
                    atr_14 = EXCLUDED.atr_14,
                    stage = EXCLUDED.stage,
                    rs_line = EXCLUDED.rs_line
            """), row_data)
            inserted += 1
        except Exception as e:
            print(f"  {symbol} {idx}: Insert failed: {e}")
    
    if not dry_run:
        session.commit()
    
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Fill ETF snapshot history gaps")
    parser.add_argument("--db-url", required=True, help="PostgreSQL connection URL")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert")
    parser.add_argument("--symbols", help="Comma-separated symbols (default: all ETFs)")
    args = parser.parse_args()
    
    symbols = args.symbols.split(",") if args.symbols else ETF_SYMBOLS
    
    engine = create_engine(args.db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print(f"Processing {len(symbols)} symbols: {', '.join(symbols)}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    total_inserted = 0
    for sym in symbols:
        missing = get_missing_dates(session, sym)
        if not missing:
            print(f"{sym}: No gaps")
            continue
        
        print(f"{sym}: {len(missing)} missing dates ({missing[0].date()} to {missing[-1].date()})")
        inserted = compute_and_insert(session, sym, missing, dry_run=args.dry_run)
        print(f"  -> Inserted {inserted} rows")
        total_inserted += inserted
    
    print()
    print(f"Total: {total_inserted} rows inserted")
    
    session.close()


if __name__ == "__main__":
    main()
