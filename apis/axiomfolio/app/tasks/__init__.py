"""
AxiomFolio Celery Tasks Package
===============================

Domain-driven task organization:
- market/       : Market data backfill, history, regime, coverage
- portfolio/    : Broker sync, reconciliation, orders
- strategy/     : Signal evaluation, entry/exit scanning
- intelligence/ : AI-powered briefs and analysis
- ops/          : Auto-ops, IBKR watchdog

Core files at root level:
- celery_app.py     : Celery application configuration
- job_catalog.py    : Scheduled job definitions
- utils/            : Shared task utilities (task_utils, schedule_helpers, schedule_metadata)
"""

# Re-export commonly used tasks for backwards compatibility
# New code should import from subpackages directly

__all__ = []
