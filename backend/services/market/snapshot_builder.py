from __future__ import annotations

import datetime as _pydt
import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import pandas as pd
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models import MarketSnapshot
from backend.models.market_data import (
    EarningsCalendarEvent,
    MarketRegime,
    PriceData,
    MarketSnapshotHistory,
)
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
from backend.services.market.dataframe_utils import (
    ensure_newest_first,
    ensure_oldest_first,
    price_data_rows_to_dataframe,
)
from backend.services.market.constants import FUNDAMENTAL_FIELDS
from backend.services.market.stage_utils import compute_stage_run_lengths
from backend.services.market.stage_quality_service import normalize_stage_label
from backend.services.market.snapshot_history_writer import upsert_snapshot_history_row
from backend.services.market.fundamentals_service import needs_fundamentals

if TYPE_CHECKING:
    from backend.services.market.provider_router import ProviderRouter
    from backend.services.market.quote_service import QuoteService
    from backend.services.market.fundamentals_service import FundamentalsService

logger = logging.getLogger(__name__)


def _earnings_utc_for_report_date(
    report_date: _pydt.date,
    time_of_day: Optional[str],
) -> datetime:
    """Map ``report_date`` + optional ``time_of_day`` to a UTC ``datetime``.

    - ``bmo`` / ``BMO``: 13:30 UTC (09:30 ET market open)
    - ``amc`` / ``AMC``: 21:00 UTC (17:00 ET market close)
    - Otherwise: end of UTC day so same-day rows stay future-dated for filters.
    """
    tod = (time_of_day or "").strip().lower()
    if tod == "bmo":
        return datetime.combine(
            report_date, time(13, 30), tzinfo=timezone.utc
        )
    if tod == "amc":
        return datetime.combine(
            report_date, time(21, 0), tzinfo=timezone.utc
        )
    return datetime.combine(
        report_date, time(23, 59, 59), tzinfo=timezone.utc
    )


def next_earnings_utc_from_calendar(db: Session, symbol: str) -> Optional[datetime]:
    """Earliest ``earnings_calendar.report_date`` on or after today (UTC), as a UTC time.

    Event time uses ``time_of_day`` (``bmo``/``amc``) or end-of-UTC-day so a
    same-day ``report_date`` is not materialized as midnight in the past.

    Returns ``None`` when the calendar has no future row for the symbol.
    """
    sym = (symbol or "").upper()
    if not sym:
        return None
    today = datetime.now(timezone.utc).date()
    row = (
        db.query(
            EarningsCalendarEvent.report_date,
            EarningsCalendarEvent.time_of_day,
        )
        .filter(
            EarningsCalendarEvent.symbol == sym,
            EarningsCalendarEvent.report_date >= today,
        )
        .order_by(EarningsCalendarEvent.report_date.asc())
        .first()
    )
    if row is None or row[0] is None:
        return None
    d, tod = row[0], row[1]
    return _earnings_utc_for_report_date(d, tod)


_STAGE_SNAPSHOT_FIELDS = (
    "stage_label", "stage_slope_pct", "stage_dist_pct",
    "ext_pct", "sma150_slope", "sma50_slope",
    "ema10_dist_pct", "ema10_dist_n", "vol_ratio",
    "rs_mansfield_pct",
    "atre_promoted", "pass_count", "action_override", "manual_review",
)


class SnapshotBuilder:
    """Snapshot computation, persistence, stage run derivation, and related helpers."""

    def __init__(self, provider_router: "ProviderRouter", quote: "QuoteService", fundamentals: "FundamentalsService") -> None:
        self._provider = provider_router
        self._quote = quote
        self._fundamentals = fundamentals

    # ---------------------- Snapshot from DataFrame ----------------------

    def _snapshot_from_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Common snapshot builder used by DB and provider flows."""
        if df is None or df.empty or "Close" not in df.columns:
            return {}

        df_newest = ensure_newest_first(df)
        df_oldest = ensure_oldest_first(df_newest)

        price = float(df_newest["Close"].iloc[0])
        as_of_ts = None
        try:
            as_of_ts = (
                df_newest.index[0].to_pydatetime()
                if hasattr(df_newest.index[0], "to_pydatetime")
                else df_newest.index[0]
            )
        except Exception as e:
            logger.warning("snapshot as_of_ts from dataframe index failed: %s", e)
            as_of_ts = None

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
            except Exception as e:
                logger.debug("range_pos(%s) computation failed: %s", window, e)
                return None

        def atrx(ma_val: Optional[float]) -> Optional[float]:
            try:
                if ma_val is None or atr_14 is None or atr_14 == 0:
                    return None
                return float((price - float(ma_val)) / float(atr_14))
            except Exception as e:
                logger.debug("atrx computation failed: %s", e)
                return None

        snapshot: Dict[str, Any] = {
            "current_price": price,
            "as_of_timestamp": as_of_ts.isoformat() if hasattr(as_of_ts, "isoformat") else as_of_ts,
            "rsi": indicators.get("rsi"),
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
            # From ``compute_full_indicator_series`` (20d rolling volume mean; vol_ratio uses it)
            "volume_avg_20d": indicators.get("volume_avg_20d"),
            "vol_ratio": indicators.get("vol_ratio"),
        }

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

    # ---------------------- Stage helpers ----------------------

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

        if latest_history_row is not None:
            latest_stage_norm = self._normalize_stage_label(
                getattr(latest_history_row, "stage_label", None)
            )
            latest_days_raw = getattr(latest_history_row, "current_stage_days", None)
            try:
                latest_days = int(latest_days_raw) if latest_days_raw is not None else None
            except Exception as e:
                logger.warning(
                    "derive_stage_run_fields: invalid current_stage_days on history row: %s",
                    e,
                )
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
                pass
            elif latest_stage_norm in (None, "UNKNOWN") and not has_normalized_prior:
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

    # ---------------------- Snapshot CRUD ----------------------

    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Return the latest technical snapshot for a symbol.

        Flow: stored -> DB compute -> provider compute -> persist
        """
        session = SessionLocal()
        try:
            snap = self.get_snapshot_from_store(session, symbol)
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
        """Fetch freshest snapshot from MarketSnapshot if not expired."""
        now = datetime.now(timezone.utc)
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
        exp_utc: datetime | None = None
        try:
            if exp is not None:
                exp_utc = (
                    exp.replace(tzinfo=timezone.utc)
                    if exp.tzinfo is None
                    else exp.astimezone(timezone.utc)
                )
        except Exception as e:
            logger.warning("expiry_tz_normalize failed for %s: %s", symbol, e)
        if exp_utc is not None and exp_utc < now:
            return {}
        try:
            if isinstance(row.raw_analysis, dict) and row.raw_analysis:
                return dict(row.raw_analysis)
        except Exception as e:
            logger.warning("raw_analysis_parse failed for %s: %s", symbol, e)
        out: Dict[str, Any] = {
            "current_price": getattr(row, "current_price", None),
            "as_of_timestamp": getattr(row, "as_of_timestamp", None),
            "rsi": getattr(row, "rsi", None),
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
        recompute_metrics: dict[str, int] | None = None,
    ) -> Dict[str, Any]:
        """Compute a snapshot purely from local PriceData (and enrich it)."""
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
        df = price_data_rows_to_dataframe(rows, ascending=False)
        snapshot = self._snapshot_from_dataframe(df)
        if not snapshot:
            return {}
        try:
            as_of_ts = df.index.max()
            if as_of_ts is not None:
                snapshot["as_of_timestamp"] = (
                    as_of_ts.isoformat() if hasattr(as_of_ts, "isoformat") else str(as_of_ts)
                )
        except Exception as e:
            logger.warning("as_of_timestamp_extract failed for %s: %s", symbol, e)

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
                sym_newest = df.copy()
                bm_newest = bm_df.copy()

                _prior_row = (
                    db.query(MarketSnapshot)
                    .filter(
                        MarketSnapshot.symbol == symbol,
                        MarketSnapshot.analysis_type == "technical_snapshot",
                    )
                    .first()
                )
                _regime = getattr(_prior_row, "regime_state", None) or "R1"
                _prior_stage = getattr(_prior_row, "stage_label", None) or "UNKNOWN"
                _prior_atre = bool(getattr(_prior_row, "atre_promoted", False))
                _prior_pc = int(getattr(_prior_row, "pass_count", None) or 0)

                stage = compute_weinstein_stage_from_daily(
                    sym_newest, bm_newest,
                    regime_state=_regime,
                    prior_stage=_prior_stage,
                    prior_atre_promoted=_prior_atre,
                    prior_pass_count=_prior_pc,
                )
                if isinstance(stage, dict):
                    for _k in _STAGE_SNAPSHOT_FIELDS:
                        _v = stage.get(_k)
                        if _v is not None:
                            snapshot[_k] = _v
                    lbl = snapshot.get("stage_label")
                    if lbl is not None:
                        snapshot["stage_4h"] = lbl
                        snapshot["stage_confirmed"] = True
                    try:
                        stage_prev = compute_weinstein_stage_from_daily(
                            sym_newest.iloc[5:].copy(),
                            bm_newest.iloc[5:].copy(),
                        )
                        if isinstance(stage_prev, dict) and stage_prev.get("stage_label") is not None:
                            snapshot["stage_label_5d_ago"] = stage_prev.get("stage_label")
                    except Exception as e:
                        logger.warning("stage_label_5d_ago failed for %s: %s", symbol, e)
                try:
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
                        except Exception as e:
                            logger.debug(
                                "snapshot_as_of_dt parse failed for %s: %s", symbol, e
                            )
                            snapshot_as_of_dt = None

                    hist_q = (
                        db.query(MarketSnapshotHistory)
                        .filter(
                            MarketSnapshotHistory.symbol == symbol,
                            MarketSnapshotHistory.analysis_type == "technical_snapshot",
                        )
                    )
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
                        prev_utc = (
                            prev_ts.replace(tzinfo=timezone.utc)
                            if prev_ts.tzinfo is None
                            else prev_ts.astimezone(timezone.utc)
                        )
                        age = datetime.now(timezone.utc) - prev_utc
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
                info = self._fundamentals.get_fundamentals_info(symbol)
                for k in FUNDAMENTAL_FIELDS:
                    if info.get(k) is not None:
                        snapshot[k] = info.get(k)
            except Exception as e:
                logger.warning("fundamentals_fetch failed for %s: %s", symbol, e)

        # ``MarketRegime`` is authoritative for regime_state. Pulling it here keeps
        # every fresh snapshot row stamped with the real regime from the regime engine
        # rather than inheriting whatever the prior snapshot row had (which, if that
        # prior row was itself built before the regime engine ran, would be stale).
        # Scan overlay also updates this column post-build; this ensures the row is
        # correct at creation time, not just after the next scan_overlay tick.
        try:
            latest_regime = (
                db.query(MarketRegime)
                .order_by(MarketRegime.as_of_date.desc())
                .first()
            )
            if latest_regime is not None and getattr(latest_regime, "regime_state", None):
                snapshot["regime_state"] = latest_regime.regime_state
                if recompute_metrics is not None:
                    recompute_metrics["regime_state_written"] = (
                        recompute_metrics.get("regime_state_written", 0) + 1
                    )
            else:
                if recompute_metrics is not None:
                    recompute_metrics["regime_state_missing"] = (
                        recompute_metrics.get("regime_state_missing", 0) + 1
                    )
        except Exception as e:
            logger.warning(
                "latest_market_regime_lookup failed for %s: %s: %s",
                symbol,
                type(e).__name__,
                e,
            )
            if recompute_metrics is not None:
                recompute_metrics["regime_state_lookup_errors"] = (
                    recompute_metrics.get("regime_state_lookup_errors", 0) + 1
                )

        # ``earnings_calendar`` is authoritative for next_earnings (overrides FMP / stale copy).
        try:
            cal_ne: Optional[datetime] = next_earnings_utc_from_calendar(db, symbol)
            snapshot["next_earnings"] = cal_ne
            if recompute_metrics is not None:
                if cal_ne is not None:
                    recompute_metrics["earnings_written"] = (
                        recompute_metrics.get("earnings_written", 0) + 1
                    )
                else:
                    recompute_metrics["earnings_missing"] = (
                        recompute_metrics.get("earnings_missing", 0) + 1
                    )
        except Exception as e:
            logger.warning(
                "next_earnings_calendar_lookup failed for %s: %s: %s",
                symbol,
                type(e).__name__,
                e,
            )
            if recompute_metrics is not None:
                recompute_metrics["earnings_lookup_errors"] = (
                    recompute_metrics.get("earnings_lookup_errors", 0) + 1
                )
        return snapshot

    async def compute_snapshot_from_providers(self, symbol: str) -> Dict[str, Any]:
        """Compute a snapshot from provider OHLCV when DB path is missing (slow-path fallback)."""
        data = await self._provider.get_historical_data(symbol, period="1y", interval="1d")
        if data is None or data.empty:
            price_only = await self._quote.get_current_price(symbol)
            return {"current_price": float(price_only)} if price_only else {}

        snapshot = self._snapshot_from_dataframe(data)
        if not snapshot:
            return {}

        try:
            bm_df = await self._provider.get_historical_data("SPY", period="1y", interval="1d")
            if bm_df is not None and not bm_df.empty:
                stage = compute_weinstein_stage_from_daily(data, bm_df)
                if isinstance(stage, dict):
                    for _k in _STAGE_SNAPSHOT_FIELDS:
                        _v = stage.get(_k)
                        if _v is not None:
                            snapshot[_k] = _v
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
            funda = self._fundamentals.get_fundamentals_info(symbol)
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
        """Persist latest snapshot and append to immutable history."""
        if not snapshot:
            raise ValueError("empty snapshot")
        now = datetime.now(timezone.utc)
        expiry = now + pd.Timedelta(hours=ttl_hours)

        from datetime import timezone as _tz, time as _time

        as_of_ts: datetime | None = None
        raw_as_of = snapshot.get("as_of_timestamp")
        try:
            if isinstance(raw_as_of, datetime):
                as_of_ts = raw_as_of
            elif isinstance(raw_as_of, str) and raw_as_of.strip():
                s = raw_as_of.strip()
                if s.endswith("Z"):
                    as_of_ts = datetime.fromisoformat(s.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(s)
                    as_of_ts = dt if dt.tzinfo else dt.replace(tzinfo=_tz.utc)
        except Exception as e:
            logger.warning(
                "persist_snapshot as_of_timestamp parse failed for %s: %s", symbol, e
            )
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
                    as_of_ts = as_of_ts.replace(tzinfo=_tz.utc)
            except Exception as e:
                logger.warning(
                    "persist_snapshot DB fallback as_of_timestamp failed for %s: %s",
                    symbol,
                    e,
                )
                as_of_ts = None

        snapshot_json = dict(snapshot)
        if isinstance(as_of_ts, datetime):
            snapshot_json["as_of_timestamp"] = as_of_ts.replace(tzinfo=None).isoformat()
        # JSON column does not accept ``datetime``; every datetime value in the
        # snapshot dict (e.g. ``next_earnings`` from the earnings calendar) must
        # be serialized to an ISO string before write. The typed column copy
        # below still gets the raw ``datetime``.
        for _k, _v in list(snapshot_json.items()):
            if isinstance(_v, datetime):
                snapshot_json[_k] = _v.isoformat()

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
            row.analysis_timestamp = datetime.now(timezone.utc)
            for k, v in snapshot.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            if as_of_ts is not None and hasattr(row, "as_of_timestamp"):
                row.as_of_timestamp = as_of_ts
            db.add(row)
        else:
            row.analysis_timestamp = datetime.now(timezone.utc)
            row.expiry_timestamp = expiry
            row.raw_analysis = snapshot_json
            for k, v in snapshot.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            if as_of_ts is not None and hasattr(row, "as_of_timestamp"):
                row.as_of_timestamp = as_of_ts

        if as_of_ts is not None:
            as_of_date = datetime.combine(as_of_ts.date(), _time.min)
            upsert_snapshot_history_row(
                db,
                symbol,
                as_of_date,
                snapshot_json,
                analysis_type=analysis_type,
            )
        db.flush()
        if auto_commit:
            db.commit()
        return row

    # ---------------------- High-level helpers ----------------------

    async def build_indicator_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Build a technical snapshot from provider OHLCV with indicators."""
        return await self.compute_snapshot_from_providers(symbol)

    async def get_weinstein_stage(self, symbol: str, benchmark: str = "SPY") -> Dict[str, Any]:
        """Compute Weinstein stage by fetching daily series for symbol and a benchmark."""
        sym_df = await self._provider.get_historical_data(symbol, period="1y", interval="1d")
        bm_df = await self._provider.get_historical_data(benchmark, period="1y", interval="1d")
        try:
            return compute_weinstein_stage_from_daily(sym_df, bm_df)
        except Exception as e:
            logger.warning(
                "get_weinstein_stage failed for %s vs %s: %s", symbol, benchmark, e
            )
            return {"stage": "UNKNOWN"}

    async def get_technical_analysis(self, symbol: str) -> Dict[str, Any]:
        """Compatibility wrapper — returns the latest snapshot."""
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
            except Exception as e:
                logger.debug("get_tracked_details _to_float failed: %s", e)
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
            if entry.get("current_price") is None and price_map.get(sym):
                entry["current_price"] = _to_float(price_map.get(sym))
        return details
