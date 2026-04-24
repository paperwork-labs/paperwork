"""
Tax export endpoints (FileFree.ai and friends).

We mount this as a sibling of :mod:`app.api.routes.portfolio.stocks` so
the existing ``GET /tax-report/export`` Schedule D CSV stays untouched
(don't break what works) while this router adds the new versioned package
format under ``/tax/filefree/...``.

Why a separate router?

* The FileFree contract is versioned and audited separately from the
  in-app Schedule D CSV. Splitting routers makes it obvious to reviewers
  which endpoints carry that contract.
* When entitlement gating (PR #326) lands, the FileFree endpoints will
  almost certainly require ``Feature.TAX_EXPORT`` -- one decorator on
  this router can cover the whole surface.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.silver.tax.filefree_exporter import FileFreeExporter
from app.services.silver.tax.schemas import SCHEMA_VERSION
from app.services.silver.tax.serialization import package_to_csv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tax/filefree", tags=["tax-export"])


@router.get(
    "/export",
    summary="Export FileFree.ai-shaped tax package for one user-year",
)
def export_filefree(
    year: int = Query(
        ...,
        ge=1900,
        le=2100,
        description="Tax year to export (matches close-trade calendar year).",
    ),
    format: str = Query(
        "json",
        pattern="^(json|csv)$",
        description="Output format: 'json' (versioned package) or 'csv' (lots only).",
    ),
    account_ids: Optional[List[int]] = Query(
        None,
        description="Optional whitelist of broker account ids; default is all of the user's accounts.",
    ),
    include_tax_advantaged: bool = Query(
        False,
        description="If true, include IRA/Roth/HSA accounts (audit dump). Default excludes them.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the FileFree.ai tax package as JSON or CSV.

    When there are no in-scope accounts, or no realized ``CLOSED_LOT`` /
    ``WASH_SALE`` rows for the requested calendar year, the response is still
    ``200`` with an empty ``lots`` array, zeroed ``summary`` totals, and
    ``warnings`` empty unless the mapper skipped rows (for example unknown
    accounts or missing close dates). In-scope accounts are still listed so
    the consumer can show a per-account "no realized gains" state.
    """
    try:
        exporter = FileFreeExporter(db)
        package = exporter.export(
            user_id=user.id,
            tax_year=year,
            account_ids=account_ids,
            include_tax_advantaged=include_tax_advantaged,
        )
    except Exception as e:
        logger.exception(
            "filefree_export failed: user_id=%s year=%s: %s", user.id, year, e
        )
        raise HTTPException(status_code=500, detail="tax export failed")

    if format == "csv":
        body = package_to_csv(package)
        filename = f"filefree-{year}-user{user.id}.csv"
        return StreamingResponse(
            iter([body]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-FileFree-Schema-Version": SCHEMA_VERSION,
                "X-FileFree-Lot-Count": str(package.summary.lot_count),
            },
        )

    # JSON: use Pydantic's encoder so Decimals stringify and dates ISO-format.
    payload = package.model_dump(mode="json")
    return JSONResponse(
        content=payload,
        headers={
            "X-FileFree-Schema-Version": SCHEMA_VERSION,
            "X-FileFree-Lot-Count": str(package.summary.lot_count),
        },
    )


@router.get(
    "/schema-version",
    summary="Return the FileFree.ai export schema version this server speaks",
)
def filefree_schema_version():
    """Cheap health/contract endpoint -- consumers poll this before exporting."""
    return {"schema_version": SCHEMA_VERSION}
