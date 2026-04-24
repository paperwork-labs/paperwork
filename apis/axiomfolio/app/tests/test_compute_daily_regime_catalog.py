"""
Coverage for the `compute_daily_regime` JobTemplate added to the catalog
as a standalone scheduled job (not only via the nightly DAG).

Why this matters
----------------

Before this catalog entry, regime computation only ran as a step inside
the nightly DAG bootstrap (`admin_coverage_backfill` at 01:00 UTC).
When that DAG failed partway, the day's `MarketRegime` row was never
written and:

  - the `regime` SystemStatus dimension stayed red until next midnight,
  - exit-cascade evaluation made decisions against a stale regime,
  - intelligence briefs went out without that day's regime context.

Adding a standalone catalog entry at 03:20 UTC (after fundamentals fill
at 03:15 and before earnings sync at 03:30) acts as a safety net.  This
test guards the contract.
"""
from __future__ import annotations

from celery.schedules import crontab

from app.tasks.celery_app import _build_beat_schedule
from app.tasks.job_catalog import CATALOG, JobTemplate


def _by_id(job_id: str) -> JobTemplate:
    matches = [j for j in CATALOG if j.id == job_id]
    assert matches, f"JobTemplate id={job_id!r} not in CATALOG"
    assert len(matches) == 1, f"Duplicate JobTemplate id={job_id!r}"
    return matches[0]


def test_compute_daily_regime_template_exists_and_is_wired_correctly():
    job = _by_id("compute_daily_regime")

    # The Celery task name must match the actual @shared_task in
    # app/tasks/market/regime.py — auto-generated as
    # `<module>.<function>` because no explicit name= is set.
    assert job.task == "app.tasks.market.regime.compute_daily"

    # Cron is intentionally `'20 3 * * *'` — see job_catalog comment.
    assert job.default_cron == "20 3 * * *"
    assert job.default_tz == "UTC"

    # Must match the @task_run("compute_daily_regime") label used by
    # the JobRun lookup in the Admin → Jobs panel and pipeline DAG.
    assert job.job_run_label == "compute_daily_regime"

    # Timeout must not exceed the task's hard time_limit (180s in
    # regime.py); allow equal so it isn't artificially capped low.
    assert job.timeout_s <= 180

    assert job.enabled is True
    assert job.group == "market_data"


def test_compute_daily_regime_lands_in_beat_schedule_with_correct_crontab():
    schedule = _build_beat_schedule()
    assert "compute_daily_regime" in schedule, (
        "compute_daily_regime template did not produce a beat entry — "
        "check JobTemplate.enabled and the cron parser in celery_app._build_beat_schedule"
    )

    entry = schedule["compute_daily_regime"]
    assert entry["task"] == "app.tasks.market.regime.compute_daily"

    expected = crontab(minute="20", hour="3", day_of_week="*", day_of_month="*", month_of_year="*")
    actual = entry["schedule"]
    # crontab.__eq__ is well-defined; compare directly.
    assert actual == expected, (
        f"compute_daily_regime cron mismatch: expected {expected!r}, got {actual!r}"
    )


def test_compute_daily_regime_does_not_collide_with_neighbors():
    """Sanity: the regime job must not share a minute slot with other
    market_data jobs that contend for the same worker resources."""
    by_cron = {}
    for job in CATALOG:
        if job.group != "market_data" or not job.enabled:
            continue
        by_cron.setdefault(job.default_cron, []).append(job.id)

    regime_neighbors = by_cron.get("20 3 * * *", [])
    assert regime_neighbors == ["compute_daily_regime"], (
        f"03:20 UTC slot is shared with: {regime_neighbors!r}; pick a different minute"
    )
