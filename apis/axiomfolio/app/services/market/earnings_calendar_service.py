"""Earnings calendar service — FMP premium with yfinance fallback.

Fetches upcoming earnings dates, EPS/revenue estimates, and actuals.
FMP v3/earning_calendar is premium-only; when unavailable (free tier or
key missing), falls back to yfinance Ticker.calendar per symbol.

medallion: silver
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import requests
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models.market_data import EarningsCalendarEvent
from app.services.market.rate_limiter import provider_rate_limiter

logger = logging.getLogger(__name__)


@dataclass
class EarningsEvent:
    """In-memory DTO for an earnings event before persistence."""

    symbol: str
    report_date: date
    fiscal_period: str | None = None
    estimate_eps: Decimal | None = None
    actual_eps: Decimal | None = None
    estimate_revenue: Decimal | None = None
    actual_revenue: Decimal | None = None
    time_of_day: str = "unknown"  # bmo | amc | unknown
    source: str = "unknown"


def _safe_decimal(val: object) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _normalize_time_of_day(raw: str | None) -> str:
    if not raw:
        return "unknown"
    lower = raw.strip().lower()
    if lower in ("bmo", "before market open", "before market"):
        return "bmo"
    if lower in ("amc", "after market close", "after market"):
        return "amc"
    return "unknown"


class EarningsCalendarService:
    """Earnings calendar with tiered provider fallback."""

    def get_earnings_calendar(
        self,
        db: Session,
        from_date: date | None = None,
        to_date: date | None = None,
        symbols: list[str] | None = None,
    ) -> list[dict]:
        """Query persisted earnings events, optionally filtered by date range and symbols."""
        q = db.query(EarningsCalendarEvent)
        if from_date:
            q = q.filter(EarningsCalendarEvent.report_date >= from_date)
        if to_date:
            q = q.filter(EarningsCalendarEvent.report_date <= to_date)
        if symbols:
            upper = [s.upper() for s in symbols]
            q = q.filter(EarningsCalendarEvent.symbol.in_(upper))
        rows = q.order_by(EarningsCalendarEvent.report_date.asc()).all()
        return [_row_to_dict(r) for r in rows]

    def sync_earnings(
        self,
        db: Session,
        symbols: list[str],
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        """Fetch from best available provider and upsert into DB.

        Returns counters: {source, fetched, upserted, errors}.
        """
        if from_date is None:
            from_date = date.today() - timedelta(days=7)
        if to_date is None:
            to_date = date.today() + timedelta(days=90)

        events: list[EarningsEvent] = []
        source = "none"

        if self._fmp_available():
            try:
                events = self._fetch_from_fmp(from_date, to_date)
                source = "fmp"
                if symbols:
                    upper = {s.upper() for s in symbols}
                    events = [e for e in events if e.symbol in upper]
                logger.info(
                    "FMP earnings: fetched %d events (%s to %s)",
                    len(events),
                    from_date,
                    to_date,
                )
            except Exception as exc:
                logger.warning("FMP earnings fetch failed, falling back to yfinance: %s", exc)
                events = []

        if not events and symbols:
            try:
                events = self._fetch_from_yfinance(symbols)
                source = "yfinance"
                logger.info(
                    "yfinance earnings: fetched %d events for %d symbols", len(events), len(symbols)
                )
            except Exception as exc:
                logger.warning("yfinance earnings fetch failed: %s", exc)

        upserted = 0
        errors = 0
        for ev in events:
            try:
                with db.begin_nested():
                    self._upsert_event(db, ev)
                upserted += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    "Failed to upsert earnings for %s %s: %s", ev.symbol, ev.report_date, exc
                )

        if upserted:
            db.commit()

        return {
            "source": source,
            "fetched": len(events),
            "upserted": upserted,
            "errors": errors,
        }

    # ── Provider checks ──────────────────────────────────────────

    @staticmethod
    def _fmp_available() -> bool:
        """FMP earnings calendar requires a premium key and paid/unlimited tier."""
        if not settings.FMP_API_KEY:
            return False
        tier = settings.MARKET_PROVIDER_POLICY.strip().lower()
        return tier in ("paid", "unlimited")

    # ── FMP ──────────────────────────────────────────────────────

    def _fetch_from_fmp(self, from_date: date, to_date: date) -> list[EarningsEvent]:
        """FMP /v3/earning_calendar endpoint (premium only)."""
        provider_rate_limiter.acquire_sync("fmp")

        url = (
            f"https://financialmodelingprep.com/api/v3/earning_calendar"
            f"?from={from_date.isoformat()}&to={to_date.isoformat()}"
            f"&apikey={settings.FMP_API_KEY}"
        )
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"FMP earning_calendar HTTP {resp.status_code}")

        data = resp.json()
        if isinstance(data, dict) and (data.get("Error Message") or data.get("error")):
            msg = data.get("Error Message") or data.get("error")
            raise RuntimeError(f"FMP earning_calendar error: {msg}")

        if not isinstance(data, list):
            raise RuntimeError(
                f"FMP earning_calendar unexpected payload type: {type(data).__name__}"
            )

        events: list[EarningsEvent] = []
        for item in data:
            symbol = (item.get("symbol") or "").upper()
            raw_date = item.get("date")
            if not symbol or not raw_date:
                continue
            try:
                report_dt = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue

            events.append(
                EarningsEvent(
                    symbol=symbol,
                    report_date=report_dt,
                    fiscal_period=item.get("fiscalDateEnding"),
                    estimate_eps=_safe_decimal(item.get("epsEstimated")),
                    actual_eps=_safe_decimal(item.get("eps")),
                    estimate_revenue=_safe_decimal(item.get("revenueEstimated")),
                    actual_revenue=_safe_decimal(item.get("revenue")),
                    time_of_day=_normalize_time_of_day(item.get("time")),
                    source="fmp",
                )
            )
        return events

    # ── yfinance ─────────────────────────────────────────────────

    def _fetch_from_yfinance(self, symbols: list[str]) -> list[EarningsEvent]:
        """yfinance Ticker.calendar property (always free)."""
        events: list[EarningsEvent] = []
        for sym in symbols:
            provider_rate_limiter.acquire_sync("yfinance")
            try:
                ticker = yf.Ticker(sym)
                cal = ticker.calendar
                if cal is None or (hasattr(cal, "empty") and cal.empty):
                    continue
                earnings_dates = self._extract_yf_dates(cal)
                for dt in earnings_dates:
                    events.append(
                        EarningsEvent(
                            symbol=sym.upper(),
                            report_date=dt,
                            source="yfinance",
                        )
                    )
            except Exception as exc:
                logger.warning("yfinance calendar failed for %s: %s", sym, exc)
        return events

    @staticmethod
    def _extract_yf_dates(cal: object) -> list[date]:
        """Parse earnings dates from yfinance calendar (dict or DataFrame)."""
        dates: list[date] = []
        if isinstance(cal, dict):
            raw = cal.get("Earnings Date", [])
            if not isinstance(raw, (list, tuple)):
                raw = [raw]
            for d in raw:
                parsed = _parse_date(d)
                if parsed:
                    dates.append(parsed)
        else:
            import pandas as pd

            if isinstance(cal, pd.DataFrame):
                if "Earnings Date" in cal.columns:
                    for d in cal["Earnings Date"]:
                        parsed = _parse_date(d)
                        if parsed:
                            dates.append(parsed)
                elif "Earnings Date" in cal.index:
                    row = cal.loc["Earnings Date"]
                    for d in (
                        row if hasattr(row, "__iter__") and not isinstance(row, str) else [row]
                    ):
                        parsed = _parse_date(d)
                        if parsed:
                            dates.append(parsed)
        return dates

    # ── Persistence ──────────────────────────────────────────────

    @staticmethod
    def _upsert_event(db: Session, ev: EarningsEvent) -> None:
        """Upsert a single earnings event using ON CONFLICT (Postgres)."""
        stmt = pg_insert(EarningsCalendarEvent).values(
            symbol=ev.symbol,
            report_date=ev.report_date,
            fiscal_period=ev.fiscal_period or "N/A",
            estimate_eps=ev.estimate_eps,
            actual_eps=ev.actual_eps,
            estimate_revenue=ev.estimate_revenue,
            actual_revenue=ev.actual_revenue,
            time_of_day=ev.time_of_day,
            source=ev.source,
            fetched_at=datetime.now(UTC),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_earnings_sym_date_period",
            set_={
                "estimate_eps": stmt.excluded.estimate_eps,
                "actual_eps": stmt.excluded.actual_eps,
                "estimate_revenue": stmt.excluded.estimate_revenue,
                "actual_revenue": stmt.excluded.actual_revenue,
                "time_of_day": stmt.excluded.time_of_day,
                "source": stmt.excluded.source,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        db.execute(stmt)


def _parse_date(val: object) -> date | None:
    """Best-effort parse of a date-like value into a date object."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        import pandas as pd

        if isinstance(val, pd.Timestamp):
            return val.date()
    except ImportError:
        pass
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%b %d, %Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


def _row_to_dict(row: EarningsCalendarEvent) -> dict:
    """Serialize an ORM row to a JSON-safe dict."""
    return {
        "id": row.id,
        "symbol": row.symbol,
        "report_date": row.report_date.isoformat() if row.report_date else None,
        "fiscal_period": row.fiscal_period,
        "estimate_eps": float(row.estimate_eps) if row.estimate_eps is not None else None,
        "actual_eps": float(row.actual_eps) if row.actual_eps is not None else None,
        "estimate_revenue": float(row.estimate_revenue)
        if row.estimate_revenue is not None
        else None,
        "actual_revenue": float(row.actual_revenue) if row.actual_revenue is not None else None,
        "time_of_day": row.time_of_day,
        "source": row.source,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }


earnings_calendar_service = EarningsCalendarService()
