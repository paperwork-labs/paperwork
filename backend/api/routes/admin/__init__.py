"""
Admin Routes Package
====================

Administrative endpoints:
- Management (CRUD, system operations)
- Scheduler (job management)
- Agent (auto-ops agent dashboard)
"""

from .management import router as management_router
from .management import _role_value
from .scheduler import router as scheduler_router
from .agent import router as agent_router
from .autoops import router as autoops_router
from .corporate_actions import router as corporate_actions_router

__all__ = [
    "management_router",
    "scheduler_router",
    "agent_router",
    "autoops_router",
    "corporate_actions_router",
    "_role_value",
]
