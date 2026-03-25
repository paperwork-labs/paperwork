"""
Settings Routes Package
=======================

User and app settings endpoints:
- App settings (themes, preferences)
- Account management (profile, credentials)
- Notifications (alert preferences)
"""

from .app import router as app_router
from .account import router as account_router
from .notifications import router as notifications_router

__all__ = [
    "app_router",
    "account_router",
    "notifications_router",
]
