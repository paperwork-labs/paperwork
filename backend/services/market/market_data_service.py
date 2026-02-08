from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import timedelta

import finnhub
import fmpsdk
import pandas as pd
import redis
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy import func, distinct

from backend.config import settings
from backend.database import SessionLocal
from backend.models import MarketSnapshot
from backend.models.market_data import PriceData
from backend.models.index_constituent import IndexConstituent
from backend.services.market.indicator_engine import (
    calculate_performance_windows,
    classify_ma_bucket_from_ma,
    compute_atr_matrix_metrics,
    compute_core_indicators,
    compute_gap_counts,
    compute_td_sequential_counts,
    compute_trendline_counts,
    compute_weinstein_stage_from_daily,
)
from backend.services.market.universe import tracked_symbols_with_source
from backend.services.market.constants import (
    FUNDAMENTAL_FIELDS,
    FUNDAMENTAL_FIELDS_WITH_NAME,
    FUNDAMENTAL_FIELDS_WITH_SUB_INDUSTRY,
)
from backend.services.market.dataframe_utils import price_data_rows_to_dataframe
from backend.services.market.provider_service import MarketDataProviderService
from backend.services.market.snapshot_service import MarketSnapshotService
from backend.services.market.coverage_service import CoverageService
from backend.services.market.coverage_utils import compute_coverage_status

logger = logging.getLogger(__name__)


class APIProvider(Enum):
    FINNHUB = "finnhub"
    TWELVE_DATA = "twelve_data"
    FMP = "fmp"
    YFINANCE = "yfinance"


class MarketDataService:
    """Market data facade with a clean, policy-driven provider strategy.

    Responsibilities:
    - Provider routing (paid vs free) for quotes and historical OHLCV
    - Caching of quotes/series in Redis
    - Building technical snapshots from local DB first (fast path),
      falling back to provider fetch when needed (slow path)
    - Enriching snapshots with chart metrics and fundamentals
    - Persisting snapshots to MarketSnapshot

    Policy:
    - paid: prefer FMP for historical/quotes; yfinance fallback
    - free: FMP (if key) + yfinance + Twelve Data (if key) + finnhub
    """

    def __init__(self) -> None:
        self._redis_client = None
        self.cache_ttl_seconds = int(getattr(settings, "MARKET_DATA_CACHE_TTL", 300))

        # Optional API clients
        self.finnhub_client = (
            finnhub.Client(api_key=settings.FINNHUB_API_KEY)
            if settings.FINNHUB_API_KEY
            else None
        )

        self.twelve_data_client = None
        try:
            from twelvedata import TDClient  # lazy import
            if settings.TWELVE_DATA_API_KEY:
                self.twelve_data_client = TDClient(apikey=settings.TWELVE_DATA_API_KEY)
        except Exception:
            self.twelve_data_client = None

        # Facade services for clearer responsibilities
        self.providers = MarketDataProviderService(self)
        self.snapshots = MarketSnapshotService(self)
        self.coverage = CoverageService(self)

        if settings.FMP_API_KEY:
            logger.info("FMP API configured")

        # Index endpoints for constituents
        self.index_endpoints = {
            "SP500": {"fmp": "sp500_constituent"},
            "NASDAQ100": {"fmp": "nasdaq_constituent"},
            "DOW30": {"fmp": "dowjones_constituent"},
        }

    @property
    def redis_client(self) -> redis.Redis:
        if self._redis_client is None:
            url = getattr(settings, "REDIS_URL", None)
            if not url:
                raise RuntimeError("REDIS_URL is not configured")
            self._redis_client = redis.from_url(url)
        return self._redis_client

    def is_backfill_5m_enabled(self) -> bool:
        """Check admin toggle stored in Redis; default to enabled on errors."""
        try:
            raw = self.redis_client.get("coverage:backfill_5m_enabled")
            if raw is None:
                return True
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode()
            return str(raw).strip().lower() not in ("0", "false", "off", "disabled")
        except Exception:
            # Fail open if Redis unavailable so daily flows aren't blocked
            return True

    def benchmark_health(
        self,
        db: Session,
        benchmark_symbol: str = "SPY",
        required_bars: int | None = None,
        latest_daily_dt: datetime | None = None,
    ) -> Dict[str, Any]:
        """Return benchmark health stats for Stage/RS diagnostics."""
        required = required_bars or max(
            260, int(getattr(settings, "SNAPSHOT_DAILY_BARS_LIMIT", 400))
        )
        latest_dt = (
            db.query(func.max(PriceData.date))
            .filter(PriceData.symbol == benchmark_symbol, PriceData.interval == "1d")
            .scalar()
        )
        count = (
            db.query(func.count(PriceData.id))
            .filter(PriceData.symbol == benchmark_symbol, PriceData.interval == "1d")
            .scalar()
            or 0
        )
        stale = False
        if latest_daily_dt and latest_dt:
            try:
                stale = latest_dt.date() < latest_daily_dt.date()
            except Exception:
                stale = False
        return {
            "symbol": benchmark_symbol,
            "latest_daily_dt": latest_dt,
            "latest_daily_date": latest_dt.date().isoformat() if latest_dt else None,
            "daily_bars": int(count),
            "required_bars": int(required),
            "ok": int(count) >= int(required),
            "stale": bool(stale),
        }

    # ---------------------- Internal helpers ----------------------
    def _visibility_scope(self) -> str:
        return "all_authenticated" if settings.MARKET_DATA_SECTION_PUBLIC else "admin_only"

    def _snapshot_from_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Common snapshot builder used by DB and provider flows."""
        if df is None or df.empty or "Close" not in df.columns:
            return {}

        price = float(df["Close"].iloc[0])
        # df is newest-first with datetime index (when sourced from DB/provider)
        as_of_ts = None
        try:
            as_of_ts = df.index[0].to_pydatetime() if hasattr(df.index[0], "to_pydatetime") else df.index[0]
        except Exception:
            as_of_ts = None
        data_for_ta = df.iloc[::-1].copy()
        indicators = compute_core_indicators(data_for_ta)
        indicators["current_price"] = price
        indicators.update(compute_atr_matrix_metrics(data_for_ta, indicators))
        indicators.update(calculate_performance_windows(df))

        sma_50 = indicators.get("sma_50")
        sma_200 = indicators.get("sma_200")
        ema_8 = indicators.get("ema_8")
        ema_21 = indicators.get("ema_21")
        ema_200 = indicators.get("ema_200")
        atr_14 = indicators.get("atr_14") or indicators.get("atr")
        atr_30 = indicators.get("atr_30")

        def pct_dist(val: Optional[float]) -> Optional[float]:
            return (price / val - 1.0) * 100.0 if (val and price) else None

        def atr_dist(val: Optional[float]) -> Optional[float]:
            return ((price - val) / atr_14) if (val and price and atr_14 and atr_14 != 0) else None

        ma_for_bucket = {
            "price": price,
            "sma_5": indicators.get("sma_5"),
            "sma_8": indicators.get("sma_8"),
            "sma_21": indicators.get("sma_21"),
            "sma_50": indicators.get("sma_50"),
            "sma_100": indicators.get("sma_100"),
            "sma_200": indicators.get("sma_200"),
        }
        bucket = classify_ma_bucket_from_ma(ma_for_bucket).get("bucket")

        def range_pos(window: int) -> Optional[float]:
            try:
                if window <= 0:
                    return None
                if len(data_for_ta) < window:
                    return None
                recent = data_for_ta.tail(window)
                if recent.empty:
                    return None
                hi = float(recent["High"].max())
                lo = float(recent["Low"].min())
                if hi <= lo:
                    return None
                return float((price - lo) / (hi - lo) * 100.0)
            except Exception:
                return None

        def atrx(ma_val: Optional[float]) -> Optional[float]:
            try:
                if ma_val is None or atr_14 is None or atr_14 == 0:
                    return None
                return float((price - float(ma_val)) / float(atr_14))
            except Exception:
                return None

        snapshot: Dict[str, Any] = {
            "current_price": price,
            "as_of_timestamp": as_of_ts.isoformat() if hasattr(as_of_ts, "isoformat") else as_of_ts,
            "rsi": indicators.get("rsi"),
            # Canonical consolidated fields
            "sma_5": indicators.get("sma_5"),
            "sma_10": indicators.get("sma_10"),
            "sma_14": indicators.get("sma_14"),
            "sma_21": indicators.get("sma_21"),
            "sma_50": sma_50,
            "sma_100": indicators.get("sma_100"),
            "sma_150": indicators.get("sma_150"),
            "sma_200": sma_200,
            "atr_14": atr_14,
            "atr_30": atr_30,
            "atrp_14": ((atr_14 / price) * 100.0) if (atr_14 and price) else None,
            "atrp_30": ((atr_30 / price) * 100.0) if (atr_30 and price) else None,
            "atr_distance": ((price - sma_50) / atr_14) if (price and sma_50 and atr_14) else None,
            "range_pos_20d": range_pos(20),
            "range_pos_50d": range_pos(50),
            "range_pos_52w": range_pos(252),
            "atrx_sma_21": atrx(indicators.get("sma_21")),
            "atrx_sma_50": atrx(sma_50),
            "atrx_sma_100": atrx(indicators.get("sma_100")),
            "atrx_sma_150": atrx(indicators.get("sma_150")),

            # Backward-compat (to be dropped after we flip all callers)
            "atr_value": atr_14,
            "atr_percent": ((atr_14 / price) * 100.0) if (atr_14 and price) else None,
            "ema_10": indicators.get("ema_10"),
            "ema_8": ema_8,
            "ema_21": ema_21,
            "ema_200": ema_200,
            "macd": indicators.get("macd"),
            "macd_signal": indicators.get("macd_signal"),
            "perf_1d": indicators.get("perf_1d"),
            "perf_3d": indicators.get("perf_3d"),
            "perf_5d": indicators.get("perf_5d"),
            "perf_20d": indicators.get("perf_20d"),
            "perf_60d": indicators.get("perf_60d"),
            "perf_120d": indicators.get("perf_120d"),
            "perf_252d": indicators.get("perf_252d"),
            "perf_mtd": indicators.get("perf_mtd"),
            "perf_qtd": indicators.get("perf_qtd"),
            "perf_ytd": indicators.get("perf_ytd"),
            "ma_bucket": bucket,
            "pct_dist_ema8": pct_dist(ema_8),
            "pct_dist_ema21": pct_dist(ema_21),
            "pct_dist_ema200": pct_dist(ema_200 or sma_200),
            "atr_dist_ema8": atr_dist(ema_8),
            "atr_dist_ema21": atr_dist(ema_21),
            "atr_dist_ema200": atr_dist(ema_200 or sma_200),
        }

        # Chart metrics (TD Sequential, gaps, trendlines)
        try:
            df_newest = df.head(120).copy()
            if not df_newest.empty:
                td = compute_td_sequential_counts(df_newest["Close"].tolist())
                snapshot.update(td)
                snapshot.update(compute_gap_counts(df_newest))
                snapshot.update(compute_trendline_counts(df_newest.iloc[::-1].copy()))
        except Exception:
            pass
        for key in ("stage_label", "stage_slope_pct", "stage_dist_pct"):
            snapshot.setdefault(key, None)

        return snapshot

    @staticmethod
    def _needs_fundamentals(snapshot: Dict[str, Any]) -> bool:
        return any(snapshot.get(f) is None for f in FUNDAMENTAL_FIELDS)


    # ---------------------- Provider selection ----------------------
    def _provider_priority(self, data_type: str) -> List[APIProvider]:
        """Return provider order based on MARKET_PROVIDER_POLICY and availability.

        data_type: "historical_data" | "real_time_quote" | "company_info"
        paid policy: [FMP, yfinance]
        free policy: [FMP?] + yfinance + [Twelve Data?] + finnhub
        """
        policy = str(getattr(settings, "MARKET_PROVIDER_POLICY", "paid")).lower()
        has_fmp = bool(settings.FMP_API_KEY)
        has_td = bool(settings.TWELVE_DATA_API_KEY)
        if data_type == "historical_data":
            if policy == "paid":
                # Prefer FMP; in paid mode use Twelve Data before yfinance to avoid CF issues
                if has_fmp and has_td:
                    return [APIProvider.FMP, APIProvider.TWELVE_DATA, APIProvider.YFINANCE]
                if has_fmp:
                    return [APIProvider.FMP, APIProvider.YFINANCE]
                if has_td:
                    return [APIProvider.TWELVE_DATA, APIProvider.YFINANCE]
                return [APIProvider.YFINANCE]
            order: List[APIProvider] = []
            if has_fmp:
                order.append(APIProvider.FMP)
            order.append(APIProvider.YFINANCE)
            if has_td:
                order.append(APIProvider.TWELVE_DATA)
            order.append(APIProvider.FINNHUB)
            return order
        if data_type == "real_time_quote":
            return [APIProvider.FMP, APIProvider.YFINANCE]
        if data_type == "company_info":
            return [APIProvider.FMP, APIProvider.YFINANCE]
        return [APIProvider.YFINANCE]

    def _is_provider_available(self, provider: APIProvider) -> bool:
        if provider == APIProvider.FMP:
            return bool(settings.FMP_API_KEY)
        if provider == APIProvider.TWELVE_DATA:
            return self.twelve_data_client is not None
        if provider == APIProvider.FINNHUB:
            return self.finnhub_client is not None
        if provider == APIProvider.YFINANCE:
            return True
        return False

    # ---------------------- Quotes and history ----------------------
    @staticmethod
    def _extract_http_status(exc: Exception) -> Optional[int]:
        """Best-effort extraction of HTTP status code from provider exceptions."""
        try:
            # requests/httpx style
            resp = getattr(exc, "response", None)
            if resp is not None:
                code = getattr(resp, "status_code", None)
                if isinstance(code, int):
                    return code
        except Exception:
            pass
        for attr in ("status_code", "status"):
            try:
                code = getattr(exc, attr, None)
                if isinstance(code, int):
                    return code
            except Exception:
                continue
        # Last resort: parse digits from message
        try:
            msg = str(exc)
            for needle in ("429", "500", "502", "503", "504"):
                if needle in msg:
                    return int(needle)
        except Exception:
            pass
        return None

    async def _call_blocking_with_retries(
        self,
        fn,
        *args,
        attempts: Optional[int] = None,
        max_delay_seconds: Optional[float] = None,
        **kwargs,
    ):
        """Run a blocking provider call in a thread with bounded exponential backoff.

        We use this to make provider calls concurrency-safe (they don't block the event loop),
        and resilient (429/5xx/backoff and continue).
        """
        n = int(attempts or int(getattr(settings, "MARKET_BACKFILL_RETRY_ATTEMPTS", 6)))
        max_delay = float(
            max_delay_seconds
            if max_delay_seconds is not None
            else float(getattr(settings, "MARKET_BACKFILL_RETRY_MAX_DELAY_SECONDS", 60.0))
        )
        last_exc: Optional[Exception] = None
        for i in range(max(1, n)):
            try:
                return await asyncio.to_thread(fn, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001 (provider libs raise wide exceptions)
                last_exc = exc
                status = self._extract_http_status(exc)
                # Backoff for rate limits and transient upstream errors; otherwise keep it short.
                is_rate_limited = status == 429 or "Too Many" in str(exc)
                is_transient = status in (429, 500, 502, 503, 504) or is_rate_limited
                if i >= n - 1:
                    break
                base = 0.8 if is_transient else 0.2
                delay = min(max_delay, base * (2**i))
                # jitter in [0.75x, 1.25x]
                delay = delay * (0.75 + random.random() * 0.5)
                await asyncio.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError("provider call failed without exception")

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol with provider policy and 60s Redis cache."""
        cache_key = f"price:{symbol}"
        cached = self.redis_client.get(cache_key)
        if cached:
            try:
                return float(cached)
            except Exception:
                pass
        for provider in self._provider_priority("real_time_quote"):
            if not self._is_provider_available(provider):
                continue
            try:
                price = None
                if provider == APIProvider.FMP:
                    q = fmpsdk.quote(apikey=settings.FMP_API_KEY, symbol=symbol)
                    price = q and len(q) > 0 and q[0].get("price")
                elif provider == APIProvider.YFINANCE:
                    hist = yf.Ticker(symbol).history(period="1d", interval="1m")
                    price = float(hist["Close"].iloc[-1]) if not hist.empty else None
                if price is not None:
                    self.redis_client.setex(cache_key, 60, str(price))
                    return float(price)
            except Exception:
                continue
        return None

    def get_fundamentals_info(self, symbol: str) -> Dict[str, Any]:
        """Return fundamentals for a symbol using FMP first, then yfinance.

        Returns keys: name, sector, industry, sub_industry, market_cap when available.
        """
        info: Dict[str, Any] = {}
        def to_pct(value: Any) -> Optional[float]:
            try:
                if value is None:
                    return None
                v = float(value)
                if -1.0 <= v <= 1.0:
                    return v * 100.0
                return v
            except Exception:
                return None

        def set_if_missing(key: str, value: Any) -> None:
            if info.get(key) is None and value is not None:
                info[key] = value

        try:
            if settings.FMP_API_KEY:
                prof = fmpsdk.company_profile(apikey=settings.FMP_API_KEY, symbol=symbol)
                if prof and len(prof) > 0 and isinstance(prof[0], dict):
                    d = prof[0]
                    info = {
                        "name": d.get("companyName") or d.get("company_name") or d.get("symbol"),
                        "sector": d.get("sector"),
                        "industry": d.get("industry"),
                        "sub_industry": d.get("subIndustry") or d.get("sub_industry"),
                        "market_cap": d.get("mktCap"),
                    }
                    if d.get("beta") is not None:
                        info["beta"] = d.get("beta")
                try:
                    metrics = fmpsdk.key_metrics_ttm(apikey=settings.FMP_API_KEY, symbol=symbol)
                    if metrics and isinstance(metrics[0], dict):
                        m = metrics[0]
                        set_if_missing("pe_ttm", m.get("peRatioTTM") or m.get("peRatio"))
                        set_if_missing("peg_ttm", m.get("pegRatioTTM") or m.get("pegRatio"))
                        set_if_missing("dividend_yield", to_pct(m.get("dividendYieldTTM") or m.get("dividendYield")))
                        set_if_missing("roe", to_pct(m.get("roeTTM") or m.get("roe")))
                        set_if_missing("beta", m.get("beta"))
                except Exception as exc:
                    logger.warning("Failed to fetch FMP key metrics for %s: %s", symbol, exc)
                try:
                    ratios = fmpsdk.ratios_ttm(apikey=settings.FMP_API_KEY, symbol=symbol)
                    if ratios and isinstance(ratios[0], dict):
                        r = ratios[0]
                        set_if_missing("pe_ttm", r.get("priceEarningsRatioTTM") or r.get("priceEarningsRatio"))
                        set_if_missing("peg_ttm", r.get("pegRatioTTM") or r.get("pegRatio"))
                        set_if_missing("roe", to_pct(r.get("returnOnEquityTTM") or r.get("returnOnEquity")))
                        set_if_missing("dividend_yield", to_pct(r.get("dividendYieldTTM") or r.get("dividendYield")))
                except Exception as exc:
                    logger.warning("Failed to fetch FMP ratios for %s: %s", symbol, exc)
                try:
                    growth = fmpsdk.financial_growth(apikey=settings.FMP_API_KEY, symbol=symbol)
                    if growth and isinstance(growth[0], dict):
                        g = growth[0]
                        set_if_missing("eps_growth_yoy", to_pct(g.get("epsGrowth") or g.get("epsgrowth")))
                        set_if_missing("eps_growth_qoq", to_pct(g.get("epsGrowthQuarterly") or g.get("epsGrowthQoQ")))
                        set_if_missing("revenue_growth_yoy", to_pct(g.get("revenueGrowth") or g.get("revenuegrowth")))
                        set_if_missing("revenue_growth_qoq", to_pct(g.get("revenueGrowthQuarterly") or g.get("revenueGrowthQoQ")))
                except Exception as exc:
                    logger.warning("Failed to fetch or process financial growth from FMP for %s: %s", symbol, exc)
        except Exception as exc:
            logger.warning("Failed to fetch FMP fundamentals for %s: %s", symbol, exc)
        try:
            y = yf.Ticker(symbol).info
            if y:
                if not info:
                    info = {
                        "name": y.get("shortName") or y.get("longName") or y.get("symbol"),
                        "sector": y.get("sector"),
                        "industry": y.get("industry"),
                        "sub_industry": y.get("subIndustry") or y.get("industry") or None,
                        "market_cap": y.get("marketCap"),
                    }
                set_if_missing("beta", y.get("beta"))
                set_if_missing("pe_ttm", y.get("trailingPE") or y.get("forwardPE"))
                set_if_missing("peg_ttm", y.get("pegRatio"))
                set_if_missing("roe", to_pct(y.get("returnOnEquity")))
                set_if_missing("dividend_yield", to_pct(y.get("dividendYield")))
                set_if_missing("eps_growth_yoy", to_pct(y.get("earningsGrowth")))
                set_if_missing("eps_growth_qoq", to_pct(y.get("earningsQuarterlyGrowth")))
                set_if_missing("revenue_growth_yoy", to_pct(y.get("revenueGrowth")))
                set_if_missing("revenue_growth_qoq", to_pct(y.get("revenueQuarterlyGrowth")))
                set_if_missing("analyst_rating", y.get("recommendationKey"))
                earnings = y.get("earningsDate")
                if isinstance(earnings, (list, tuple)) and earnings:
                    set_if_missing("next_earnings", earnings[0])
                set_if_missing("last_earnings", y.get("lastEarningsDate"))
        except Exception:
            if not info:
                info = {}
        return info

    async def get_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        max_bars: Optional[int] = 270,
        return_provider: bool = False,
    ) -> Optional[pd.DataFrame] | tuple[Optional[pd.DataFrame], Optional[str]]:
        """Get OHLCV (newest->first index) with provider policy.

        Semantics (provider-aware):
        - `period` is a coarse request hint (calendar range) for providers that support it
          (e.g. yfinance). Some providers effectively ignore it for daily history.
        - `max_bars` is the hard bound: when set and interval=="1d", we keep only the newest
          `max_bars` rows so downstream compute is stable and predictable.
        - Cache TTL: 300s for intraday; 3600s for daily+
        """
        cache_key = f"historical:{symbol}:{period}:{interval}"
        cached = self.redis_client.get(cache_key)
        if cached:
            try:
                df_cached = pd.read_json(cached, orient="index")
                if return_provider:
                    return df_cached, None
                return df_cached
            except Exception:
                pass

        provider_used: Optional[str] = None
        for provider in self._provider_priority("historical_data"):
            if not self._is_provider_available(provider):
                continue
            provider_used = provider.value
            try:
                if provider == APIProvider.FMP:
                    # Support daily and intraday (5m) for FMP
                    if interval == "5m":
                        df = await self._call_blocking_with_retries(self._get_historical_fmp_5m_sync, symbol, period)
                    else:
                        df = await self._call_blocking_with_retries(self._get_historical_fmp_sync, symbol, period, interval)
                elif provider == APIProvider.TWELVE_DATA:
                    df = await self._call_blocking_with_retries(self._get_historical_twelve_data_sync, symbol, period, interval)
                elif provider == APIProvider.YFINANCE:
                    df = await self._call_blocking_with_retries(self._get_historical_yfinance_sync, symbol, period, interval)
                elif provider == APIProvider.FINNHUB:
                    df = None  # not implemented
                else:
                    df = None
                if df is not None and not df.empty:
                    if max_bars and interval == "1d":
                        df = df.head(max_bars)
                    ttl = 300 if interval in ("1m", "5m") else 3600
                    self.redis_client.setex(cache_key, ttl, df.to_json(orient="index"))
                    if return_provider:
                        return df, provider_used
                    return df
            except Exception:
                continue
        return (None, provider_used) if return_provider else None

    def _get_historical_yfinance_sync(
        self, symbol: str, period: str, interval: str
    ) -> Optional[pd.DataFrame]:
        data = yf.Ticker(symbol).history(period=period, interval=interval)
        if data is None or data.empty:
            return None
        required = ["Open", "High", "Low", "Close"]
        if not any(c in data.columns for c in required):
            return None
        if "Volume" not in data.columns:
            data["Volume"] = 0
        return data[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]].sort_index(ascending=False)

    def _get_historical_fmp_5m_sync(self, symbol: str, period: str) -> Optional[pd.DataFrame]:
        """Fetch intraday 5m bars from FMP historical_chart.

        FMP returns newest-first timestamps. `period` is best-effort: we trim using days.
        """
        # FMP supports intervals like '5min'
        data = fmpsdk.historical_chart(
            apikey=settings.FMP_API_KEY, symbol=symbol, interval="5min"
        )
        if isinstance(data, dict):
            # FMP sometimes returns error dicts; raise so retry/backoff kicks in.
            msg = data.get("Error Message") or data.get("error") or data.get("message") or str(data)
            raise RuntimeError(f"FMP historical_chart error: {msg}")
        if not data or not isinstance(data, list):
            return None
        df = pd.DataFrame(data)
        # Normalize columns and index
        if df.empty or "date" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        cols = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in cols if c in df.columns]]
        df.columns = ["Open", "High", "Low", "Close", "Volume"][: len(df.columns)]
        # Best-effort period trim (e.g., '5d', '30d', '60d')
        try:
            if isinstance(period, str) and period.endswith("d"):
                days = int(period[:-1])
                cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=days)
                df = df[df.index >= cutoff]
        except Exception:
            pass
        return df.sort_index(ascending=False)

    def _get_historical_twelve_data_sync(
        self, symbol: str, period: str, interval: str
    ) -> Optional[pd.DataFrame]:
        if not self.twelve_data_client:
            return None
        td_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1h",
            "1d": "1day",
            "1wk": "1week",
            "1mo": "1month",
        }
        ts = self.twelve_data_client.time_series(
            symbol=symbol, interval=td_map.get(interval, "1day"), outputsize="5000"
        )
        df = ts.as_pandas()
        if df is None or df.empty:
            return None
        out = pd.DataFrame(index=df.index)
        for src, dst in [
            ("open", "Open"),
            ("high", "High"),
            ("low", "Low"),
            ("close", "Close"),
            ("volume", "Volume"),
        ]:
            if src in df.columns:
                out[dst] = df[src]
            elif src.capitalize() in df.columns:
                out[dst] = df[src.capitalize()]
        if "Close" not in out.columns:
            return None
        if "Volume" not in out.columns:
            out["Volume"] = 0
        return out.sort_index(ascending=False)

    def _get_historical_fmp_sync(
        self, symbol: str, period: str, interval: str
    ) -> Optional[pd.DataFrame]:
        if interval != "1d":
            return None
        raw = fmpsdk.historical_price_full(apikey=settings.FMP_API_KEY, symbol=symbol)
        # FMP can return either {"symbol": ..., "historical": [...]} or an error dict.
        if isinstance(raw, dict):
            if raw.get("Error Message") or raw.get("error") or raw.get("message"):
                msg = raw.get("Error Message") or raw.get("error") or raw.get("message")
                raise RuntimeError(f"FMP historical_price_full error: {msg}")
            raw = raw.get("historical")
        if not raw or not isinstance(raw, list):
            return None
        df = pd.DataFrame(raw)
        if df.empty or "date" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        cols = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in cols if c in df.columns]]
        df.columns = ["Open", "High", "Low", "Close", "Volume"][: len(df.columns)]
        return df.sort_index(ascending=False)

    # ---------------------- Index Constituents ----------------------

    async def get_index_constituents(self, index_name: str) -> List[str]:
        """Return constituents for supported indices (SP500, NASDAQ100, DOW30).

        Strategy: Redis cache → FMP → Wikipedia fallback. Normalized to UPPER and '.'→'-'.
        """
        cache_key = f"index_constituents:{index_name}"
        # Redis cache
        cached = self.redis_client.get(cache_key)
        if cached:
            try:
                obj = json.loads(cached)
                if isinstance(obj, dict) and obj.get("symbols"):
                    return list(obj.get("symbols"))
            except Exception:
                pass
        idx = index_name.upper()
        ep = self.index_endpoints.get(idx, {}).get("fmp")
        symbols: List[str] = []
        # FMP
        if settings.FMP_API_KEY and ep:
            try:
                fn = getattr(fmpsdk, ep, None)
                data = fn(apikey=settings.FMP_API_KEY) if callable(fn) else []
            except Exception:
                data = []
            if isinstance(data, list):
                symbols = [str(d.get("symbol", "")).strip().upper().replace('.', '-') for d in data if d.get("symbol")]
        # Track which path we used
        provider_used = "fmp" if symbols else None
        # Wikipedia fallback
        if not symbols:
            import pandas as _pd
            try:
                if idx == "SP500":
                    tables = _pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
                    if tables:
                        df = tables[0]
                        if "Symbol" in df.columns:
                            symbols = [str(s).upper().replace('.', '-') for s in df["Symbol"].dropna().tolist()]
                elif idx == "NASDAQ100":
                    tables = _pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
                    for t in tables:
                        for col in ["Ticker", "Symbol", "Company", "Stock Symbol"]:
                            if col in t.columns:
                                symbols = [str(s).upper().replace('.', '-') for s in t[col].dropna().tolist()]
                                break
                        if symbols:
                            break
                elif idx == "DOW30":
                    tables = _pd.read_html("https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average")
                    for t in tables:
                        if "Symbol" in t.columns and len(t) <= 40:
                            symbols = [str(s).upper().replace('.', '-') for s in t["Symbol"].dropna().tolist()]
                            break
            except Exception:
                symbols = []
        fallback_used = False if provider_used == "fmp" and symbols else (True if not provider_used else False)
        provider_used = provider_used or ("wikipedia" if symbols else "none")
        # Normalize and cache
        out = sorted(list({s for s in symbols if s and len(s) <= 5}))
        try:
            self.redis_client.setex(cache_key, 24 * 3600, json.dumps({"symbols": out}))
            # Store lightweight meta for observability
            meta_key = f"{cache_key}:meta"
            self.redis_client.setex(
                meta_key,
                24 * 3600,
                json.dumps({"provider_used": provider_used, "fallback_used": bool(fallback_used), "count": len(out)}),
            )
        except Exception:
            pass
        return out

    async def get_all_tradeable_symbols(self, indices: Optional[List[str]] = None) -> Dict[str, List[str]]:
        idxs = ["SP500", "NASDAQ100", "DOW30"] if not indices else [i.upper() for i in indices]
        result: Dict[str, List[str]] = {}
        for idx in idxs:
            try:
                result[idx] = await self.get_index_constituents(idx)
            except Exception:
                result[idx] = []
        return result


    # ---------------------- Snapshots ----------------------
    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Return the latest technical snapshot for a symbol.

        Flow:
        1) Try existing stored snapshot in MarketSnapshot (respect expiry)
        2) If not present/stale: build from local DB prices (fast path)
        3) If still missing: compute from provider OHLCV (slow path)
        4) Persist refreshed snapshot and return
        """
        session = SessionLocal()
        try:
            # 1) Try stored snapshot first
            snap = self.get_snapshot_from_store(session, symbol)
            # 2) Build and persist if missing/stale
            if not snap:
                snap = self.compute_snapshot_from_db(session, symbol)
            if not snap:
                snap = await self.compute_snapshot_from_providers(symbol)
            if snap:
                self.persist_snapshot(session, symbol, snap)
            return snap or {}
        finally:
            session.close()

    def get_snapshot_from_store(self, db: Session, symbol: str) -> Dict[str, Any]:
        """Fetch freshest snapshot from MarketSnapshot if not expired.

        Returns raw_analysis if available; otherwise rebuilds a dict from mapped columns.
        """
        now = datetime.utcnow()
        row = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )
        if not row:
            return {}
        exp = row.expiry_timestamp
        try:
            if exp is not None and getattr(exp, 'tzinfo', None) is not None:
                exp = exp.replace(tzinfo=None)
        except Exception:
            pass
        if exp and exp < now:
            return {}
        try:
            if isinstance(row.raw_analysis, dict) and row.raw_analysis:
                return dict(row.raw_analysis)
        except Exception:
            pass
        # Fallback: minimal reconstruction from mapped columns
        out: Dict[str, Any] = {
            "current_price": getattr(row, "current_price", None),
            "as_of_timestamp": getattr(row, "as_of_timestamp", None),
            "rsi": getattr(row, "rsi", None),
            # Canonical fields
            "sma_5": getattr(row, "sma_5", None),
            "sma_10": getattr(row, "sma_10", None),
            "sma_14": getattr(row, "sma_14", None),
            "sma_21": getattr(row, "sma_21", None),
            "sma_50": getattr(row, "sma_50", None),
            "sma_100": getattr(row, "sma_100", None),
            "sma_150": getattr(row, "sma_150", None),
            "sma_200": getattr(row, "sma_200", None),
            "atr_14": getattr(row, "atr_14", None),
            "atr_30": getattr(row, "atr_30", None),
            "atrp_14": getattr(row, "atrp_14", None),
            "atrp_30": getattr(row, "atrp_30", None),
            "range_pos_20d": getattr(row, "range_pos_20d", None),
            "range_pos_50d": getattr(row, "range_pos_50d", None),
            "range_pos_52w": getattr(row, "range_pos_52w", None),
            "atrx_sma_21": getattr(row, "atrx_sma_21", None),
            "atrx_sma_50": getattr(row, "atrx_sma_50", None),
            "atrx_sma_100": getattr(row, "atrx_sma_100", None),
            "atrx_sma_150": getattr(row, "atrx_sma_150", None),
            "rs_mansfield_pct": getattr(row, "rs_mansfield_pct", None),
            "stage_label": getattr(row, "stage_label", None),
            "stage_label_5d_ago": getattr(row, "stage_label_5d_ago", None),
            "stage_slope_pct": getattr(row, "stage_slope_pct", None),
            "stage_dist_pct": getattr(row, "stage_dist_pct", None),
            "pe_ttm": getattr(row, "pe_ttm", None),
            "peg_ttm": getattr(row, "peg_ttm", None),
            "roe": getattr(row, "roe", None),
            "eps_growth_yoy": getattr(row, "eps_growth_yoy", None),
            "eps_growth_qoq": getattr(row, "eps_growth_qoq", None),
            "revenue_growth_yoy": getattr(row, "revenue_growth_yoy", None),
            "revenue_growth_qoq": getattr(row, "revenue_growth_qoq", None),
            "dividend_yield": getattr(row, "dividend_yield", None),
            "beta": getattr(row, "beta", None),
            "analyst_rating": getattr(row, "analyst_rating", None),
            "last_earnings": getattr(row, "last_earnings", None),
            "next_earnings": getattr(row, "next_earnings", None),

            # Backward-compat legacy keys (to be dropped after callers migrate)
            "atr_value": getattr(row, "atr_value", None),
            "ema_10": getattr(row, "ema_10", None),
            "ema_8": getattr(row, "ema_8", None),
            "ema_21": getattr(row, "ema_21", None),
            "ema_200": getattr(row, "ema_200", None),
            "macd": getattr(row, "macd", None),
            "macd_signal": getattr(row, "macd_signal", None),
            "perf_1d": getattr(row, "perf_1d", None),
            "perf_3d": getattr(row, "perf_3d", None),
            "perf_5d": getattr(row, "perf_5d", None),
            "perf_20d": getattr(row, "perf_20d", None),
            "perf_60d": getattr(row, "perf_60d", None),
            "perf_120d": getattr(row, "perf_120d", None),
            "perf_252d": getattr(row, "perf_252d", None),
            "perf_mtd": getattr(row, "perf_mtd", None),
            "perf_qtd": getattr(row, "perf_qtd", None),
            "perf_ytd": getattr(row, "perf_ytd", None),
            "ma_bucket": getattr(row, "ma_bucket", None),
            "pct_dist_ema8": getattr(row, "pct_dist_ema8", None),
            "pct_dist_ema21": getattr(row, "pct_dist_ema21", None),
            "pct_dist_ema200": getattr(row, "pct_dist_ema200", None),
            "atr_dist_ema8": getattr(row, "atr_dist_ema8", None),
            "atr_dist_ema21": getattr(row, "atr_dist_ema21", None),
            "atr_dist_ema200": getattr(row, "atr_dist_ema200", None),
            "td_buy_setup": getattr(row, "td_buy_setup", None),
            "td_sell_setup": getattr(row, "td_sell_setup", None),
            "gaps_unfilled_up": getattr(row, "gaps_unfilled_up", None),
            "gaps_unfilled_down": getattr(row, "gaps_unfilled_down", None),
            "trend_up_count": getattr(row, "trend_up_count", None),
            "trend_down_count": getattr(row, "trend_down_count", None),
            "sector": getattr(row, "sector", None),
            "industry": getattr(row, "industry", None),
            "market_cap": getattr(row, "market_cap", None),
        }
        return out

    def compute_snapshot_from_db(
        self,
        db: Session,
        symbol: str,
        *,
        as_of_dt: datetime | None = None,
    ) -> Dict[str, Any]:
        """Compute a snapshot purely from local PriceData (and enrich it) for speed and consistency.

        - Reads the last ~270 daily bars (newest->first) from price_data
        - Computes indicators locally (no provider calls)
        - Also enriches with chart metrics and fundamentals before returning
        """
        from backend.models import PriceData

        limit_bars = int(getattr(settings, "SNAPSHOT_DAILY_BARS_LIMIT", 400))
        q = db.query(
            PriceData.date,
            PriceData.open_price,
            PriceData.high_price,
            PriceData.low_price,
            PriceData.close_price,
            PriceData.volume,
        ).filter(PriceData.symbol == symbol, PriceData.interval == "1d")
        if as_of_dt is not None:
            q = q.filter(PriceData.date <= as_of_dt)
        rows = q.order_by(PriceData.date.desc()).limit(limit_bars).all()
        if not rows:
            return {}
        df = price_data_rows_to_dataframe(rows, ascending=True)
        snapshot = self._snapshot_from_dataframe(df)
        if not snapshot:
            return {}
        # Record "as-of" timestamp (latest daily bar used for this snapshot).
        # Keep it JSON-friendly (ISO string). The typed DB column is persisted separately.
        try:
            as_of_ts = df.index.max()
            if as_of_ts is not None:
                snapshot["as_of_timestamp"] = (
                    as_of_ts.isoformat() if hasattr(as_of_ts, "isoformat") else str(as_of_ts)
                )
        except Exception:
            pass

        # Level 3/4: Relative strength vs SPY + Weinstein stage (DB-only if benchmark available).
        try:
            bm = "SPY"
            bm_rows = (
                db.query(
                    PriceData.date,
                    PriceData.open_price,
                    PriceData.high_price,
                    PriceData.low_price,
                    PriceData.close_price,
                    PriceData.volume,
                )
                .filter(PriceData.symbol == bm, PriceData.interval == "1d")
                .order_by(PriceData.date.desc())
                .limit(limit_bars)
                .all()
            )
            if bm_rows:
                bm_df = price_data_rows_to_dataframe(bm_rows, ascending=True)
                # compute_weinstein_stage_from_daily expects newest-first
                sym_newest = df.copy()
                bm_newest = bm_df.copy()
                stage = compute_weinstein_stage_from_daily(sym_newest, bm_newest)
                if isinstance(stage, dict):
                    if stage.get("stage_label") is not None:
                        snapshot["stage_label"] = stage.get("stage_label")
                    if stage.get("stage_slope_pct") is not None:
                        snapshot["stage_slope_pct"] = stage.get("stage_slope_pct")
                    if stage.get("stage_dist_pct") is not None:
                        snapshot["stage_dist_pct"] = stage.get("stage_dist_pct")
                    if stage.get("rs_mansfield_pct") is not None:
                        snapshot["rs_mansfield_pct"] = stage.get("rs_mansfield_pct")
                    # Stage 5 trading days ago: drop newest 5 bars and recompute
                    try:
                        stage_prev = compute_weinstein_stage_from_daily(
                            sym_newest.iloc[5:].copy(),
                            bm_newest.iloc[5:].copy(),
                        )
                        if isinstance(stage_prev, dict) and stage_prev.get("stage_label") is not None:
                            snapshot["stage_label_5d_ago"] = stage_prev.get("stage_label")
                    except Exception:
                        pass
        except Exception:
            pass
        # Fundamentals enrichment (reuse from latest snapshot if present; otherwise fetch once)
        # Prefer fundamentals from the latest stored snapshot
        try:
            prev_row = (
                db.query(MarketSnapshot)
                .filter(
                    MarketSnapshot.symbol == symbol,
                    MarketSnapshot.analysis_type == "technical_snapshot",
                )
                .order_by(MarketSnapshot.analysis_timestamp.desc())
                .first()
            )
            if prev_row:
                for key in FUNDAMENTAL_FIELDS_WITH_SUB_INDUSTRY:
                    val = getattr(prev_row, key, None)
                    if val is not None and snapshot.get(key) is None:
                        snapshot[key] = val
        except Exception:
            pass

        if self._needs_fundamentals(snapshot):
            try:
                info = self.get_fundamentals_info(symbol)
                for k in FUNDAMENTAL_FIELDS_WITH_NAME:
                    if info.get(k) is not None:
                        snapshot[k] = info.get(k)
            except Exception:
                pass
        # no broad except here; previous except already guarded
        return snapshot

    async def compute_snapshot_from_providers(self, symbol: str) -> Dict[str, Any]:
        """Compute a snapshot from provider OHLCV when DB path is missing (and enrich it).

        - Uses get_historical_data (policy-driven) to fetch ~1y daily bars
        - Computes indicators locally; no external indicator APIs are used
        - Intended as a slow-path fallback to bootstrap symbols not yet in DB
        """
        data = await self.get_historical_data(symbol, period="1y", interval="1d")
        if data is None or data.empty:
            price_only = await self.get_current_price(symbol)
            return {"current_price": float(price_only)} if price_only else {}

        snapshot = self._snapshot_from_dataframe(data)
        if not snapshot:
            return {}

        # Level 3/4: Relative strength vs SPY + Weinstein stage (provider slow-path; best-effort).
        try:
            bm_df = await self.get_historical_data("SPY", period="1y", interval="1d")
            if bm_df is not None and not bm_df.empty:
                stage = compute_weinstein_stage_from_daily(data, bm_df)
                if isinstance(stage, dict):
                    if stage.get("stage_label") is not None:
                        snapshot["stage_label"] = stage.get("stage_label")
                    if stage.get("stage_slope_pct") is not None:
                        snapshot["stage_slope_pct"] = stage.get("stage_slope_pct")
                    if stage.get("stage_dist_pct") is not None:
                        snapshot["stage_dist_pct"] = stage.get("stage_dist_pct")
                    if stage.get("rs_mansfield_pct") is not None:
                        snapshot["rs_mansfield_pct"] = stage.get("rs_mansfield_pct")
                    try:
                        stage_prev = compute_weinstein_stage_from_daily(
                            data.iloc[5:].copy(),
                            bm_df.iloc[5:].copy(),
                        )
                        if isinstance(stage_prev, dict) and stage_prev.get("stage_label") is not None:
                            snapshot["stage_label_5d_ago"] = stage_prev.get("stage_label")
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            funda = self.get_fundamentals_info(symbol)
            if funda:
                for k in FUNDAMENTAL_FIELDS_WITH_NAME:
                    if funda.get(k) is not None:
                        snapshot[k] = funda.get(k)
        except Exception:
            pass
        return snapshot


    def persist_snapshot(
        self,
        db: Session,
        symbol: str,
        snapshot: Dict[str, Any],
        analysis_type: str = "technical_snapshot",
        ttl_hours: int = 24,
        ) -> MarketSnapshot:
        """Persist latest snapshot (MarketSnapshot) and append to immutable history (MarketSnapshotHistory).

        Architecture:
        - `market_snapshot`: fast "latest view" per (symbol, analysis_type)
        - `market_snapshot_history`: immutable daily ledger keyed by (symbol, analysis_type, as_of_date)
        """
        if not snapshot:
            raise ValueError("empty snapshot")
        now = datetime.utcnow()
        expiry = now + pd.Timedelta(hours=ttl_hours)

        # Normalize as-of timestamp:
        # - MarketSnapshot.as_of_timestamp (timestamptz)
        # - MarketSnapshotHistory.as_of_date (timestamp without tz, midnight)
        from backend.models import PriceData
        from backend.models.market_data import MarketSnapshotHistory
        from datetime import timezone, time as _time

        as_of_ts: datetime | None = None
        raw_as_of = snapshot.get("as_of_timestamp")
        try:
            if isinstance(raw_as_of, datetime):
                as_of_ts = raw_as_of
            elif isinstance(raw_as_of, str) and raw_as_of.strip():
                s = raw_as_of.strip()
                # Treat timezone-less ISO strings as UTC.
                if s.endswith("Z"):
                    as_of_ts = datetime.fromisoformat(s.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(s)
                    as_of_ts = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            as_of_ts = None
        if as_of_ts is None:
            try:
                as_of_ts = (
                    db.query(PriceData.date)
                    .filter(PriceData.symbol == symbol.upper(), PriceData.interval == "1d")
                    .order_by(PriceData.date.desc())
                    .limit(1)
                    .scalar()
                )
                if isinstance(as_of_ts, datetime) and as_of_ts.tzinfo is None:
                    as_of_ts = as_of_ts.replace(tzinfo=timezone.utc)
            except Exception:
                as_of_ts = None

        # Ensure raw snapshot stays JSON-serializable.
        snapshot_json = dict(snapshot)
        if isinstance(as_of_ts, datetime):
            snapshot_json["as_of_timestamp"] = as_of_ts.replace(tzinfo=None).isoformat()

        row = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.analysis_type == analysis_type,
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )
        if row is None:
            row = MarketSnapshot(
                symbol=symbol,
                analysis_type=analysis_type,
                expiry_timestamp=expiry,
                raw_analysis=snapshot_json,
            )
            for k, v in snapshot.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            if as_of_ts is not None and hasattr(row, "as_of_timestamp"):
                row.as_of_timestamp = as_of_ts
            db.add(row)
        else:
            row.expiry_timestamp = expiry
            row.raw_analysis = snapshot_json
            for k, v in snapshot.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            if as_of_ts is not None and hasattr(row, "as_of_timestamp"):
                row.as_of_timestamp = as_of_ts

        # Append to immutable daily ledger (idempotent upsert by unique constraint).
        if as_of_ts is not None:
            as_of_date = datetime.combine(as_of_ts.date(), _time.min)
            existing = (
                db.query(MarketSnapshotHistory)
                .filter(
                    MarketSnapshotHistory.symbol == symbol,
                    MarketSnapshotHistory.analysis_type == analysis_type,
                    MarketSnapshotHistory.as_of_date == as_of_date,
                )
                .first()
            )
            if existing:
                # Headline fields
                existing.current_price = snapshot_json.get("current_price")
                existing.rsi = snapshot_json.get("rsi")
                existing.atr_value = snapshot_json.get("atr_value")
                existing.sma_50 = snapshot_json.get("sma_50")
                existing.macd = snapshot_json.get("macd")
                existing.macd_signal = snapshot_json.get("macd_signal")
                # Wide fields (best-effort: set only if model has the attr)
                for k, v in snapshot_json.items():
                    if hasattr(existing, k):
                        setattr(existing, k, v)
            else:
                hist = MarketSnapshotHistory(
                    symbol=symbol,
                    analysis_type=analysis_type,
                    as_of_date=as_of_date,
                    current_price=snapshot_json.get("current_price"),
                    rsi=snapshot_json.get("rsi"),
                    atr_value=snapshot_json.get("atr_value"),
                    sma_50=snapshot_json.get("sma_50"),
                    macd=snapshot_json.get("macd"),
                    macd_signal=snapshot_json.get("macd_signal"),
                )
                for k, v in snapshot_json.items():
                    if hasattr(hist, k):
                        setattr(hist, k, v)
                db.add(hist)
        db.flush()
        db.commit()
        return row

    # ---------------------- Persistence Helpers (OHLCV Backfill) ----------------------
    def persist_price_bars(
        self,
        db: Session,
        symbol: str,
        df: pd.DataFrame,
        *,
        interval: str = "1d",
        data_source: str = "provider",
        is_adjusted: bool = True,
        delta_after: Optional[datetime] = None,
    ) -> int:
        """Persist OHLCV bars into `price_data` with ON CONFLICT DO NOTHING.

        - Assumes df index are timestamps (newest->first or ascending; both ok)
        - Coalesces missing O/H/L/Volume to Close/0 to avoid NULLs
        - If delta_after is provided, only insert rows with ts > delta_after
        - Returns number of attempted inserts (not necessarily rows changed)
        """
        if df is None or df.empty:
            return 0
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from backend.models import PriceData
        except Exception as exc:
            raise RuntimeError("PostgreSQL dialect or models unavailable") from exc

        # Build rows in chronological order for clarity (and stable delta filtering).
        try:
            df_iter = df.sort_index(ascending=True).iterrows()
        except Exception:
            df_iter = df.iterrows()

        rows: list[dict[str, Any]] = []
        for ts, row in df_iter:
            try:
                pd_date = (
                    datetime.fromtimestamp(ts.timestamp())
                    if hasattr(ts, "timestamp")
                    else ts
                )
            except Exception:
                pd_date = ts
            if delta_after and pd_date <= delta_after:
                continue
            close_val = float(row.get("Close"))
            open_val = (
                float(row.get("Open"))
                if "Open" in row and row.get("Open") is not None
                else close_val
            )
            high_val = (
                float(row.get("High"))
                if "High" in row and row.get("High") is not None
                else close_val
            )
            low_val = (
                float(row.get("Low"))
                if "Low" in row and row.get("Low") is not None
                else close_val
            )
            vol_val = int(row.get("Volume") or 0) if "Volume" in row else 0
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
                }
            )

        if not rows:
            return 0

        stmt = pg_insert(PriceData).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_symbol_date_interval",
            set_={
                "data_source": data_source,
            },
            where=or_(
                PriceData.data_source.is_(None),
                PriceData.data_source.in_(["provider", "fmp_td_yf"]),
            ),
        )
        db.execute(stmt)
        db.commit()
        return len(rows)

    async def backfill_daily_bars(
        self,
        db: Session,
        symbol: str,
        *,
        lookback_period: str = "1y",
        max_bars: int = 270,
    ) -> Dict[str, Any]:
        """Delta backfill last ~270 daily bars for a single symbol using provider policy."""
        # Determine last stored date to do delta-only inserts
        last_date: Optional[datetime] = None
        try:
            from backend.models import PriceData
            last_date = (
                db.query(PriceData.date)
                .filter(PriceData.symbol == symbol.upper(), PriceData.interval == "1d")
                .order_by(PriceData.date.desc())
                .limit(1)
                .scalar()
            )
        except Exception:
            last_date = None
        df, provider_used = await self.get_historical_data(
            symbol=symbol.upper(),
            period=lookback_period,
            interval="1d",
            max_bars=None,
            return_provider=True,
        )
        if df is None or df.empty:
            return {
                "status": "empty",
                "symbol": symbol.upper(),
                "inserted": 0,
                "provider": provider_used,
            }
        # Trim to bounded size for downstream compute
        df = df.tail(max_bars) if max_bars else df
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
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """Delta backfill last N days of 5m bars for a single symbol using provider policy."""
        from backend.models import PriceData
        sym = symbol.upper()
        # Last stored timestamp for 5m to do delta-only inserts
        last_ts: Optional[datetime] = (
            db.query(PriceData.date)
            .filter(PriceData.symbol == sym, PriceData.interval == "5m")
            .order_by(PriceData.date.desc())
            .limit(1)
            .scalar()
        )
        period = f"{max(1, int(lookback_days))}d"
        df, provider_used = await self.get_historical_data(
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
        from backend.models import PriceData
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

    # ---------------------- High-level TA helpers for tests/integration ----------------------
    async def build_indicator_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Build a technical snapshot from provider OHLCV (newest->first) with indicators."""
        return await self.compute_snapshot_from_providers(symbol)

    async def get_weinstein_stage(self, symbol: str, benchmark: str = "SPY") -> Dict[str, Any]:
        """Compute Weinstein stage by fetching daily series for symbol and a benchmark."""
        sym_df = await self.get_historical_data(symbol, period="1y", interval="1d")
        bm_df = await self.get_historical_data(benchmark, period="1y", interval="1d")
        try:
            return compute_weinstein_stage_from_daily(sym_df, bm_df)
        except Exception:
            return {"stage": "UNKNOWN"}

    async def get_technical_analysis(self, symbol: str) -> Dict[str, Any]:
        """Compatibility wrapper expected by tests – returns the latest snapshot."""
        return await self.get_snapshot(symbol)

    def get_tracked_details(self, db: Session, symbols: List[str]) -> Dict[str, Any]:
        if not symbols:
            return {}
        sym_set = {s.upper() for s in symbols}
        rows = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol.in_(sym_set),
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshot.symbol.asc(), MarketSnapshot.analysis_timestamp.desc())
            .all()
        )
        price_rows = (
            db.query(PriceData.symbol, PriceData.close_price)
            .filter(PriceData.symbol.in_(sym_set), PriceData.interval == "1d")
            .distinct(PriceData.symbol)
            .order_by(PriceData.symbol.asc(), PriceData.date.desc())
            .all()
        )
        price_map = {sym.upper(): close for sym, close in price_rows if sym}

        details: Dict[str, Any] = {}
        seen: set[str] = set()

        def _to_float(value):
            try:
                return float(value) if value is not None else None
            except Exception:
                return None

        for row in rows:
            sym = (row.symbol or "").upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            details[sym] = {
                "current_price": _to_float(getattr(row, "current_price", None))
                or _to_float(price_map.get(sym)),
                "atr_value": _to_float(getattr(row, "atr_value", None)),
                "stage_label": getattr(row, "stage_label", None),
                "stage_dist_pct": _to_float(getattr(row, "stage_dist_pct", None)),
                "stage_slope_pct": _to_float(getattr(row, "stage_slope_pct", None)),
                "ma_bucket": getattr(row, "ma_bucket", None),
                "sector": getattr(row, "sector", None),
                "industry": getattr(row, "industry", None),
                "market_cap": _to_float(getattr(row, "market_cap", None)),
                "last_snapshot_at": getattr(
                    row.analysis_timestamp, "isoformat", lambda: None
                )(),
            }

        cons_rows = (
            db.query(
                IndexConstituent.symbol,
                IndexConstituent.index_name,
                IndexConstituent.sector,
                IndexConstituent.industry,
            )
            .filter(IndexConstituent.symbol.in_(sym_set))
            .all()
        )
        for sym, idx_name, sector, industry in cons_rows:
            symbol = (sym or "").upper()
            if not symbol:
                continue
            entry = details.setdefault(symbol, {})
            entry.setdefault("indices", set()).add(idx_name)
            entry.setdefault("sector", sector)
            entry.setdefault("industry", industry)
        for sym, entry in details.items():
            if isinstance(entry.get("indices"), set):
                entry["indices"] = sorted(entry["indices"])
            # Backfill price if still missing
            if entry.get("current_price") is None and price_map.get(sym):
                entry["current_price"] = _to_float(price_map.get(sym))
        return details

    # ---------------------- Coverage instrumentation ----------------------
    def _compute_interval_coverage_for_symbols(
        self,
        db: Session,
        *,
        symbols: List[str],
        interval: str,
        now_utc: datetime | None = None,
        stale_sample_limit: int | None = None,
        return_full_stale: bool = False,
    ) -> tuple[Dict[str, Any], List[str] | None]:
        """Compute freshness buckets and stale/missing sets for a given symbol universe.

        - Includes missing symbols (no bars) in the `none` bucket.
        - Returns a sampled `stale` list for UI, but can also return the full stale symbol list.
        """
        now = now_utc or datetime.utcnow()
        safe_symbols = sorted({str(s).upper() for s in (symbols or []) if s})
        sym_set = set(safe_symbols)
        if stale_sample_limit is None:
            stale_sample_limit = int(settings.COVERAGE_STALE_SAMPLE)

        last_dt: Dict[str, datetime | None] = {s: None for s in safe_symbols}
        if sym_set:
            rows = (
                db.query(PriceData.symbol, PriceData.date)
                .filter(PriceData.interval == interval, PriceData.symbol.in_(sym_set))
                .order_by(PriceData.symbol.asc(), PriceData.date.desc())
                .distinct(PriceData.symbol)
                .all()
            )
            for sym, dt in rows:
                if sym:
                    last_dt[str(sym).upper()] = dt

        def _bucketize(ts: datetime | None) -> str:
            if not ts:
                return "none"
            age = now - ts
            if age <= timedelta(hours=24):
                return "<=24h"
            if age <= timedelta(hours=48):
                return "24-48h"
            return ">48h"

        freshness = {"<=24h": 0, "24-48h": 0, ">48h": 0, "none": 0}
        stale_items: List[Dict[str, Any]] = []
        stale_full: List[str] = []

        for sym in safe_symbols:
            dt = last_dt.get(sym)
            bucket = _bucketize(dt)
            freshness[bucket] = int(freshness.get(bucket, 0)) + 1
            if bucket in (">48h", "none"):
                stale_items.append(
                    {"symbol": sym, "last": dt.isoformat() if dt else None, "bucket": bucket}
                )
                stale_full.append(sym)

        stale_items.sort(
            key=lambda item: (
                item.get("bucket") or "",
                item.get("last") or "",
                item.get("symbol") or "",
            )
        )
        stale_sample = stale_items[: max(0, int(stale_sample_limit))]

        fresh_24 = int(freshness["<=24h"])
        fresh_48 = int(freshness["24-48h"])
        stale_48h = int(freshness[">48h"])
        missing = int(freshness["none"])

        last_iso_map: Dict[str, str | None] = {s: (last_dt[s].isoformat() if last_dt[s] else None) for s in safe_symbols}

        section: Dict[str, Any] = {
            # Count = within freshness SLA (<=48h).
            "count": fresh_24 + fresh_48,
            "last": last_iso_map,
            "freshness": freshness,
            "stale": stale_sample,
            "fresh_24h": fresh_24,
            "fresh_48h": fresh_48,
            "fresh_gt48h": 0,
            "stale_48h": stale_48h,
            "missing": missing,
        }
        return section, (stale_full if return_full_stale else None)

    def coverage_snapshot(
        self,
        db: Session,
        *,
        fill_lookback_days: int | None = None,
    ) -> Dict[str, Any]:
        """Compute coverage freshness, stale lists, and tracked stats for instrumentation/UI."""
        now = datetime.utcnow()
        from backend.models.market_data import MarketSnapshotHistory

        idx_counts: Dict[str, int] = {}
        for idx in ("SP500", "NASDAQ100", "DOW30"):
            idx_counts[idx] = (
                db.query(IndexConstituent)
                .filter(IndexConstituent.index_name == idx, IndexConstituent.is_active.is_(True))
                .count()
            )

        tracked_list, tracked_from_redis = tracked_symbols_with_source(
            db, redis_client=self.redis_client
        )
        tracked_total = len(set(tracked_list))
        if tracked_total:
            universe = sorted(set(tracked_list))
        else:
            universe = sorted(
                {
                    str(s).upper()
                    for (s,) in db.query(PriceData.symbol).distinct().all()
                    if s
                }
            )
        total_symbols = len(universe)

        def _fill_by_date(interval: str, days: int | None = None) -> List[Dict[str, Any]]:
            """Return date buckets for 'has OHLCV row on that date' coverage.

            Each row represents a date (UTC, derived from stored timestamps) with:
            - symbol_count: distinct symbols with at least 1 bar on that date
            - pct_of_universe: symbol_count / total_symbols * 100
            """
            if not universe or total_symbols == 0:
                return []
            lookback = int(
                days
                if days is not None
                else (
                    int(fill_lookback_days)
                    if fill_lookback_days is not None
                    else getattr(settings, "COVERAGE_FILL_LOOKBACK_DAYS", 90)
                )
            )
            start_dt = now - timedelta(days=lookback)
            rows = (
                db.query(
                    func.date(PriceData.date).label("d"),
                    func.count(distinct(PriceData.symbol)).label("symbol_count"),
                )
                .filter(
                    PriceData.interval == interval,
                    PriceData.symbol.in_(set(universe)),
                    PriceData.date >= start_dt,
                )
                .group_by(func.date(PriceData.date))
                .order_by(func.date(PriceData.date).asc())
                .all()
            )
            out: List[Dict[str, Any]] = []
            for d, symbol_count in rows:
                if not d:
                    continue
                n = int(symbol_count or 0)
                out.append(
                    {
                        "date": str(d),
                        "symbol_count": n,
                        "pct_of_universe": round((n / total_symbols) * 100.0, 1) if total_symbols else 0.0,
                    }
                )
            return out

        def _snapshot_fill_by_date(days: int | None = None) -> List[Dict[str, Any]]:
            """Per-date snapshot coverage for technical snapshots (MarketSnapshotHistory ledger)."""
            if not universe or total_symbols == 0:
                return []
            lookback = int(
                days
                if days is not None
                else (
                    int(fill_lookback_days)
                    if fill_lookback_days is not None
                    else getattr(settings, "COVERAGE_FILL_LOOKBACK_DAYS", 90)
                )
            )
            start_dt = now - timedelta(days=lookback)
            snap_dt = MarketSnapshotHistory.as_of_date
            rows = (
                db.query(
                    func.date(snap_dt).label("d"),
                    func.count(distinct(MarketSnapshotHistory.symbol)).label("symbol_count"),
                )
                .filter(
                    MarketSnapshotHistory.analysis_type == "technical_snapshot",
                    MarketSnapshotHistory.symbol.in_(set(universe)),
                    snap_dt >= start_dt,
                )
                .group_by(func.date(snap_dt))
                .order_by(func.date(snap_dt).asc())
                .all()
            )
            out: List[Dict[str, Any]] = []
            for d, symbol_count in rows:
                if not d:
                    continue
                n = int(symbol_count or 0)
                out.append(
                    {
                        "date": str(d),
                        "symbol_count": n,
                        "pct_of_universe": round((n / total_symbols) * 100.0, 1) if total_symbols else 0.0,
                    }
                )
            return out

        daily_section, _ = self._compute_interval_coverage_for_symbols(
            db,
            symbols=universe,
            interval="1d",
            now_utc=now,
            return_full_stale=False,
        )
        m5_section, _ = self._compute_interval_coverage_for_symbols(
            db,
            symbols=universe,
            interval="5m",
            now_utc=now,
            return_full_stale=False,
        )

        snapshot = {
            "generated_at": now.isoformat(),
            "symbols": total_symbols,
            "tracked_count": tracked_total if tracked_from_redis else total_symbols,
            "tracked_sample": tracked_list[:10],
            "indices": idx_counts,
            "daily": daily_section,
            "m5": m5_section,
        }
        # Daily fill series (date -> % of symbols with OHLCV on that date)
        try:
            snapshot["daily"]["fill_by_date"] = _fill_by_date("1d", days=None)
        except Exception:
            snapshot["daily"]["fill_by_date"] = []
        # Snapshot fill series (technical snapshots) for same period
        try:
            snapshot["daily"]["snapshot_fill_by_date"] = _snapshot_fill_by_date(days=None)
        except Exception:
            snapshot["daily"]["snapshot_fill_by_date"] = []
        snapshot["status"] = compute_coverage_status(snapshot)
        return snapshot

# Global instance
market_data_service = MarketDataService()

