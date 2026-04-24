# AxiomFolio Tasks Package

Celery task modules that drive the **Intelligence**, **Portfolio**, and **Strategy** pillars.

## Package Layout

```
app/tasks/
├── celery_app.py      # Celery application configuration
├── job_catalog.py     # Scheduled job definitions (seeds cron_schedule table)
├── utils/             # Shared helpers: task_utils, schedule_helpers, schedule_metadata
├── market/            # Market data pipeline (backfill, indicators, regime, coverage)
├── portfolio/         # Broker sync, reconciliation, orders
├── strategy/          # Signal evaluation, entry/exit scanning
├── intelligence/      # AI-powered briefs and analysis
└── ops/               # Auto-ops, IBKR watchdog
```

## Market Tasks (Canonical Reference)

**See [`market/README.md`](./market/README.md)** for the complete market-task inventory, schedules, dependencies, runbooks, and troubleshooting.

## Operations Quick Reference

| What | Where |
|------|-------|
| Scheduled jobs | `job_catalog.py` → Admin Schedules → Render cron sync |
| Run a task manually | `make task-run TASK=app.tasks.market.<module>.<function>` |
| Worker logs (Docker dev) | `make logs` |
