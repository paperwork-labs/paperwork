from __future__ import annotations

from typing import Any, Dict
from datetime import datetime


def _expected_latest_trading_day():
    """Return the most recent completed NYSE trading session date string.

    Uses exchange_calendars if available, falls back to simple weekday logic.
    """
    try:
        import exchange_calendars as xcals
        import pandas as pd
        from datetime import datetime
        from zoneinfo import ZoneInfo

        nyse = xcals.get_calendar("XNYS")
        today = pd.Timestamp.now(tz="UTC").normalize()
        et_now = datetime.now(ZoneInfo("America/New_York"))
        schedule = nyse.sessions_in_range(today - pd.Timedelta(days=10), today)
        if et_now.hour < 16:
            closed = schedule[schedule < today]
        else:
            closed = schedule[schedule <= today]
        if len(closed) > 0:
            return closed[-1].strftime("%Y-%m-%d")
    except Exception:
        pass
    # Fallback: simple weekday logic
    from datetime import date, timedelta
    d = date.today()
    if d.weekday() == 0:
        d -= timedelta(days=3)
    elif d.weekday() == 6:
        d -= timedelta(days=2)
    else:
        d -= timedelta(days=1)
    return d.isoformat()


def compute_coverage_status(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Derive human-readable coverage state + KPI percentages from a raw snapshot."""
    total_symbols = int(snapshot.get("symbols") or 0)
    tracked = int(snapshot.get("tracked_count") or 0)

    daily = snapshot.get("daily", {}) or {}
    m5 = snapshot.get("m5", {}) or {}
    daily_count = int(daily.get("count") or 0)
    m5_count = int(m5.get("count") or 0)
    # Stale counts should reflect the full universe, not just the sampled `stale` lists.
    daily_freshness = daily.get("freshness") or {}
    m5_freshness = m5.get("freshness") or {}
    stale_daily = int(daily.get("stale_48h") or daily_freshness.get(">48h") or 0) + int(
        daily.get("missing") or daily_freshness.get("none") or 0
    )
    stale_m5 = int(m5.get("stale_48h") or m5_freshness.get(">48h") or 0) + int(
        m5.get("missing") or m5_freshness.get("none") or 0
    )
    # Fall back to list lengths only if no aggregate counts are available.
    if stale_daily == 0 and not daily_freshness and daily.get("stale"):
        stale_daily = len(daily.get("stale") or [])
    if stale_m5 == 0 and not m5_freshness and m5.get("stale"):
        stale_m5 = len(m5.get("stale") or [])

    # If 5m backfill is explicitly disabled, 5m coverage should be informational only
    # and must not drive degraded/warning states.
    meta = snapshot.get("meta", {}) or {}
    backfill_5m_enabled = meta.get("backfill_5m_enabled")
    if backfill_5m_enabled is None:
        backfill_5m_enabled = snapshot.get("backfill_5m_enabled")
    backfill_5m_enabled = True if backfill_5m_enabled is None else bool(backfill_5m_enabled)

    def pct(count: int) -> float:
        return round((count / total_symbols) * 100.0, 1) if total_symbols else 0.0

    # Trading-day aware daily %:
    # Prefer the latest observed trading day in daily.fill_by_date (based on stored OHLCV rows),
    # and compute % as-of that date. This avoids false "degraded" on weekends/holidays.
    expected_daily_date = None
    expected_daily_pct = None
    missing_latest = None
    try:
        series = list(daily.get("fill_by_date") or [])
        # entries are like: {date: "YYYY-MM-DD", symbol_count: n, pct_of_universe: x}
        series = [r for r in series if isinstance(r, dict) and r.get("date")]
        if series:
            newest = max(series, key=lambda r: str(r.get("date")))
            expected_daily_date = str(newest.get("date"))
            expected_daily_pct = float(newest.get("pct_of_universe") or 0.0)
            # symbol_count is distinct symbols with a 1d bar on that date
            sc = int(newest.get("symbol_count") or 0)
            missing_latest = max(0, int(total_symbols) - sc) if total_symbols else 0
    except Exception:
        expected_daily_date = None
        expected_daily_pct = None
        missing_latest = None

    daily_pct = round(expected_daily_pct, 1) if isinstance(expected_daily_pct, (int, float)) else pct(daily_count)
    m5_pct = pct(m5_count)

    label = "ok"
    summary = "Coverage healthy across daily + 5m intervals."
    if total_symbols == 0:
        label = "idle"
        summary = "No symbols discovered yet. Run refresh + tracked tasks."
    if total_symbols > 0 and expected_daily_date is not None and missing_latest is not None:
        # “Green” means: everyone has the latest trading-day bar.
        if missing_latest > 0:
            label = "degraded"
            summary = f"{missing_latest} symbols missing daily bar for {expected_daily_date}."
        else:
            # Market-hours hint (computed in NY timezone, but stored timestamps remain UTC).
            try:
                from zoneinfo import ZoneInfo
                from datetime import timedelta, time as _time

                ny = ZoneInfo("America/New_York")
                now_ny = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).astimezone(ny)
                is_weekend = now_ny.weekday() >= 5
                open_t = _time(hour=9, minute=30)
                close_t = _time(hour=16, minute=0)
                is_open = (not is_weekend) and (open_t <= now_ny.time() <= close_t)
                close_dt = datetime.combine(now_ny.date(), close_t, tzinfo=ny)
                within_grace = (not is_weekend) and (now_ny >= close_dt) and (now_ny <= close_dt + timedelta(hours=18))
                if not is_open:
                    hint = "Market closed" if not within_grace else "Market closed (within close grace)"
                    summary = f"{hint}. Daily coverage is green (latest bar {expected_daily_date})."
                else:
                    summary = f"Daily coverage is green (latest bar {expected_daily_date})."
            except Exception:
                summary = f"Daily coverage is green (latest bar {expected_daily_date})."
    elif total_symbols > 0 and daily_pct < 90:
        label = "degraded"
        summary = f"Daily coverage {daily_pct}% below 90% SLA."
    elif stale_daily:
        # Fallback to legacy bucket-based stale counts if fill_by_date isn't present.
        label = "degraded"
        none_n = int((daily.get("freshness") or {}).get("none") or daily.get("missing") or 0)
        summary = (
            f"{stale_daily} symbols have daily bars older than 48h."
            if none_n == 0
            else f"{stale_daily} symbols have daily bars older than 48h or missing."
        )
    elif backfill_5m_enabled:
        if m5_pct == 0 and total_symbols:
            label = "degraded"
            summary = "5m coverage is 0% – run intraday backfill."
        elif stale_m5:
            label = "warning"
            summary = f"{stale_m5} symbols missing 5m data."

    return {
        "label": label,
        "summary": summary,
        "daily_pct": daily_pct,
        "m5_pct": m5_pct,
        "stale_daily": int(missing_latest) if isinstance(missing_latest, int) else stale_daily,
        "stale_m5": stale_m5,
        "symbols": total_symbols,
        "tracked_count": tracked,
        "thresholds": {
            "daily_pct": 100,
            "m5_expectation": ">=1 refresh/day" if backfill_5m_enabled else "ignored (disabled by admin)",
        },
        "daily_expected_date": expected_daily_date,
    }
