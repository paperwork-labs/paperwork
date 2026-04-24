"""Backfill parameter helpers.

We expose operator-facing knobs like `days` (roughly "trading days of coverage desired"),
but providers don't support "last N trading days" directly. We therefore:

- choose a coarse provider `period` (calendar range) when the provider supports it (e.g. yfinance)
- always apply a hard `max_bars` bound to the returned dataframe so downstream compute is stable
- include a buffer so indicators like SMA200 (and other rolling windows) have enough history

medallion: silver
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DailyBackfillParams:
    days: int
    period: str
    max_bars: int
    buffer_bars: int


def daily_backfill_params(
    *,
    days: int | None,
    default_days: int = 200,
    min_bars: int = 270,
    buffer_bars: int = 70,
) -> DailyBackfillParams:
    """Return provider request params for daily OHLCV backfills.

    Notes:
    - `days` is interpreted as "roughly trading days", not calendar days.
    - `period` is a provider request hint (calendar range). Providers differ:
      - yfinance honors period strings like "1y", "2y", "5y", "max"
      - FMP daily historical endpoint returns its full history; period is effectively ignored
      - TwelveData uses outputsize; period is effectively ignored
    - `max_bars` is always enforced after fetch (newest-first), so behavior is consistent.
    """
    d = int(days or 0)
    if d <= 0:
        d = int(default_days)

    buf = max(0, int(buffer_bars))
    max_bars = max(int(min_bars), d + buf)

    if max_bars <= 45:
        period = "1mo"
    elif max_bars <= 130:
        period = "3mo"
    elif max_bars <= 210:
        period = "6mo"
    elif max_bars <= 270:
        period = "1y"
    elif max_bars <= 540:
        period = "2y"
    elif max_bars <= 1260:
        period = "5y"
    else:
        period = "max"

    return DailyBackfillParams(days=d, period=period, max_bars=max_bars, buffer_bars=buf)
