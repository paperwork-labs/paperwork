from __future__ import annotations

import asyncio
import json
import logging
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import fmpsdk
import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.services.market.dataframe_utils import ensure_newest_first
from backend.services.market.rate_limiter import provider_rate_limiter

if TYPE_CHECKING:
    from backend.services.market.market_infra import MarketInfra
    from backend.services.market.price_bar_writer import PriceBarWriter

logger = logging.getLogger(__name__)

L2_FRESHNESS_MAX_DAYS = 4


def _last_n_trading_sessions(n: int = 2) -> list:
    """Return the last N completed NYSE trading sessions using exchange_calendars.

    Falls back to empty list if the library is unavailable.
    """
    try:
        import exchange_calendars as xcals

        nyse = xcals.get_calendar("XNYS")
        # tz-naive: exchange_calendars sessions are naive UTC dates
        today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
        schedule = nyse.sessions_in_range(today - pd.Timedelta(days=15), today)
        from zoneinfo import ZoneInfo

        et_now = datetime.now(ZoneInfo("America/New_York"))
        if et_now.hour < 16:
            closed = schedule[schedule < today]
        else:
            closed = schedule[schedule <= today]
        return list(closed[-n:])
    except Exception as e:
        logger.warning("_last_n_trading_sessions failed, using empty session list: %s", e)
        return []


def _is_l2_fresh(latest_bar_date) -> bool:
    """Check if the latest bar is from a recent completed trading session.

    Uses exchange_calendars for NYSE schedule awareness (holidays, early closes).
    Falls back to static L2_FRESHNESS_MAX_DAYS if calendar is unavailable.
    """
    if latest_bar_date is None:
        return False
    try:
        bar_ts = pd.Timestamp(latest_bar_date).normalize()
        sessions = _last_n_trading_sessions(2)
        if sessions:
            oldest_acceptable = pd.Timestamp(sessions[0]).normalize()
            return bar_ts >= oldest_acceptable
    except Exception:
        logger.debug("Trading session check failed for L2 freshness, falling back to day count")
    days_stale = (pd.Timestamp.now("UTC").normalize().tz_localize(None) - pd.Timestamp(latest_bar_date).normalize().tz_localize(None)).days
    return days_stale <= L2_FRESHNESS_MAX_DAYS


class APIProvider(Enum):
    FINNHUB = "finnhub"
    TWELVE_DATA = "twelve_data"
    FMP = "fmp"
    YFINANCE = "yfinance"


_cb_failures: Dict[str, int] = {}
_cb_open_until: Dict[str, float] = {}
_cb_lock = threading.Lock()


class ProviderRouter:
    """Provider selection, circuit breakers, retry logic, and historical data fetching."""

    _CB_THRESHOLD = 5
    _CB_COOLDOWN_S = 600

    def __init__(self, infra: "MarketInfra", price_bars: "PriceBarWriter") -> None:
        self._infra = infra
        self._pbw = price_bars

    # ---------------------- Circuit breaker ----------------------

    def _cb_is_open(self, provider: APIProvider) -> bool:
        key = provider.value
        with _cb_lock:
            deadline = _cb_open_until.get(key, 0.0)
            if time.monotonic() < deadline:
                return True
            if deadline:
                _cb_failures.pop(key, None)
                _cb_open_until.pop(key, None)
        return False

    def _cb_record_failure(self, provider: APIProvider) -> None:
        key = provider.value
        with _cb_lock:
            _cb_failures[key] = _cb_failures.get(key, 0) + 1
            if _cb_failures[key] >= self._CB_THRESHOLD:
                _cb_open_until[key] = time.monotonic() + self._CB_COOLDOWN_S
                logger.warning(
                    "Circuit breaker OPEN for %s after %d consecutive failures (cooldown %ds)",
                    key, _cb_failures[key], self._CB_COOLDOWN_S,
                )

    def _cb_record_success(self, provider: APIProvider) -> None:
        key = provider.value
        with _cb_lock:
            _cb_failures.pop(key, None)
            _cb_open_until.pop(key, None)

    # ---------------------- Provider selection ----------------------

    def _provider_priority(self, data_type: str) -> List[APIProvider]:
        """Return provider order based on MARKET_PROVIDER_POLICY and availability.

        data_type: "historical_data" | "real_time_quote" | "company_info"
        paid policy: [FMP, yfinance, TwelveData]
        free policy: [FMP?] + yfinance + [TwelveData?] + finnhub
        """
        policy = str(getattr(settings, "MARKET_PROVIDER_POLICY", "paid")).lower()
        has_fmp = bool(settings.FMP_API_KEY)
        has_td = bool(settings.TWELVE_DATA_API_KEY)
        if data_type == "historical_data":
            if policy == "paid":
                if has_fmp and has_td:
                    return [APIProvider.FMP, APIProvider.YFINANCE, APIProvider.TWELVE_DATA]
                if has_fmp:
                    return [APIProvider.FMP, APIProvider.YFINANCE]
                if has_td:
                    return [APIProvider.YFINANCE, APIProvider.TWELVE_DATA]
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
        if self._cb_is_open(provider):
            return False
        if provider == APIProvider.FMP:
            if not settings.FMP_API_KEY:
                return False
            try:
                probe = self._infra._sync_redis.get("health:provider_keys")
                if probe:
                    data = json.loads(probe)
                    fmp_probe = data.get("fmp")
                    if isinstance(fmp_probe, str):
                        lower = fmp_probe.strip().lower()
                        if lower.startswith("error"):
                            return False
                        if lower.startswith("http_") and lower != "http_200":
                            return False
                    elif isinstance(fmp_probe, dict):
                        if str(fmp_probe.get("status", "")).strip().lower() == "error":
                            return False
            except Exception:
                logger.debug("FMP provider availability check failed, assuming available")
            return True
        if provider == APIProvider.TWELVE_DATA:
            return self._infra.twelve_data_client is not None
        if provider == APIProvider.FINNHUB:
            return self._infra.finnhub_client is not None
        if provider == APIProvider.YFINANCE:
            return True
        return False

    # ---------------------- Retry helpers ----------------------

    @staticmethod
    def _extract_http_status(exc: Exception) -> Optional[int]:
        """Best-effort extraction of HTTP status code from provider exceptions."""
        try:
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
            except Exception as e:
                logger.debug("http_status getattr %s failed: %s", attr, e)
                continue
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
        """Run a blocking provider call in a thread with bounded exponential backoff."""
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
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                status = self._extract_http_status(exc)
                is_rate_limited = status == 429 or "too many" in str(exc).lower()
                is_transient = status in (429, 500, 502, 503, 504) or is_rate_limited
                if is_rate_limited and i == 0:
                    n = min(n, 2)
                if i >= n - 1:
                    break
                base = 0.8 if is_transient else 0.2
                delay = min(max_delay, base * (2**i))
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
                is_rate_limited = status == 429 or "too many" in str(exc).lower()
                is_transient = status in (429, 500, 502, 503, 504) or is_rate_limited
                if is_rate_limited and i == 0:
                    n = min(n, 2)
                if i >= n - 1:
                    break
                base = 0.8 if is_transient else 0.2
                delay = min(max_delay, base * (2**i))
                delay = delay * (0.75 + random.random() * 0.5)
                time.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError("provider call failed without exception")

    # ---------------------- Period helpers ----------------------

    @staticmethod
    def _period_to_start_date(period: str) -> datetime:
        """Convert period string to a start date for DB queries."""
        now = datetime.now(timezone.utc)
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
        return (now - delta).replace(tzinfo=None)

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

    # ---------------------- Historical data ----------------------

    async def get_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        max_bars: Optional[int] = 270,
        return_provider: bool = False,
        db: Optional[Session] = None,
        skip_write_through: bool = False,
    ) -> Optional[pd.DataFrame] | tuple[Optional[pd.DataFrame], Optional[str]]:
        """Get OHLCV (newest->first index) with provider policy.

        Semantics (provider-aware):
        - `period` is a coarse request hint (calendar range) for providers that support it.
        - `max_bars` is the hard bound: when set and interval=="1d", we keep only the newest
          `max_bars` rows so downstream compute is stable and predictable.
        - Cache TTL: 300s for intraday; 3600s for daily+
        """
        cache_key = f"historical:{symbol}:{period}:{interval}"
        r = None
        cached = None
        try:
            r = await self._infra._get_redis()
            cached = await r.get(cache_key)
        except Exception as e:
            logger.warning(
                "Redis unavailable for historical cache read for %s, falling through to L2/L3: %s",
                symbol,
                e,
            )
        if cached:
            try:
                df_cached = pd.read_json(cached, orient="index")
                try:
                    _date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    await r.hincrby(f"provider:calls:{_date_key}", "l1_hit", 1)
                    await r.expire(f"provider:calls:{_date_key}", 86400 * 30)
                except Exception:
                    logger.debug("Redis L1 hit counter increment failed")
                if return_provider:
                    return df_cached, "redis_cache"
                return df_cached
            except Exception as e:
                logger.warning("cached_dataframe_parse failed for %s: %s", symbol, e)

        # --- L2: PriceData DB lookup ---
        if db is not None:
            try:
                start_dt = self._period_to_start_date(period)
                db_df = self._pbw.get_db_history(db, symbol, interval=interval, start=start_dt)
                min_bars = self._min_bars_for_period(period)
                if db_df is not None and len(db_df) >= max(min_bars, 1):
                    db_df = ensure_newest_first(db_df)
                    latest_date = db_df.index.max()
                    if latest_date is not None:
                        if not _is_l2_fresh(latest_date):
                            logger.debug("L2 stale for %s: latest bar %s, falling through to L3",
                                         symbol, latest_date)
                        else:
                            if max_bars and interval == "1d":
                                db_df = db_df.head(max_bars)
                            ttl = 300 if interval in ("1m", "5m") else 3600
                            try:
                                rw = r if r is not None else await self._infra._get_redis()
                                await rw.setex(cache_key, ttl, db_df.to_json(orient="index"))
                                try:
                                    _date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                                    await rw.hincrby(f"provider:calls:{_date_key}", "l2_hit", 1)
                                    await rw.expire(f"provider:calls:{_date_key}", 86400 * 30)
                                except Exception:
                                    logger.debug("Redis L2 hit counter increment failed")
                            except Exception as l2_cache_exc:
                                logger.warning(
                                    "Redis L2 cache write failed for %s (non-blocking): %s",
                                    symbol,
                                    l2_cache_exc,
                                )
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
            _counter_name = "twelvedata" if provider == APIProvider.TWELVE_DATA else provider.value
            if r is not None:
                try:
                    _date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    _current = int(await r.hget(f"provider:calls:{_date_key}", _counter_name) or 0)
                    _policy = settings.provider_policy
                    _budgets = {
                        "fmp": _policy.fmp_daily_budget,
                        "twelvedata": _policy.twelvedata_daily_budget,
                        "yfinance": _policy.yfinance_daily_budget,
                    }
                    _limit = _budgets.get(_counter_name, 10000)
                    if _current >= _limit:
                        logger.warning("Provider %s over daily budget (%d/%d), skipping", _counter_name, _current, _limit)
                        continue
                except Exception as _budget_exc:
                    logger.warning(
                        "Redis unavailable for budget check, allowing provider call for %s: %s",
                        _counter_name,
                        _budget_exc,
                    )
            await provider_rate_limiter.acquire(
                "twelvedata" if provider == APIProvider.TWELVE_DATA else provider.value
            )
            provider_used = provider.value
            fetch_symbol = symbol
            if provider == APIProvider.YFINANCE and str(symbol).upper() == "SOX":
                fetch_symbol = "^SOX"
            try:
                if provider == APIProvider.FMP:
                    if interval == "5m":
                        df = await self._call_blocking_with_retries(self._get_historical_fmp_5m_sync, fetch_symbol, period)
                    else:
                        df = await self._call_blocking_with_retries(self._get_historical_fmp_sync, fetch_symbol, period, interval)
                elif provider == APIProvider.TWELVE_DATA:
                    df = await self._call_blocking_with_retries(self._get_historical_twelve_data_sync, fetch_symbol, period, interval)
                elif provider == APIProvider.YFINANCE:
                    df = await self._call_blocking_with_retries(self._get_historical_yfinance_sync, fetch_symbol, period, interval)
                elif provider == APIProvider.FINNHUB:
                    df = None
                else:
                    df = None
                if df is not None and not df.empty:
                    self._cb_record_success(provider)
                    if max_bars and interval == "1d":
                        df = df.head(max_bars)
                    ttl = 300 if interval in ("1m", "5m") else 3600
                    try:
                        rw = r if r is not None else await self._infra._get_redis()
                        await rw.setex(cache_key, ttl, df.to_json(orient="index"))
                        try:
                            _date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                            _counter_name = "twelvedata" if provider == APIProvider.TWELVE_DATA else provider.value
                            await rw.hincrby(f"provider:calls:{_date_key}", _counter_name, 1)
                            await rw.expire(f"provider:calls:{_date_key}", 86400 * 30)
                        except Exception:
                            logger.debug("Redis provider call counter increment failed")
                    except Exception as l3_cache_exc:
                        logger.warning(
                            "Redis L3 cache write for %s failed (non-blocking): %s",
                            symbol,
                            l3_cache_exc,
                        )
                    if not skip_write_through:
                        def _persist_in_thread():
                            _session = SessionLocal()
                            try:
                                self._pbw.persist_price_bars(
                                    _session, symbol, df,
                                    interval=interval,
                                    data_source=provider_used or "provider",
                                )
                            finally:
                                _session.close()

                        try:
                            await asyncio.to_thread(_persist_in_thread)
                        except Exception as persist_exc:
                            logger.warning("Write-through persist_price_bars for %s failed (non-blocking): %s", symbol, persist_exc)
                    if return_provider:
                        return df, provider_used
                    return df
            except Exception as exc:
                self._cb_record_failure(provider)
                logger.warning("Provider %s failed for %s (%s/%s): %s", provider.value, symbol, period, interval, exc)
                continue
        return (None, provider_used) if return_provider else None

    # ---------------------- Provider-specific fetchers ----------------------

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
        """Fetch intraday 5m bars from FMP historical_chart."""
        data = fmpsdk.historical_chart(
            apikey=settings.FMP_API_KEY, symbol=symbol, interval="5min"
        )
        if isinstance(data, dict):
            msg = data.get("Error Message") or data.get("error") or data.get("message") or str(data)
            raise RuntimeError(f"FMP historical_chart error: {msg}")
        if not data or not isinstance(data, list):
            return None
        df = pd.DataFrame(data)
        if df.empty or "date" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        cols = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in cols if c in df.columns]]
        df.columns = ["Open", "High", "Low", "Close", "Volume"][: len(df.columns)]
        try:
            if isinstance(period, str) and period.endswith("d"):
                days = int(period[:-1])
                cutoff = pd.Timestamp.now("UTC") - pd.Timedelta(days=days)
                df = df[df.index >= cutoff]
        except Exception as e:
            logger.warning("period_filter failed for %s: %s", symbol, e)
        return df.sort_index(ascending=False)

    def _get_historical_twelve_data_sync(
        self, symbol: str, period: str, interval: str
    ) -> Optional[pd.DataFrame]:
        if not self._infra.twelve_data_client:
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
        ts = self._infra.twelve_data_client.time_series(
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
        self, symbol: str, period: str, interval: str, to_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        if interval != "1d":
            return None
        from datetime import date as _date
        days_map = {
            "5d": 10, "1mo": 30, "3mo": 90, "6mo": 180,
            "1y": 365, "2y": 730, "3y": 1095,
            "5y": 1850, "10y": 3700, "max": 36500,
        }
        delta = days_map.get(period, 365)
        from_date = (_date.today() - timedelta(days=delta)).isoformat()
        fmp_kwargs: Dict[str, Any] = {
            "apikey": settings.FMP_API_KEY,
            "symbol": symbol,
            "from_date": from_date,
        }
        if to_date:
            fmp_kwargs["to_date"] = to_date
        raw = fmpsdk.historical_price_full(**fmp_kwargs)
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

    def _fetch_fmp_historical_dividends_sync(self, symbol: str) -> List[Dict]:
        """Single FMP stock_dividend HTTP fetch; raises on transport or error payloads."""
        import requests

        url = (
            "https://financialmodelingprep.com/api/v3/historical-price-full/stock_dividend/"
            f"{symbol}?apikey={settings.FMP_API_KEY}"
        )
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"FMP dividend HTTP {resp.status_code}")
        data = resp.json()
        if isinstance(data, dict) and (
            data.get("Error Message") or data.get("error") or data.get("message")
        ):
            msg = data.get("Error Message") or data.get("error") or data.get("message")
            raise RuntimeError(f"FMP dividend error: {msg}")
        if not isinstance(data, dict):
            raise RuntimeError("FMP dividend unexpected payload type")
        historical = data.get("historical")
        if historical is None:
            return []
        if not isinstance(historical, list):
            raise RuntimeError("FMP dividend historical is not a list")
        return historical

    def get_historical_dividends(self, symbol: str) -> List[Dict]:
        """Fetch historical dividend payments from FMP for a given symbol."""
        if not settings.FMP_API_KEY:
            return []
        try:
            try:
                _r_sync = self._infra._sync_redis
                _date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                _current = int(_r_sync.hget(f"provider:calls:{_date_key}", "fmp") or 0)
                _budget = settings.provider_policy.fmp_daily_budget
                if _current >= _budget:
                    logger.warning(
                        "get_historical_dividends: FMP over daily budget (%d/%d), skipping %s",
                        _current,
                        _budget,
                        symbol,
                    )
                    return []
            except Exception as _budget_exc:
                logger.warning(
                    "Redis unavailable for FMP budget check, allowing dividend fetch for %s: %s",
                    symbol,
                    _budget_exc,
                )
            provider_rate_limiter.acquire_sync("fmp")
            historical = self._call_blocking_with_retries_sync(
                self._fetch_fmp_historical_dividends_sync, symbol
            )
            self._infra._record_provider_call_sync("fmp")
            return historical
        except Exception as e:
            logger.warning("FMP dividend fetch failed for %s: %s", symbol, e)
            return []
