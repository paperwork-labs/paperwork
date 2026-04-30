"""HTTP API for static infrastructure catalog (services + vendors)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Query

from app.schemas.base import success_response
from app.services import infra_registry as infra_registry_svc

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

router = APIRouter(prefix="/infra", tags=["infra"])


@router.get("/services")
def list_infra_services(provider: str | None = Query(default=None)) -> JSONResponse:
    services = infra_registry_svc.list_services(provider=provider)
    return success_response({"services": [s.model_dump() for s in services]})


@router.get("/vendors")
def list_infra_vendors(category: str | None = Query(default=None)) -> JSONResponse:
    vendors = infra_registry_svc.list_vendors(category=category)
    return success_response({"vendors": [v.model_dump() for v in vendors]})
