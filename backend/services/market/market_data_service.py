from __future__ import annotations

import asyncio
from collections import Counter
import json
import logging
import random
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import finnhub
import fmpsdk
import pandas as pd
import redis
import redis.asyncio as aioredis
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy import func, distinct

from backend.config import settings
from backend.database import SessionLocal
from backend.models import MarketSnapshot
from backend.models.market_data import PriceData, MarketSnapshotHistory
from backend.models.index_constituent import IndexConstituent
from backend.services.market.indicator_engine import (
    calculate_performance_windows,
    classify_ma_bucket_from_ma,
    compute_atr_matrix_metrics,
    compute_full_indicator_series,
    extract_latest_values,
    compute_gap_counts,
    compute_td_sequential_counts,
    compute_trendline_counts,
    compute_weinstein_stage_from_daily,
)
from backend.services.market.universe import tracked_symbols_with_source
from backend.services.market.constants import FUNDAMENTAL_FIELDS
from backend.services.market.dataframe_utils import (
    ensure_newest_first,
    ensure_oldest_first,
    price_data_rows_to_dataframe,
)
from backend.services.market.provider_service import MarketDataProviderService
from backend.services.market.snapshot_service import MarketSnapshotService
from backend.services.market.coverage_service import CoverageService
from backend.services.market.coverage_utils import compute_coverage_status
from backend.services.market.stage_utils import compute_stage_run_lengths
from backend.services.market.fundamentals_service import FundamentalsService, needs_fundamentals
from backend.services.market.stage_quality_service import (
    StageQualityService,
    normalize_stage_label,
    VALID_STAGE_LABELS,
)

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
        self._redis_sync: Optional[redis.Redis] = None
        self._redis_async: Optional[aioredis.Redis] = None
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
        self.fundamentals = FundamentalsService(self)
        self.stage_quality = StageQualityService()

        if settings.FMP_API_KEY:
            logger.info("FMP API configured")

        # Index endpoints for constituents (per-provider)
        self.index_endpoints = {
            "SP500": {"fmp": "sp500_constituent", "finnhub": "^GSPC"},
            "NASDAQ100": {"fmp": "nasdaq_constituent", "finnhub": "^NDX"},
            "DOW30": {"fmp": "dowjones_constituent", "finnhub": "^DJI"},
            "RUSSELL2000": {"fmp": "russell2000_constituent", "finnhub": "^RUT"},
        }

    @property
    def redis_client(self) -> redis.Redis:
        """Sync Redis for Celery, HTTP sync handlers, and `tracked_symbols*`."""
        return self._sync_redis

    @property
    def _sync_redis(self) -> redis.Redis:
        if self._redis_sync is None:
            url = getattr(settings, "REDIS_URL", None)
            if not url:
                raise RuntimeError("REDIS_URL is not configured")
            self._redis_sync = redis.from_url(url)
        return self._redis_sync

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis_async is None:
            url = getattr(settings, "REDIS_URL", None)
            if not url:
                raise RuntimeError("REDIS_URL is not configured")
            self._redis_async = aioredis.from_url(url)
        return self._redis_async

    def is_backfill_5m_enabled(self) -> bool:
        """Check admin toggle stored in Redis; default to DISABLED until admin enables."""
        try:
            raw = self._sync_redis.get("coverage:backfill_5m_enabled")
            if raw is None:
                return False  # Default OFF — admin must explicitly enable
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode()
            return str(raw).strip().lower() not in ("0", "false", "off", "disabled")
        except Exception:
            # Default OFF on errors — 5m backfill is optional, daily flows not blocked
            return False

    async def is_backfill_5m_enabled_async(self) -> bool:
        """Async variant for FastAPI async routes (non-blocking Redis)."""
        try:
            r = await self._get_redis()
            raw = await r.get("coverage:backfill_5m_enabled")
            if raw is None:
                return False  # Default OFF — admin must explicitly enable
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode()
            return str(raw).strip().lower() not in ("0", "false", "off", "disabled")
        except Exception:
            return False  # Default OFF on errors too

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

        # Normalize once to keep ordering contracts explicit and stable.
        df_newest = ensure_newest_first(df)
        df_oldest = ensure_oldest_first(df_newest)

        price = float(df_newest["Close"].iloc[0])
        # df_newest is newest-first with datetime index.
        as_of_ts = None
        try:
            as_of_ts = (
                df_newest.index[0].to_pydatetime()
                if hasattr(df_newest.index[0], "to_pydatetime")
                else df_newest.index[0]
            )
        except Exception:
            as_of_ts = None
        # Use canonical indicator pipeline (not deprecated compute_core_indicators)
        indicator_series = compute_full_indicator_series(df_oldest)
        indicators = extract_latest_values(indicator_series)
        indicators["current_price"] = price
        indicators.update(compute_atr_matrix_metrics(df_oldest, indicators))
        indicators.update(calculate_performance_windows(df_newest))

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
                if len(df_oldest) < window:
                    return None
                recent = df_oldest.tail(window)
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
            chart_df = df_newest.head(120).copy()
            if not chart_df.empty:
                td = compute_td_sequential_counts(chart_df["Close"].tolist())
                snapshot.update(td)
                snapshot.update(compute_gap_counts(chart_df))
                snapshot.update(compute_trendline_counts(ensure_oldest_first(chart_df)))
        except Exception as e:
            logger.warning("chart_metrics_computation failed: %s", e)
        for key in (
            "stage_label",
            "stage_4h",
            "stage_confirmed",
            "stage_slope_pct",
            "stage_dist_pct",
        ):
            snapshot.setdefault(key, None)

        return snapshot

    @staticmethod
    def _normalize_stage_label(stage_label: Any) -> Optional[str]:
        return normalize_stage_label(stage_label)

    def _derive_stage_run_fields(
        self,
        *,
        current_stage_label: Any,
        prior_stage_labels: list[Any] | None,
        latest_history_row: Any | None = None,
    ) -> Dict[str, Any]:
        """Compute per-symbol stage run metadata from stage-label history + current stage."""
        current_norm = self._normalize_stage_label(current_stage_label)
        if current_norm is None or current_norm == "UNKNOWN":
            return {
                "current_stage_days": None,
                "previous_stage_label": None,
                "previous_stage_days": None,
            }

        normalized_prior = []
        for lbl in (prior_stage_labels or []):
            n = self._normalize_stage_label(lbl)
            # Ignore unknown/empty history labels so they do not erase stage runs.
            if n is not None and n != "UNKNOWN":
                normalized_prior.append(n)
        has_normalized_prior = len(normalized_prior) > 0
        seq = normalized_prior + [current_norm]
        run_data = compute_stage_run_lengths(seq)
        if not run_data:
            out = {
                "current_stage_days": 1,
                "previous_stage_label": None,
                "previous_stage_days": None,
            }
        else:
            last = run_data[-1]
            out = {
                "current_stage_days": last.get("current_stage_days"),
                "previous_stage_label": last.get("previous_stage_label"),
                "previous_stage_days": last.get("previous_stage_days"),
            }

        # When history depth is sparse, preserve authoritative run-length metadata
        # from latest history rows to avoid resetting long-running stages.
        if latest_history_row is not None:
            latest_stage_norm = self._normalize_stage_label(
                getattr(latest_history_row, "stage_label", None)
            )
            latest_days_raw = getattr(latest_history_row, "current_stage_days", None)
            try:
                latest_days = int(latest_days_raw) if latest_days_raw is not None else None
            except Exception:
                latest_days = None

            if latest_stage_norm == current_norm:
                if isinstance(latest_days, int) and latest_days > 0:
                    out["current_stage_days"] = max(
                        int(out.get("current_stage_days") or 0), latest_days + 1
                    )
                if out.get("previous_stage_label") is None:
                    out["previous_stage_label"] = getattr(
                        latest_history_row, "previous_stage_label", None
                    )
                if out.get("previous_stage_days") is None:
                    out["previous_stage_days"] = getattr(
                        latest_history_row, "previous_stage_days", None
                    )
            elif latest_stage_norm and latest_stage_norm != "UNKNOWN" and latest_stage_norm != current_norm:
                out["previous_stage_label"] = (
                    out.get("previous_stage_label") or latest_stage_norm
                )
                if isinstance(latest_days, int) and latest_days > 0:
                    out["previous_stage_days"] = max(
                        int(out.get("previous_stage_days") or 0), latest_days
                    )
                if not out.get("current_stage_days"):
                    out["current_stage_days"] = 1
            elif latest_stage_norm in (None, "UNKNOWN") and has_normalized_prior:
                # Latest history row is UNKNOWN but we have known prior labels.
                # The run-length from normalized_prior + current is already correct
                # (UNKNOWN gaps are filtered out). Trust the computed `out` as-is;
                # it already reflects the proper previous_stage from the known
                # sequence and current_stage_days = 1 for a fresh stage entry.
                pass
            elif latest_stage_norm in (None, "UNKNOWN") and not has_normalized_prior:
                # Some historical rows may carry UNKNOWN stage labels while still
                # maintaining monotonic run lengths. Preserve that continuity
                # instead of collapsing current_stage_days to 1.
                if isinstance(latest_days, int) and latest_days > 0:
                    out["current_stage_days"] = max(
                        int(out.get("current_stage_days") or 0), latest_days + 1
                    )
                if out.get("previous_stage_label") is None:
                    out["previous_stage_label"] = getattr(
                        latest_history_row, "previous_stage_label", None
                    )
                if out.get("previous_stage_days") is None:
                    out["previous_stage_days"] = getattr(
                        latest_history_row, "previous_stage_days", None
                    )

        return {
            "current_stage_days": out.get("current_stage_days"),
            "previous_stage_label": out.get("previous_stage_label"),
            "previous_stage_days": out.get("previous_stage_days"),
        }

    @staticmethod
    def _needs_fundamentals(snapshot: Dict[str, Any]) -> bool:
        return needs_fundamentals(snapshot)


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
        except Exception as e:
            logger.warning("http_status_extraction failed: %s", e)
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
        except Exception as e:
            logger.warning("status_code_parse failed: %s", e)
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

    def _call_blocking_with_retries_sync(
        self,
        fn,
        *args,
        attempts: Optional[int] = None,
        max_delay_seconds: Optional[float] = None,
        **kwargs,
    ):
        """Sync helper for provider calls with bounded exponential backoff."""
        n = int(attempts or int(getattr(settings, "MARKET_BACKFILL_RETRY_ATTEMPTS", 6)))
        max_delay = float(
            max_delay_seconds
            if max_delay_seconds is not None
            else float(getattr(settings, "MARKET_BACKFILL_RETRY_MAX_DELAY_SECONDS", 60.0))
        )
        last_exc: Optional[Exception] = None
        for i in range(max(1, n)):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                status = self._extract_http_status(exc)
                is_rate_limited = status == 429 or "Too Many" in str(exc)
                is_transient = status in (429, 500, 502, 503, 504) or is_rate_limited
                if i >= n - 1:
                    break
                base = 0.8 if is_transient else 0.2
                delay = min(max_delay, base * (2**i))
                delay = delay * (0.75 + random.random() * 0.5)
                time.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError("provider call failed without exception")

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol with provider policy and 60s Redis cache."""
        cache_key = f"price:{symbol}"
        r = await self._get_redis()
        cached = await r.get(cache_key)
        if cached:
            try:
                return float(cached)
            except Exception as e:
                logger.warning("cached_price_parse failed for %s: %s", symbol, e)
        for provider in self._provider_priority("real_time_quote"):
            if not self._is_provider_available(provider):
                continue
            try:
                price = None
                if provider == APIProvider.FMP:
                    q = await self._call_blocking_with_retries(
                        fmpsdk.quote, apikey=settings.FMP_API_KEY, symbol=symbol
                    )
                    price = q and len(q) > 0 and q[0].get("price")
                elif provider == APIProvider.YFINANCE:
                    hist = await self._call_blocking_with_retries(
                        lambda: yf.Ticker(symbol).history(period="1d", interval="1m")
                    )
                    price = float(hist["Close"].iloc[-1]) if not hist.empty else None
                if price is not None:
                    await r.setex(cache_key, 60, str(price))
                    return float(price)
            except Exception:
                continue
        return None

    def get_fundamentals_info(self, symbol: str) -> Dict[str, Any]:
        """Delegate to FundamentalsService (multi-provider cascade)."""
        return self.fundamentals.get_fundamentals_info(symbol)


    def _period_to_start_date(period: str) -> datetime:
        """Convert period string to a start date for DB queries."""
        now = datetime.utcnow()
        mapping = {
            "1d": timedelta(days=5),
            "5d": timedelta(days=10),
            "1mo": timedelta(days=35),
            "3mo": timedelta(days=100),
            "6mo": timedelta(days=200),
            "1y": timedelta(days=370),
            "2y": timedelta(days=740),
            "3y": timedelta(days=1100),
            "5y": timedelta(days=1850),
            "10y": timedelta(days=3700),
            "max": timedelta(days=36500),
            "ytd": timedelta(days=370),
        }
        delta = mapping.get(period, timedelta(days=370))
        return now - delta

    @staticmethod
    def _min_bars_for_period(period: str) -> int:
        """Minimum acceptable bar count for a period. Prevents returning sparse data."""
        mapping = {
            "1d": 1,
            "5d": 3,
            "1mo": 15,
            "3mo": 50,
            "6mo": 100,
            "1y": 200,
            "2y": 450,
            "3y": 700,
            "5y": 1100,
            "10y": 2200,
            "max": 0,
            "ytd": 0,
        }
        return mapping.get(period, 200)

    async def get_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        max_bars: Optional[int] = 270,
        return_provider: bool = False,
        db: Optional[Session] = None,
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
        r = await self._get_redis()
        cached = await r.get(cache_key)
        if cached:
            try:
                df_cached = pd.read_json(cached, orient="index")
                if return_provider:
                    return df_cached, None
                return df_cached
            except Exception as e:
                logger.warning("cached_dataframe_parse failed for %s: %s", symbol, e)

        # --- L2: PriceData DB lookup ---
        if db is not None:
            try:
                start_dt = self._period_to_start_date(period)
                db_df = self.get_db_history(db, symbol, interval=interval, start=start_dt)
                min_bars = self._min_bars_for_period(period)
                if db_df is not None and len(db_df) >= max(min_bars, 1):
                    db_df = ensure_newest_first(db_df)
                    if max_bars and interval == "1d":
                        db_df = db_df.head(max_bars)
                    ttl = 300 if interval in ("1m", "5m") else 3600
                    await r.setex(cache_key, ttl, db_df.to_json(orient="index"))
                    logger.info("L2 DB hit for %s (%s/%s): %d bars", symbol, period, interval, len(db_df))
                    if return_provider:
                        return db_df, "db"
                    return db_df
                else:
                    logger.debug("L2 DB miss for %s (%s/%s): got %d bars, need %d",
                                 symbol, period, interval, len(db_df) if db_df is not None else 0, min_bars)
            except Exception as db_exc:
                logger.warning("L2 DB read for %s failed (falling through to L3): %s", symbol, db_exc)

        # --- L3: External API providers ---
        provider_used: Optional[str] = None
        for provider in self._provider_priority("historical_data"):
            if not self._is_provider_available(provider):
                continue
            provider_used = provider.value
            # Provider-specific symbol aliases for index proxies that may require
            # caret-prefixed tickers on some APIs (e.g., Yahoo index symbols).
            fetch_symbol = symbol
            if provider == APIProvider.YFINANCE and str(symbol).upper() == "SOX":
                fetch_symbol = "^SOX"
            try:
                if provider == APIProvider.FMP:
                    # Support daily and intraday (5m) for FMP
                    if interval == "5m":
                        df = await self._call_blocking_with_retries(self._get_historical_fmp_5m_sync, fetch_symbol, period)
                    else:
                        df = await self._call_blocking_with_retries(self._get_historical_fmp_sync, fetch_symbol, period, interval)
                elif provider == APIProvider.TWELVE_DATA:
                    df = await self._call_blocking_with_retries(self._get_historical_twelve_data_sync, fetch_symbol, period, interval)
                elif provider == APIProvider.YFINANCE:
                    df = await self._call_blocking_with_retries(self._get_historical_yfinance_sync, fetch_symbol, period, interval)
                elif provider == APIProvider.FINNHUB:
                    df = None  # not implemented
                else:
                    df = None
                if df is not None and not df.empty:
                    if max_bars and interval == "1d":
                        df = df.head(max_bars)
                    ttl = 300 if interval in ("1m", "5m") else 3600
                    await r.setex(cache_key, ttl, df.to_json(orient="index"))
                    try:
                        db_session = SessionLocal()
                        self.persist_price_bars(db_session, symbol, df, interval=interval, data_source=provider_used or "provider")
                        db_session.close()
                    except Exception as persist_exc:
                        logger.warning("Write-through persist_price_bars for %s failed (non-blocking): %s", symbol, persist_exc)
                    if return_provider:
                        return df, provider_used
                    return df
            except Exception as exc:
                logger.warning("Provider %s failed for %s (%s/%s): %s", provider.value, symbol, period, interval, exc)
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
        except Exception as e:
            logger.warning("period_filter failed for %s: %s", symbol, e)
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

    _IWM_HOLDINGS_URL = (
        "https://www.ishares.com/us/products/239710/"
        "ishares-russell-2000-etf/1467271812596.ajax"
        "?fileType=csv&fileName=IWM_holdings&dataType=fund"
    )

    @staticmethod
    def _parse_ishares_csv(text: str) -> List[str]:
        """Parse iShares ETF holdings CSV and extract ticker symbols.

        iShares CSVs have metadata header rows before the actual data table.
        The data section starts after a row containing 'Ticker' as a column header.
        """
        import csv
        import io
        import re

        lines = text.strip().splitlines()
        header_idx: Optional[int] = None
        ticker_col: Optional[int] = None
        for i, line in enumerate(lines):
            lower = line.lower()
            if "ticker" in lower:
                reader = csv.reader(io.StringIO(line))
                cols = next(reader, [])
                for j, col in enumerate(cols):
                    if col.strip().lower() == "ticker":
                        header_idx = i
                        ticker_col = j
                        break
                if header_idx is not None:
                    break

        if header_idx is None or ticker_col is None:
            return []

        symbols: List[str] = []
        for line in lines[header_idx + 1:]:
            if not line.strip():
                continue
            reader = csv.reader(io.StringIO(line))
            cols = next(reader, [])
            if ticker_col >= len(cols):
                continue
            raw = cols[ticker_col].strip().upper()
            if not raw or raw in ("-", "CASH", "N/A", "NA", "--"):
                continue
            symbol = raw.replace(".", "-")
            if not re.match(r"^[A-Z]{1,5}(?:-[A-Z]{1,2})?$", symbol):
                continue
            symbols.append(symbol)
        return symbols

    @staticmethod
    async def _get_last_good_constituents(r, idx: str) -> List[str]:
        """Return last-known-good constituent list from Redis, or empty list."""
        try:
            raw = await r.get(f"index_constituents:{idx}:last_good")
            if raw:
                data = json.loads(raw)
                return data.get("symbols", [])
        except Exception:
            pass
        return []

    async def _fetch_iwm_holdings(self) -> List[str]:
        """Fetch Russell 2000 constituents from iShares IWM ETF holdings CSV."""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    self._IWM_HOLDINGS_URL,
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers={"User-Agent": "Mozilla/5.0 AxiomFolio/1.0"},
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "iShares IWM fetch returned HTTP %d", resp.status
                        )
                        return []
                    text = await resp.text()
            return self._parse_ishares_csv(text)
        except Exception as exc:
            logger.warning("iShares IWM holdings fetch failed: %s", exc)
            return []

    async def get_index_constituents(self, index_name: str) -> List[str]:
        """Return constituents for supported indices (SP500, NASDAQ100, DOW30, RUSSELL2000).

        Strategy: Redis cache → FMP → Finnhub → Wikipedia/iShares fallback.
        Normalized to UPPER and '.'→'-'.
        """
        cache_key = f"index_constituents:{index_name}"
        # Redis cache
        r = await self._get_redis()
        cached = await r.get(cache_key)
        if cached:
            try:
                obj = json.loads(cached)
                if isinstance(obj, dict) and obj.get("symbols"):
                    return list(obj.get("symbols"))
            except Exception as e:
                logger.warning("cached_constituents_parse failed for %s: %s", index_name, e)
        idx = index_name.upper()
        ep = self.index_endpoints.get(idx, {}).get("fmp")
        symbols: List[str] = []
        # FMP via fmpsdk
        if settings.FMP_API_KEY and ep:
            try:
                fn = getattr(fmpsdk, ep, None)
                if callable(fn):
                    data = fn(apikey=settings.FMP_API_KEY)
                else:
                    # fmpsdk lacks this function — try direct HTTP call
                    import requests as _req
                    url = f"https://financialmodelingprep.com/api/v3/{ep}?apikey={settings.FMP_API_KEY}"
                    resp = _req.get(url, timeout=30)
                    data = resp.json() if resp.status_code == 200 else []
            except Exception as exc:
                logger.warning("Index %s: FMP constituent fetch failed: %s", idx, exc)
                data = []
            if isinstance(data, list):
                symbols = [str(d.get("symbol", "")).strip().upper().replace('.', '-') for d in data if d.get("symbol")]
        provider_used = "fmp" if symbols else None
        if symbols:
            logger.info("Index %s: fetched %d constituents from FMP", idx, len(symbols))

        # Finnhub fallback
        if not symbols:
            fh_symbol = self.index_endpoints.get(idx, {}).get("finnhub")
            if self.finnhub_client and fh_symbol:
                try:
                    fh_data = self.finnhub_client.indices_const(symbol=fh_symbol)
                    if isinstance(fh_data, dict) and fh_data.get("constituents"):
                        symbols = [
                            str(s).strip().upper().replace('.', '-')
                            for s in fh_data["constituents"] if s
                        ]
                        if symbols:
                            provider_used = "finnhub"
                            logger.info("Index %s: fetched %d constituents from Finnhub", idx, len(symbols))
                except Exception as exc:
                    logger.warning("Index %s: Finnhub constituents failed: %s", idx, exc)

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
                elif idx == "RUSSELL2000":
                    symbols = await self._fetch_iwm_holdings()
                    if symbols:
                        provider_used = "ishares_iwm"
                        logger.info(
                            "Index RUSSELL2000: fetched %d constituents from iShares IWM ETF",
                            len(symbols),
                        )
            except Exception as exc:
                logger.warning("Index %s: Wikipedia fallback failed: %s", idx, exc)
                symbols = []
        fallback_used = provider_used not in ("fmp",) if symbols else True
        provider_used = provider_used or ("wikipedia" if symbols else "none")
        if provider_used == "wikipedia":
            logger.info("Index %s: fetched %d constituents from Wikipedia fallback", idx, len(symbols))
        elif provider_used == "none":
            logger.error("Index %s: ALL constituent providers failed (FMP, Finnhub, Wikipedia)", idx)
        # Normalize and cache (never cache empty lists — avoids 24h lockout)
        out = sorted(list({s for s in symbols if s and len(s) <= 5}))
        if not out:
            logger.warning("Index %s: 0 constituents after normalization — skipping cache", idx)
            last_good = await self._get_last_good_constituents(r, idx)
            if last_good:
                logger.warning("Index %s: returning %d last-known-good constituents", idx, len(last_good))
            return last_good or out
        try:
            await r.setex(cache_key, 24 * 3600, json.dumps({"symbols": out}))
            await r.set(f"index_constituents:{idx}:last_good", json.dumps({"symbols": out}))
            # Store lightweight meta for observability
            meta_key = f"{cache_key}:meta"
            await r.setex(
                meta_key,
                24 * 3600,
                json.dumps({"provider_used": provider_used, "fallback_used": bool(fallback_used), "count": len(out)}),
            )
        except Exception as e:
            logger.warning("redis_constituents_cache failed for %s: %s", idx, e)
        return out

    async def get_all_tradeable_symbols(self, indices: Optional[List[str]] = None) -> Dict[str, List[str]]:
        # Default to major indices. Include RUSSELL2000 for comprehensive US equity coverage.
        idxs = ["SP500", "NASDAQ100", "DOW30", "RUSSELL2000"] if not indices else [i.upper() for i in indices]
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
        except Exception as e:
            logger.warning("expiry_tz_strip failed for %s: %s", symbol, e)
        if exp and exp < now:
            return {}
        try:
            if isinstance(row.raw_analysis, dict) and row.raw_analysis:
                return dict(row.raw_analysis)
        except Exception as e:
            logger.warning("raw_analysis_parse failed for %s: %s", symbol, e)
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
            "stage_4h": getattr(row, "stage_4h", None),
            "stage_confirmed": getattr(row, "stage_confirmed", None),
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
        skip_fundamentals: bool = False,
        benchmark_df=None,
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
        # Keep newest-first ordering for snapshot math (_snapshot_from_dataframe expects this).
        df = price_data_rows_to_dataframe(rows, ascending=False)
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
        except Exception as e:
            logger.warning("as_of_timestamp_extract failed for %s: %s", symbol, e)

        # Level 3/4: Relative strength vs SPY + Weinstein stage (DB-only if benchmark available).
        try:
            if benchmark_df is not None:
                bm_df = benchmark_df
            else:
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
                bm_df = price_data_rows_to_dataframe(bm_rows, ascending=False) if bm_rows else None
            if bm_df is not None:
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
                    lbl = snapshot.get("stage_label")
                    if lbl is not None:
                        snapshot["stage_4h"] = lbl
                        snapshot["stage_confirmed"] = True
                    # Stage 5 trading days ago: drop newest 5 bars and recompute
                    try:
                        stage_prev = compute_weinstein_stage_from_daily(
                            sym_newest.iloc[5:].copy(),
                            bm_newest.iloc[5:].copy(),
                        )
                        if isinstance(stage_prev, dict) and stage_prev.get("stage_label") is not None:
                            snapshot["stage_label_5d_ago"] = stage_prev.get("stage_label")
                    except Exception as e:
                        logger.warning("stage_label_5d_ago failed for %s: %s", symbol, e)
                # Stage duration fields (prefer latest history row if available)
                try:
                    from backend.models.market_data import MarketSnapshotHistory
                    from datetime import datetime as _dt

                    snapshot_as_of = snapshot.get("as_of_timestamp")
                    snapshot_as_of_dt = None
                    if isinstance(snapshot_as_of, _dt):
                        snapshot_as_of_dt = snapshot_as_of
                    elif isinstance(snapshot_as_of, str) and snapshot_as_of.strip():
                        try:
                            s = snapshot_as_of.strip()
                            if s.endswith("Z"):
                                snapshot_as_of_dt = _dt.fromisoformat(s.replace("Z", "+00:00"))
                            else:
                                snapshot_as_of_dt = _dt.fromisoformat(s)
                        except Exception:
                            snapshot_as_of_dt = None

                    hist_q = (
                        db.query(MarketSnapshotHistory)
                        .filter(
                            MarketSnapshotHistory.symbol == symbol,
                            MarketSnapshotHistory.analysis_type == "technical_snapshot",
                        )
                    )
                    # Avoid double-counting if today's history row already exists.
                    if snapshot_as_of_dt is not None:
                        hist_q = hist_q.filter(MarketSnapshotHistory.as_of_date < snapshot_as_of_dt)

                    latest_hist = (
                        hist_q.order_by(MarketSnapshotHistory.as_of_date.desc()).first()
                    )
                    recent_hist_rows = (
                        hist_q.order_by(MarketSnapshotHistory.as_of_date.desc())
                        .limit(400)
                        .all()
                    )
                    # compute run lengths in chronological order
                    prior_labels = [
                        getattr(r, "stage_label", None) for r in reversed(recent_hist_rows)
                    ]
                    snapshot.update(
                        self._derive_stage_run_fields(
                            current_stage_label=snapshot.get("stage_label"),
                            prior_stage_labels=prior_labels,
                            latest_history_row=latest_hist,
                        )
                    )
                except Exception as e:
                    logger.warning("stage_duration_compute failed for %s: %s", symbol, e)
        except Exception as e:
            logger.warning("stage_rs_computation failed for %s: %s", symbol, e)
        # Fundamentals enrichment (reuse from latest snapshot if present; otherwise fetch once)
        # Prefer fundamentals from the latest stored snapshot, but skip if stale (>7 days)
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
                prev_ts = getattr(prev_row, "analysis_timestamp", None)
                prev_stale = False
                if prev_ts is not None:
                    try:
                        age = datetime.utcnow() - prev_ts.replace(tzinfo=None)
                        prev_stale = age > timedelta(days=7)
                    except Exception as e:
                        logger.warning("prev_timestamp_age_check failed for %s: %s", symbol, e)
                if not prev_stale:
                    for key in FUNDAMENTAL_FIELDS:
                        val = getattr(prev_row, key, None)
                        if val is not None and snapshot.get(key) is None:
                            snapshot[key] = val
        except Exception as e:
            logger.warning("prev_fundamentals_reuse failed for %s: %s", symbol, e)

        if not skip_fundamentals and self._needs_fundamentals(snapshot):
            try:
                info = self.get_fundamentals_info(symbol)
                for k in FUNDAMENTAL_FIELDS:
                    if info.get(k) is not None:
                        snapshot[k] = info.get(k)
            except Exception as e:
                logger.warning("fundamentals_fetch failed for %s: %s", symbol, e)
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
                    lbl = snapshot.get("stage_label")
                    if lbl is not None:
                        snapshot["stage_4h"] = lbl
                        snapshot["stage_confirmed"] = True
                    try:
                        stage_prev = compute_weinstein_stage_from_daily(
                            data.iloc[5:].copy(),
                            bm_df.iloc[5:].copy(),
                        )
                        if isinstance(stage_prev, dict) and stage_prev.get("stage_label") is not None:
                            snapshot["stage_label_5d_ago"] = stage_prev.get("stage_label")
                    except Exception as e:
                        logger.warning("stage_label_5d_ago failed for %s: %s", symbol, e)
        except Exception as e:
            logger.warning("stage_rs_computation failed for %s: %s", symbol, e)

        try:
            funda = self.get_fundamentals_info(symbol)
            if funda:
                for k in FUNDAMENTAL_FIELDS:
                    if funda.get(k) is not None:
                        snapshot[k] = funda.get(k)
        except Exception as e:
            logger.warning("fundamentals_enrichment failed for %s: %s", symbol, e)
        return snapshot


    def persist_snapshot(
        self,
        db: Session,
        symbol: str,
        snapshot: Dict[str, Any],
        analysis_type: str = "technical_snapshot",
        ttl_hours: int = 24,
        auto_commit: bool = True,
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
            row.analysis_timestamp = datetime.utcnow()
            for k, v in snapshot.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            if as_of_ts is not None and hasattr(row, "as_of_timestamp"):
                row.as_of_timestamp = as_of_ts
            db.add(row)
        else:
            row.analysis_timestamp = datetime.utcnow()
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
                existing.analysis_timestamp = datetime.utcnow()
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
                    analysis_timestamp=datetime.utcnow(),
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
        if auto_commit:
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
        is_synthetic_ohlc: bool = False,
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
        prev_close: Optional[float] = None
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

            if close_val <= 0:
                logger.warning("persist_price_bars: %s %s close=%.4f (<=0)", symbol, pd_date, close_val)
            elif interval == "1d" and prev_close and prev_close > 0:
                pct_chg = abs(close_val - prev_close) / prev_close
                if pct_chg > 0.50:
                    logger.warning(
                        "persist_price_bars: %s %s %.1f%% daily move (%.2f->%.2f)",
                        symbol, pd_date, pct_chg * 100, prev_close, close_val,
                    )
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

        if not rows:
            return 0

        stmt = pg_insert(PriceData).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_symbol_date_interval",
            set_={
                "data_source": data_source,
                "is_synthetic_ohlc": is_synthetic_ohlc,
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
        for idx in ("SP500", "NASDAQ100", "DOW30", "RUSSELL2000"):
            idx_counts[idx] = (
                db.query(IndexConstituent)
                .filter(IndexConstituent.index_name == idx, IndexConstituent.is_active.is_(True))
                .count()
            )

        tracked_list, tracked_from_redis = tracked_symbols_with_source(
            db, redis_client=self._sync_redis
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

    # ---------------------- Stage quality + repair ----------------------
    _VALID_STAGE_LABELS = VALID_STAGE_LABELS

    def stage_quality_summary(
        self,
        db: Session,
        *,
        lookback_days: int = 120,
    ) -> Dict[str, Any]:
        """Delegate to StageQualityService."""
        return self.stage_quality.stage_quality_summary(db, lookback_days=lookback_days)


    def repair_stage_history_window(
        self,
        db: Session,
        *,
        days: int = 120,
        symbol: str | None = None,
    ) -> Dict[str, Any]:
        """Delegate to StageQualityService."""
        return self.stage_quality.repair_stage_history_window(db, days=days, symbol=symbol)

    def get_historical_dividends(self, symbol: str) -> List[Dict]:
        """Fetch historical dividend payments from FMP for a given symbol."""
        if not settings.FMP_API_KEY:
            return []
        try:
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/stock_dividend/{symbol}?apikey={settings.FMP_API_KEY}"
            import requests
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data.get("historical", [])
        except Exception as e:
            logger.warning("FMP dividend fetch failed for %s: %s", symbol, e)
            return []

# Global instance
market_data_service = MarketDataService()

