"""medallion: silver"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import math
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.services.silver.math.dataframe_utils import price_data_rows_to_dataframe

if TYPE_CHECKING:
    from app.services.silver.market.provider_router import ProviderRouter

logger = logging.getLogger(__name__)


class PriceBarWriter:
    """Bar persistence, backfill, and DB history reading."""

    def __init__(self) -> None:
        pass

    def persist_price_bars(
        self,
        db: Session,
        symbol: str,
        df: pd.DataFrame,
        *,
        interval: str = "1d",
        data_source: str = "provider",
        is_adjusted: bool = True,
        is_synthetic_ohlc: bool = False,
        delta_after: Optional[datetime] = None,
        auto_commit: bool = True,
    ) -> int:
        """Persist OHLCV bars into `price_data` with ON CONFLICT DO UPDATE.

        - Assumes df index are timestamps (newest->first or ascending; both ok)
        - Coalesces missing O/H/L/Volume to Close/0 to avoid NULLs
        - If delta_after is provided, only insert rows with ts > delta_after
        - Returns number of attempted inserts (not necessarily rows changed)
        """
        if df is None or df.empty:
            return 0
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from app.models import PriceData
        except Exception as exc:
            raise RuntimeError("PostgreSQL dialect or models unavailable") from exc

        try:
            df_iter = df.sort_index(ascending=True).iterrows()
        except Exception as e:
            logger.warning(
                "persist_price_bars sort_index failed for %s, using raw iterrows: %s",
                symbol,
                e,
            )
            df_iter = df.iterrows()

        rows: list[dict[str, Any]] = []
        prev_close: Optional[float] = None
        for ts, row in df_iter:
            try:
                if isinstance(ts, pd.Timestamp):
                    pd_date = ts.tz_convert("UTC").to_pydatetime().replace(tzinfo=None) if ts.tzinfo else ts.to_pydatetime()
                elif hasattr(ts, "timestamp"):
                    pd_date = datetime.utcfromtimestamp(ts.timestamp())
                else:
                    pd_date = ts
            except Exception as e:
                logger.debug(
                    "persist_price_bars row timestamp normalize failed for %s: %s",
                    symbol,
                    e,
                )
                pd_date = ts
            if delta_after and pd_date <= delta_after:
                continue
            raw_close = row.get("Close")
            if raw_close is None or (isinstance(raw_close, float) and (math.isnan(raw_close) or math.isinf(raw_close))):
                logger.debug("persist_price_bars: SKIPPING %s %s — Close is NaN/None/inf", symbol, pd_date)
                continue
            close_val = float(raw_close)
            open_val = (
                float(row.get("Open"))
                if "Open" in row and row.get("Open") is not None
                   and not (isinstance(row.get("Open"), float) and math.isnan(row.get("Open")))
                else close_val
            )
            high_val = (
                float(row.get("High"))
                if "High" in row and row.get("High") is not None
                   and not (isinstance(row.get("High"), float) and math.isnan(row.get("High")))
                else close_val
            )
            low_val = (
                float(row.get("Low"))
                if "Low" in row and row.get("Low") is not None
                   and not (isinstance(row.get("Low"), float) and math.isnan(row.get("Low")))
                else close_val
            )
            vol_val = int(row.get("Volume") or 0) if "Volume" in row else 0

            if close_val <= 0:
                logger.warning("persist_price_bars: SKIPPING %s %s close=%.4f (<=0)", symbol, pd_date, close_val)
                continue
            elif interval == "1d" and prev_close and prev_close > 0:
                pct_chg = abs(close_val - prev_close) / prev_close
                if pct_chg > 0.50:
                    logger.warning(
                        "persist_price_bars: %s %s %.1f%% daily move (%.2f->%.2f)",
                        symbol, pd_date, pct_chg * 100, prev_close, close_val,
                    )
            if high_val < low_val:
                logger.warning("persist_price_bars: FIXING %s %s high=%.4f < low=%.4f — swapping",
                               symbol, pd_date, high_val, low_val)
                high_val, low_val = low_val, high_val
            prev_close = close_val

            rows.append(
                {
                    "symbol": symbol,
                    "date": pd_date,
                    "open_price": open_val,
                    "high_price": high_val,
                    "low_price": low_val,
                    "close_price": close_val,
                    "adjusted_close": close_val,
                    "volume": vol_val,
                    "interval": interval,
                    "data_source": data_source,
                    "is_adjusted": is_adjusted,
                    "is_synthetic_ohlc": is_synthetic_ohlc,
                }
            )

        if len(rows) >= 3 and interval == "1d":
            consecutive_same = 1
            for i in range(1, len(rows)):
                if rows[i]["close_price"] == rows[i - 1]["close_price"]:
                    consecutive_same += 1
                    if consecutive_same >= 3:
                        logger.warning(
                            "persist_price_bars: %s has %d consecutive identical closes at %.4f ending %s",
                            symbol, consecutive_same, rows[i]["close_price"], rows[i]["date"],
                        )
                else:
                    consecutive_same = 1

        if not rows:
            return 0

        stmt = pg_insert(PriceData).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_symbol_date_interval",
            set_={
                "open_price": stmt.excluded.open_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "close_price": stmt.excluded.close_price,
                "adjusted_close": stmt.excluded.adjusted_close,
                "volume": stmt.excluded.volume,
                "data_source": data_source,
                "is_synthetic_ohlc": is_synthetic_ohlc,
            },
            where=or_(
                PriceData.data_source.is_(None),
                PriceData.data_source.in_(["provider", "fmp_td_yf"]),
            ),
        )
        db.execute(stmt)
        if auto_commit:
            db.commit()
        return len(rows)

    async def backfill_daily_bars(
        self,
        db: Session,
        symbol: str,
        *,
        provider: "ProviderRouter",
        lookback_period: str = "1y",
        max_bars: int = 270,
    ) -> Dict[str, Any]:
        """Delta backfill last ~270 daily bars for a single symbol using provider policy."""
        last_date: Optional[datetime] = None
        try:
            from app.models import PriceData
            last_date = (
                db.query(PriceData.date)
                .filter(PriceData.symbol == symbol.upper(), PriceData.interval == "1d")
                .order_by(PriceData.date.desc())
                .limit(1)
                .scalar()
            )
        except Exception as e:
            logger.warning(
                "backfill_daily_bars last_date query failed for %s: %s", symbol, e
            )
            last_date = None
        df, provider_used = await provider.get_historical_data(
            symbol=symbol.upper(),
            period=lookback_period,
            interval="1d",
            max_bars=max_bars,
            return_provider=True,
        )
        if df is None or df.empty:
            return {
                "status": "empty",
                "symbol": symbol.upper(),
                "inserted": 0,
                "provider": provider_used,
            }
        inserted = self.persist_price_bars(
            db,
            symbol.upper(),
            df,
            interval="1d",
            data_source=provider_used or "unknown",
            is_adjusted=True,
            delta_after=last_date,
        )
        return {
            "status": "ok",
            "symbol": symbol.upper(),
            "inserted": inserted,
            "provider": provider_used,
        }

    async def backfill_intraday_5m(
        self,
        db: Session,
        symbol: str,
        *,
        provider: "ProviderRouter",
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """Delta backfill last N days of 5m bars for a single symbol using provider policy."""
        from app.models import PriceData
        sym = symbol.upper()
        last_ts: Optional[datetime] = (
            db.query(PriceData.date)
            .filter(PriceData.symbol == sym, PriceData.interval == "5m")
            .order_by(PriceData.date.desc())
            .limit(1)
            .scalar()
        )
        period = f"{max(1, int(lookback_days))}d"
        df, provider_used = await provider.get_historical_data(
            symbol=sym,
            period=period,
            interval="5m",
            max_bars=None,
            return_provider=True,
        )
        if df is None or df.empty:
            return {"status": "empty", "symbol": sym, "inserted": 0, "provider": provider_used}
        inserted = self.persist_price_bars(
            db,
            sym,
            df,
            interval="5m",
            data_source=provider_used or "unknown",
            is_adjusted=True,
            delta_after=last_ts,
        )
        return {"status": "ok", "symbol": sym, "inserted": inserted, "provider": provider_used}

    def get_db_history(
        self,
        db: Session,
        symbol: str,
        *,
        interval: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """Read OHLCV from price_data (ascending by time) for API consumers."""
        from app.models import PriceData
        q = (
            db.query(
                PriceData.date,
                PriceData.open_price,
                PriceData.high_price,
                PriceData.low_price,
                PriceData.close_price,
                PriceData.volume,
            )
            .filter(PriceData.symbol == symbol.upper(), PriceData.interval == interval)
        )
        if start:
            q = q.filter(PriceData.date >= start)
        if end:
            q = q.filter(PriceData.date <= end)
        q = q.order_by(PriceData.date.asc())
        if limit:
            q = q.limit(limit)
        rows = q.all()
        return price_data_rows_to_dataframe(rows, ascending=True)
