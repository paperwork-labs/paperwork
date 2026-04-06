"""
Price Routes
============

Endpoints for current prices, historical data, and indicator series.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory, PriceData
from backend.services.market.market_data_service import MarketDataService
from backend.api.dependencies import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{symbol}")
async def get_current_price(
    symbol: str,
    user: User | None = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get current price for a symbol."""
    try:
        market_service = MarketDataService()
        price = await market_service.get_current_price(symbol)
        return {
            "symbol": symbol,
            "current_price": price,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Price error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/history")
async def get_history(
    symbol: str,
    period: str = Query("1y", description="e.g., 1mo, 3mo, 6mo, 1y, 2y, 5y"),
    interval: str = Query("1d", description="1d, 4h, 1h, 5m"),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Daily/intraday OHLCV series for the symbol."""
    try:
        svc = MarketDataService()
        df = await svc.get_historical_data(
            symbol=symbol.upper(), period=period, interval=interval, max_bars=None, db=db
        )
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="No historical data")

        try:
            df_out = df.iloc[::-1].copy()
        except Exception:
            df_out = df

        cols = {c.lower(): c for c in df_out.columns}

        def pick(col_name: str) -> str:
            for key in cols:
                if key.startswith(col_name):
                    return cols[key]
            return col_name

        o, h, l, c, v = pick("open"), pick("high"), pick("low"), pick("close"), pick("volume")
        out = []
        for ts, row in df_out.iterrows():
            out.append({
                "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": float(row.get(o, None) or row.get("open_price", 0) or 0),
                "high": float(row.get(h, None) or row.get("high_price", 0) or 0),
                "low": float(row.get(l, None) or row.get("low_price", 0) or 0),
                "close": float(row.get(c, None) or row.get("close_price", 0) or 0),
                "volume": float(row.get(v, 0) or 0),
            })
        return {"symbol": symbol.upper(), "period": period, "interval": interval, "bars": out}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"History error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/indicators")
async def get_indicator_series(
    symbol: str,
    indicators: str | None = None,
    period: str = "1y",
    limit: int = Query(5000, ge=1, le=5000, description="Max history rows returned"),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Read pre-computed indicator series from MarketSnapshotHistory."""
    sym = symbol.strip().upper()
    period_days = {
        "1mo": 35, "3mo": 100, "6mo": 200, "1y": 370,
        "2y": 740, "3y": 1100, "5y": 1850, "max": 36500,
    }
    days = period_days.get(period, 370)
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(MarketSnapshotHistory)
        .filter(
            MarketSnapshotHistory.symbol == sym,
            MarketSnapshotHistory.analysis_type == "technical_snapshot",
            MarketSnapshotHistory.as_of_date >= start_date,
        )
        .order_by(MarketSnapshotHistory.as_of_date.asc())
        .limit(limit)
        .all()
    )

    all_indicator_cols = [
        "current_price", "rsi", "sma_5", "sma_10", "sma_14", "sma_21", "sma_50",
        "sma_100", "sma_150", "sma_200", "ema_8", "ema_10", "ema_21", "ema_200",
        "atr_14", "atr_30", "atrp_14", "atrp_30", "macd", "macd_signal", "macd_histogram",
        "adx", "plus_di", "minus_di", "bollinger_upper", "bollinger_lower", "bollinger_width",
        "high_52w", "low_52w", "stoch_rsi", "volume_avg_20d",
        "range_pos_20d", "range_pos_50d", "range_pos_52w",
        "atrx_sma_21", "atrx_sma_50", "atrx_sma_100", "atrx_sma_150",
        "pct_dist_ema8", "pct_dist_ema21", "pct_dist_ema200",
        "atr_dist_ema8", "atr_dist_ema21", "atr_dist_ema200",
        "ma_bucket", "stage_label", "stage_slope_pct", "stage_dist_pct", "rs_mansfield_pct",
        "td_buy_setup", "td_sell_setup", "td_buy_complete", "td_sell_complete",
        "perf_1d", "perf_3d", "perf_5d", "perf_20d", "perf_60d", "perf_120d", "perf_252d",
    ]

    if indicators:
        requested = [c.strip() for c in indicators.split(",")]
        selected_cols = [c for c in requested if c in all_indicator_cols]
    else:
        selected_cols = all_indicator_cols

    dates: list[str | None] = []
    series: dict[str, list] = {col: [] for col in selected_cols}

    for row in rows:
        d = row.as_of_date
        dates.append(d.strftime("%Y-%m-%d") if d else None)
        for col in selected_cols:
            val = getattr(row, col, None)
            if isinstance(val, float) and val != val:
                val = None
            series[col].append(val)

    expected_per_year = 252
    expected_rows = int(days / 365.25 * expected_per_year) if days < 36500 else len(rows)
    backfill_requested = False
    price_data_pending = False

    if len(rows) < expected_rows * 0.8 and expected_rows > 0:
        bar_count = (
            db.query(PriceData)
            .filter(PriceData.symbol == sym, PriceData.interval == "1d", PriceData.date >= start_date)
            .count()
        )
        if bar_count >= expected_rows * 0.7:
            try:
                from backend.tasks.market.history import snapshot_for_symbol

                snapshot_for_symbol.delay(
                    symbol=sym, start_date=start_date.strftime("%Y-%m-%d")
                )
                backfill_requested = True
            except Exception:
                pass
        else:
            price_data_pending = True

    if dates and rows:
        latest_hist_date = rows[-1].as_of_date
        today = datetime.now(timezone.utc).date()
        if hasattr(latest_hist_date, "date"):
            latest_hist_date = latest_hist_date.date()
        if latest_hist_date < today:
            snapshot = (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == sym, MarketSnapshot.analysis_type == "technical_snapshot")
                .order_by(MarketSnapshot.analysis_timestamp.desc())
                .first()
            )
            if snapshot:
                dates.append(today.strftime("%Y-%m-%d"))
                for col in selected_cols:
                    val = getattr(snapshot, col, None)
                    if isinstance(val, float) and val != val:
                        val = None
                    series[col].append(val)

    return {
        "symbol": sym,
        "rows": len(dates),
        "backfill_requested": backfill_requested,
        "price_data_pending": price_data_pending,
        "series": {"dates": dates, **series},
    }
