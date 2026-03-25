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
- task_utils.py     : Shared task utilities
- job_catalog.py    : Scheduled job definitions
- schedule_helpers.py
- schedule_metadata.py
- market_data_tasks.py : Legacy market data tasks (being migrated to market/)
"""

# Re-export commonly used tasks for backwards compatibility
# New code should import from subpackages directly

__all__ = []
