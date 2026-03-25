"""
Operations Tasks Package
========================

Celery tasks for system operations:
- Auto-ops health monitoring and remediation
- IBKR gateway watchdog
"""

from .auto_ops import (
    auto_remediate_health,
)
from .ibkr_watchdog import (
    ping_ibkr_connection,
)

__all__ = [
    "auto_remediate_health",
    "ping_ibkr_connection",
]
