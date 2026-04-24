"""Symbol master read API.

Endpoints (all authenticated; the master is global so we never
attach a tenant filter — see ``app/services/symbols/`` for the
multi-tenancy notes):

* ``GET /api/v1/symbols/{ticker}/resolve?as_of=YYYY-MM-DD``
  Resolve a ticker (optionally point-in-time) to a master row.

* ``GET /api/v1/symbols/{symbol_master_id}``
  Fetch a single master row by id.

* ``GET /api/v1/symbols/{symbol_master_id}/history``
  Audit ledger for a master, oldest first.

This PR does **not** expose any mutation endpoints. Writes live on
the service layer and are gated behind admin-only call-sites
(``app/services/symbols/initial_load.py`` and future Celery
jobs). Once we have an admin operator UI for symbol management, a
separate PR will surface the writes behind ``get_admin_user``.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.symbol_master import (
    SymbolAlias,
    SymbolHistory,
    SymbolMaster,
)
from app.models.user import User
from app.services.silver.symbols import SymbolMasterService


router = APIRouter(prefix="/symbols", tags=["Symbols"])


# ---------------------------------------------------------------------------
# Pydantic response shapes
#
# We keep these in this file (rather than a shared schemas module)
# because the symbol master is a leaf domain — only the symbols
# router projects these shapes. If a second consumer appears, lift
# them into a shared module.
# ---------------------------------------------------------------------------


class SymbolMasterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    primary_ticker: str
    cik: Optional[str] = None
    isin: Optional[str] = None
    figi: Optional[str] = None
    asset_class: str
    exchange: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    gics_code: Optional[str] = None
    status: str
    delisted_at: Optional[str] = None
    merged_into_symbol_master_id: Optional[int] = None


class SymbolAliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol_master_id: int
    alias_ticker: str
    valid_from: date
    valid_to: Optional[date] = None
    source: str
    notes: Optional[str] = None


class SymbolHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol_master_id: int
    change_type: str
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    effective_date: date
    source: str


class ResolveResponse(BaseModel):
    """Resolution envelope.

    ``master`` is the resolved row (or ``null`` when unknown).
    ``matched_alias`` is the alias row that produced the match, when
    resolution went through the alias table — useful for callers that
    want to surface "you searched FB, we matched alias FB -> META
    valid from 1900-01-01" provenance to the user.
    """

    query_ticker: str
    normalized_ticker: str
    as_of_date: Optional[date] = None
    master: Optional[SymbolMasterResponse] = None
    matched_alias: Optional[SymbolAliasResponse] = None


# ---------------------------------------------------------------------------
# Endpoints
#
# Order matters: ``/{ticker}/resolve`` is declared before
# ``/{symbol_master_id}`` so FastAPI's path-param parsing routes
# ``/foo/resolve`` to the resolve endpoint instead of trying to
# coerce ``foo`` into an int. The ``int`` typing on the second
# endpoint also makes ``/symbols/AAPL`` return 422 cleanly rather
# than colliding with ticker resolution semantics.
# ---------------------------------------------------------------------------


@router.get(
    "/{ticker}/resolve",
    response_model=ResolveResponse,
    summary="Resolve a ticker (optionally point-in-time) to a SymbolMaster row.",
)
def resolve_ticker(
    ticker: str = Path(..., min_length=1, max_length=20),
    as_of: Optional[date] = Query(
        default=None,
        description=(
            "Optional ISO-8601 date. When set, walks SymbolAlias rows whose "
            "[valid_from, valid_to) window contains the date so historical "
            "lookups (e.g. 'what did FB mean on 2022-06-08?') return the "
            "right master row."
        ),
    ),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ResolveResponse:
    service = SymbolMasterService(db)
    normalized = service._normalize(ticker)
    master = service.resolve(ticker, as_of_date=as_of)

    matched_alias: Optional[SymbolAlias] = None
    if master is not None and normalized != master.primary_ticker:
        alias_q = db.query(SymbolAlias).filter(
            SymbolAlias.alias_ticker == normalized,
            SymbolAlias.symbol_master_id == master.id,
        )
        if as_of is not None:
            alias_q = alias_q.filter(SymbolAlias.valid_from <= as_of)
        matched_alias = alias_q.order_by(SymbolAlias.valid_from.desc()).first()

    return ResolveResponse(
        query_ticker=ticker,
        normalized_ticker=normalized,
        as_of_date=as_of,
        master=SymbolMasterResponse.model_validate(master) if master else None,
        matched_alias=(
            SymbolAliasResponse.model_validate(matched_alias)
            if matched_alias
            else None
        ),
    )


@router.get(
    "/{symbol_master_id}",
    response_model=SymbolMasterResponse,
    summary="Fetch a single SymbolMaster row by id.",
)
def get_symbol_master(
    symbol_master_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SymbolMasterResponse:
    master = db.get(SymbolMaster, symbol_master_id)
    if master is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SymbolMaster id={symbol_master_id} not found",
        )
    return SymbolMasterResponse.model_validate(master)


@router.get(
    "/{symbol_master_id}/history",
    response_model=List[SymbolHistoryResponse],
    summary="Audit ledger for a SymbolMaster row, oldest first.",
)
def get_symbol_history(
    symbol_master_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> List[SymbolHistoryResponse]:
    master = db.get(SymbolMaster, symbol_master_id)
    if master is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SymbolMaster id={symbol_master_id} not found",
        )
    rows = (
        db.query(SymbolHistory)
        .filter(SymbolHistory.symbol_master_id == symbol_master_id)
        .order_by(SymbolHistory.effective_date.asc(), SymbolHistory.id.asc())
        .all()
    )
    return [SymbolHistoryResponse.model_validate(r) for r in rows]
