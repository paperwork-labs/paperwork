"""Multi-tenant API routes (GDPR data-subject rights, admin cost reports)."""

from app.api.routes.multitenant.admin_costs import router as admin_costs_router
from app.api.routes.multitenant.gdpr import router as gdpr_router

__all__ = ["admin_costs_router", "gdpr_router"]
