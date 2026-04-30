"""Vendor catalog API — WS-76 PR-25.

medallion: ops
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Query
from pydantic import ValidationError

from app.schemas.base import error_response, success_response
from app.schemas.vendor import VendorCreate, VendorUpdate  # noqa: TC001
from app.services import vendors as vendors_svc

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("")
def api_list_vendors(category: str | None = Query(default=None)) -> JSONResponse:
    items = vendors_svc.list_vendors(category=category)
    return success_response({"vendors": [v.model_dump() for v in items]})


@router.get("/{vendor_id}")
def api_get_vendor(vendor_id: str) -> JSONResponse:
    v = vendors_svc.get_vendor(vendor_id)
    if v is None:
        return error_response("Vendor not found", status_code=404)
    return success_response({"vendor": v.model_dump()})


@router.post("")
def api_create_vendor(body: VendorCreate) -> JSONResponse:
    try:
        v = vendors_svc.create_vendor(body)
    except ValueError as e:
        return error_response(str(e), status_code=409)
    except (OSError, json.JSONDecodeError, ValidationError) as e:
        return error_response(f"Invalid vendor store: {e}", status_code=500)
    return success_response({"vendor": v.model_dump()}, status_code=201)


@router.put("/{vendor_id}")
def api_update_vendor(vendor_id: str, body: VendorUpdate) -> JSONResponse:
    try:
        v = vendors_svc.update_vendor(vendor_id, body)
    except KeyError:
        return error_response("Vendor not found", status_code=404)
    except (OSError, json.JSONDecodeError, ValidationError) as e:
        return error_response(f"Invalid vendor store: {e}", status_code=500)
    return success_response({"vendor": v.model_dump()})
