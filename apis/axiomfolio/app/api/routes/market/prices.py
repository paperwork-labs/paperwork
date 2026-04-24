"""
Price Routes
============

Endpoints for current prices, historical data, and indicator series.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.market_data import MarketSnapshot, MarketSnapshotHistory, PriceData
from app.services.billing.entitlement_service import EntitlementService
from app.services.market.indicator_engine import (
    compute_rs_mansfield,
    detect_kell_patterns,
    detect_volume_events,
)
from app.services.market.market_data_service import provider_router, quote
from app.api.dependencies import get_market_data_viewer, require_feature
from app.api.schemas.market import CurrentPriceResponse, PriceHistoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prices", tags=["prices"])


def _history_data_source(raw: Optional[str]) -> str:
    """Normalize internal history layer/provider tags for API consumers."""
    if raw == "redis_cache":
        return "redis_cache"
    if raw == "db":
        return "db_fallback"
    if raw == "fmp":
        return "provider_fmp"
    if raw == "yfinance":
        return "provider_yfinance"
    if raw == "twelvedata":
        return "provider_twelvedata"
    if raw:
        return f"provider_{raw}"
    return "unknown"


@router.get(
    "/{symbol}",
    response_model=CurrentPriceResponse,
    response_model_exclude_unset=True,
)
async def get_current_price(
    symbol: str,
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Get current price for a symbol."""
    try:
        sym = symbol.strip().upper()
        fresh = await quote.get_current_price_with_freshness(sym)
        if fresh is None:
            return {
                "symbol": sym,
                "current_price": None,
                "price": None,
                "timestamp": datetime.now().isoformat(),
            }
        p = fresh["price"]
        return {
            "symbol": sym,
            "current_price": p,
            "price": p,
            "source": fresh["source"],
            "as_of": fresh["as_of"],
            "age_seconds": fresh["age_seconds"],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.exception("get_current_price failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{symbol}/history", response_model=PriceHistoryResponse)
async def get_history(
    symbol: str,
    period: str = Query("1y", description="e.g., 1mo, 3mo, 6mo, 1y, 2y, 5y"),
    interval: str = Query("1d", description="1d, 4h, 1h, 5m"),
    _viewer: User = Depends(get_market_data_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Daily/intraday OHLCV series for the symbol."""
    try:
        df, raw_src = await provider_router.get_historical_data(
            symbol=symbol.upper(),
            period=period,
            interval=interval,
            max_bars=None,
            db=db,
            return_provider=True,
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
        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "data_source": _history_data_source(raw_src),
            "bars": out,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_history failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Internal server error")


def _close_series_oldest_first(df: Optional[pd.DataFrame]) -> pd.Series:
    """Extract Close as a float series with normalized daily index (oldest first)."""
    if df is None or df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    dfo = df.sort_index(ascending=True)
    s = pd.to_numeric(dfo["Close"], errors="coerce")
    idx = pd.to_datetime(s.index)
    if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    s.index = idx.normalize()
    return s


@router.get("/{symbol}/rs-mansfield")
async def get_rs_mansfield_series(
    symbol: str,
    benchmark: str = Query("SPY", min_length=1, max_length=12),
    period: str = Query("1y"),
    ma_window: int = Query(252, ge=10, le=400),
    _viewer: User = Depends(require_feature("chart.rs_ribbon")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Daily RS Mansfield % vs ``benchmark`` (live OHLCV), Pro tier or higher."""
    sym_u = symbol.strip().upper()
    bm_u = benchmark.strip().upper()
    try:
        tup_sym = await provider_router.get_historical_data(
            symbol=sym_u,
            period=period,
            interval="1d",
            max_bars=None,
            db=db,
            return_provider=True,
        )
        tup_bm = await provider_router.get_historical_data(
            symbol=bm_u,
            period=period,
            interval="1d",
            max_bars=None,
            db=db,
            return_provider=True,
        )
        df_sym = tup_sym[0] if isinstance(tup_sym, tuple) else tup_sym
        df_bm = tup_bm[0] if isinstance(tup_bm, tuple) else tup_bm
        if df_sym is None or df_sym.empty:
            raise HTTPException(status_code=404, detail=f"No historical data for {sym_u}")
        if df_bm is None or df_bm.empty:
            raise HTTPException(status_code=404, detail=f"No historical data for benchmark {bm_u}")

        sym_close = _close_series_oldest_first(df_sym)
        bench_close = _close_series_oldest_first(df_bm)
        bench_aligned = bench_close.reindex(sym_close.index, method="ffill")
        series = compute_rs_mansfield(sym_close, bench_aligned, ma_window)

        data: List[Dict[str, Any]] = []
        for idx, val in series.items():
            if val is None or (isinstance(val, float) and (val != val or not np.isfinite(val))):
                continue
            data.append(
                {
                    "date": pd.Timestamp(idx).strftime("%Y-%m-%d"),
                    "value": float(val),
                }
            )

        return {
            "symbol": sym_u,
            "benchmark": bm_u,
            "ma_window": ma_window,
            "data": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_rs_mansfield_series failed for %s vs %s: %s", sym_u, bm_u, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{symbol}/indicators")
async def get_indicator_series(
    symbol: str,
    indicators: str | None = None,
    period: str = "1y",
    limit: int = Query(5000, ge=1, le=5000, description="Max history rows returned"),
    _viewer: User = Depends(get_market_data_viewer),
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
                from app.tasks.market.history import snapshot_for_symbol

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

    out: Dict[str, Any] = {
        "symbol": sym,
        "rows": len(dates),
        "backfill_requested": backfill_requested,
        "price_data_pending": price_data_pending,
        "series": {"dates": dates, **series},
    }

    # Optional chart annotations (Pro; chart.trade_rationale is Pro+ and enforced client-side
    # for full Kell hover copy). Omitted when the caller is below chart.trade_annotations
    # so we never leak gated markers to unauthenticated or Free users.
    ent_dec = EntitlementService.check(db, _viewer, "chart.trade_annotations")
    if not ent_dec.allowed:
        return out

    p_rows = (
        db.query(PriceData)
        .filter(
            PriceData.symbol == sym,
            PriceData.interval == "1d",
            PriceData.date >= start_date,
        )
        .order_by(PriceData.date.asc())
        .all()
    )
    if len(p_rows) < 25:
        out["volume_events"] = []
        out["kell_patterns"] = []
        return out

    def _as_norm_ts(d: datetime) -> pd.Timestamp:
        if d.tzinfo is not None:
            return pd.Timestamp(d).tz_convert("UTC").tz_localize(None).normalize()
        return pd.Timestamp(d).normalize()

    ohlc_records: list[dict[str, Any]] = []
    for pr in p_rows:
        ohlc_records.append(
            {
                "ts": _as_norm_ts(pr.date) if pr.date is not None else None,
                "open": pr.open_price,
                "high": pr.high_price,
                "low": pr.low_price,
                "close": pr.close_price,
                "vol": pr.volume,
            }
        )
    ohlc_records = [r for r in ohlc_records if r["ts"] is not None and r["close"] is not None]
    if not ohlc_records:
        out["volume_events"] = []
        out["kell_patterns"] = []
        return out

    ohlcv = pd.DataFrame(ohlc_records)
    ohlcv = ohlcv.rename(
        columns={
            "ts": "index",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "vol": "Volume",
        }
    )
    ohlcv = ohlcv.set_index("index").sort_index()
    ohlcv["Open"] = pd.to_numeric(ohlcv["Open"], errors="coerce")
    ohlcv["High"] = pd.to_numeric(ohlcv["High"], errors="coerce")
    ohlcv["Low"] = pd.to_numeric(ohlcv["Low"], errors="coerce")
    ohlcv["Close"] = pd.to_numeric(ohlcv["Close"], errors="coerce")
    ohlcv["Volume"] = pd.to_numeric(ohlcv["Volume"], errors="coerce")
    ohlcv = ohlcv.dropna(subset=["Open", "High", "Low", "Close", "Volume"], how="any")

    stage_by_date: dict[date, Any] = {}
    for hrow in rows:
        d = hrow.as_of_date
        if d is None:
            continue
        if isinstance(d, datetime):
            dk = d.astimezone(timezone.utc).date() if d.tzinfo is not None else d.date()
        elif isinstance(d, date):
            dk = d
        else:
            try:
                dk = pd.Timestamp(d).date()
            except Exception:
                continue
        sl = getattr(hrow, "stage_label", None)
        if sl is not None and str(sl).strip():
            stage_by_date[dk] = sl

    def _dkey_for_ts(ts: pd.Timestamp) -> date:
        return ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()

    st_vals: list[Optional[str]] = []
    for t in ohlcv.index:
        st_vals.append(stage_by_date.get(_dkey_for_ts(t), None))
    stage_series = pd.Series(st_vals, index=ohlcv.index, dtype=object)

    try:
        ve_df = detect_volume_events(ohlcv, lookback=20)
        kp_df = detect_kell_patterns(ohlcv, stage_series)
    except Exception as e:
        logger.warning("chart annotation detection failed for %s: %s", sym, e)
        out["volume_events"] = []
        out["kell_patterns"] = []
        return out

    volume_events: List[Dict[str, str]] = []
    for ts, r in ve_df.iterrows():
        ev = r.get("volume_event")
        if ev in ("climax", "dry_up"):
            volume_events.append(
                {"date": pd.Timestamp(ts).strftime("%Y-%m-%d"), "type": str(ev)}
            )

    kell_patterns: List[Dict[str, Any]] = []
    for ts, r in kp_df.iterrows():
        pat = r.get("pattern")
        cval = r.get("confidence")
        if pat in ("EBC", "KRC", "PPB") and cval is not None and np.isfinite(
            float(cval)
        ):
            kell_patterns.append(
                {
                    "date": pd.Timestamp(ts).strftime("%Y-%m-%d"),
                    "pattern": str(pat),
                    "confidence": float(cval),
                }
            )

    out["volume_events"] = volume_events
    out["kell_patterns"] = kell_patterns
    return out
