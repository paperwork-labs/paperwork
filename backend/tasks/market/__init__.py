"""
Market Data Tasks Package
=========================

Modular Celery tasks split from monolithic market_data_tasks.py.
Each module handles a specific domain for better maintainability.

Modules:
- backfill.py: Daily bar backfill tasks
- history.py: Snapshot history recording
- regime.py: Market regime computation
- coverage.py: Coverage monitoring
- constituents.py: Index constituent management
- fundamentals.py: Fundamentals enrichment

Note: The original market_data_tasks.py still contains all tasks.
This package provides the modular structure for new tasks and
gradual migration of existing tasks.
"""

# Import from the original file for backwards compatibility
# New tasks should be added to the appropriate submodule

__all__ = []
