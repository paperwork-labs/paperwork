"""
Settings Routes Package
=======================

User and app settings endpoints:
- App settings (themes, preferences)
- Account management (profile, credentials)
- Notifications (alert preferences)
"""

from .account import router as account_router
from .app import router as app_router
from .historical_import import router as historical_import_router
from .notifications import router as notifications_router

__all__ = [
    "account_router",
    "app_router",
    "historical_import_router",
    "notifications_router",
]
