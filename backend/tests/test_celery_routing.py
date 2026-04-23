"""Verify Celery task routing splits heavy and fast queues correctly.

Background: production v0 ran a single worker with concurrency=1. A single
``repair_stage_history`` job would block the worker for an hour, starving
dashboard warming and triggering the "Queued but never started" failure
mode (regression R36).

This test guards the routing rules in ``backend/tasks/celery_app.py`` so a
future contributor cannot accidentally route a long-running job to the
fast queue, or remove the heavy queue entirely.
"""
from __future__ import annotations

from backend.tasks.celery_app import celery_app


def _route(task_name: str) -> str:
    """Return the queue name a task would be routed to."""
    routes = celery_app.conf.task_routes or {}
    for pattern, target in routes.items():
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            if task_name == prefix or task_name.startswith(prefix + "."):
                return target.get("queue", "celery")
        elif pattern == task_name:
            return target.get("queue", "celery")
    return "celery"


def test_heavy_queue_is_declared():
    queue_names = {q.name for q in celery_app.conf.task_queues}
    assert "heavy" in queue_names, "heavy queue must be declared so axiomfolio-worker-heavy can consume it"
    assert "celery" in queue_names
    assert "account_sync" in queue_names
    assert "orders" in queue_names


def test_known_long_running_market_tasks_route_to_heavy():
    long_running = [
        "backend.tasks.market.history.snapshot_last_n_days",
        "backend.tasks.market.history.snapshot_for_date",
        "backend.tasks.market.history.snapshot_for_symbol",
        "backend.tasks.market.history.repair_stage_history_async",
        "backend.tasks.market.fundamentals.fill_missing",
        "backend.tasks.market.fundamentals.refresh_stale",
        "backend.tasks.market.fundamentals.enrich_index",
        "backend.tasks.market.intraday.bars_5m_symbols",
        "backend.tasks.market.intraday.bars_5m_last_n_days",
        "backend.tasks.market.backfill.symbols",
        "backend.tasks.market.backfill.daily_bars",
        "backend.tasks.market.backfill.daily_since",
        "backend.tasks.market.reconciliation.spot_check",
    ]
    for task in long_running:
        assert _route(task) == "heavy", f"{task} must route to the heavy queue"


def test_short_running_tasks_stay_off_heavy_queue():
    short = [
        "backend.tasks.market.regime.compute_daily",
        "backend.tasks.market.backfill.tracked_cache",
        "backend.tasks.market.backfill.constituents",
        "backend.tasks.ibkr_watchdog.ping_ibkr_connection",
    ]
    for task in short:
        assert _route(task) != "heavy", f"{task} should not be on the heavy queue"


def test_portfolio_sync_routes_to_account_sync():
    assert _route("backend.tasks.portfolio.sync.sync_account") == "account_sync"


def test_portfolio_orders_route_to_orders_queue():
    assert _route("backend.tasks.portfolio.orders.submit_order") == "orders"
