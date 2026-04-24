"""
Admin Routes Package
====================

Administrative endpoints:
- Management (CRUD, system operations)
- Scheduler (job management)
- Agent (auto-ops agent dashboard)
"""

from .agent import router as agent_router
from .autoops import router as autoops_router
from .corporate_actions import router as corporate_actions_router
from .deploy_health import router as deploy_health_router
from .jobs import router as jobs_router
from .management import _role_value
from .management import router as management_router
from .scheduler import router as scheduler_router

__all__ = [
    "_role_value",
    "agent_router",
    "autoops_router",
    "corporate_actions_router",
    "deploy_health_router",
    "jobs_router",
    "management_router",
    "scheduler_router",
]
