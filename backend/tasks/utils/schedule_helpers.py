from __future__ import annotations

from typing import Optional

from celery.schedules import crontab


def build_crontab_schedule(
    *,
    minute: str,
    hour: str,
    day_of_month: str,
    month_of_year: str,
    day_of_week: str,
    timezone: Optional[str] = "UTC",
):
    """
    Create a crontab schedule that tolerates Celery versions with differing tz kwargs.

    Celery <5 uses ``tz`` while newer builds accept ``timezone``; some builds reject both.
    This helper tries both keyword styles, then falls back to mutating the schedule's ``tz``
    attribute so tests and runtime behave consistently.
    """

    tz_value = timezone or "UTC"
    base_kwargs = {
        "minute": minute,
        "hour": hour,
        "day_of_month": day_of_month,
        "month_of_year": month_of_year,
        "day_of_week": day_of_week,
    }
    for key in ("tz", "timezone"):
        try:
            return crontab(**base_kwargs, **{key: tz_value})
        except TypeError:
            continue
    schedule = crontab(**base_kwargs)
    if hasattr(schedule, "tz"):
        try:
            schedule.tz = tz_value
        except Exception:
            pass
    return schedule


__all__ = ["build_crontab_schedule"]


