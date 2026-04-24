"""Historical import API routes (G23)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.broker_account import BrokerAccount
from app.models.historical_import_run import (
    HistoricalImportRun,
    HistoricalImportSource,
)
from app.models.user import User
from app.services.portfolio.ibkr.historical_import import HistoricalImportService
from app.tasks.portfolio.historical_import import run_historical_import

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


class HistoricalImportRequest(BaseModel):
    date_from: date
    date_to: date
    xml_content: str | None = None


class HistoricalImportCsvRequest(BaseModel):
    csv_content: str = Field(min_length=1)


class HistoricalImportRunResponse(BaseModel):
    id: int
    account_id: int
    source: str
    status: str
    date_from: date | None
    date_to: date | None
    chunk_count: int
    records_total: int
    records_written: int
    records_skipped: int
    records_errors: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


def _require_user_account(db: Session, user_id: int, account_id: int) -> BrokerAccount:
    account = (
        db.query(BrokerAccount)
        .filter(
            BrokerAccount.id == account_id,
            BrokerAccount.user_id == user_id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def _to_response(run: HistoricalImportRun) -> HistoricalImportRunResponse:
    return HistoricalImportRunResponse(
        id=run.id,
        account_id=run.account_id,
        source=run.source.value,
        status=run.status.value,
        date_from=run.date_from,
        date_to=run.date_to,
        chunk_count=run.chunk_count,
        records_total=run.records_total,
        records_written=run.records_written,
        records_skipped=run.records_skipped,
        records_errors=run.records_errors,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.post("/{account_id}/historical-import", response_model=HistoricalImportRunResponse)
def start_historical_import_xml(
    account_id: int,
    payload: HistoricalImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.date_to < payload.date_from:
        raise HTTPException(status_code=422, detail="date_to must be >= date_from")
    if payload.xml_content:
        try:
            ET.fromstring(payload.xml_content)
        except ET.ParseError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "malformed_xml",
                    "message": f"Uploaded XML is malformed: {exc}",
                },
            ) from exc

    account = _require_user_account(db, current_user.id, account_id)
    run = HistoricalImportService(db).create_run(
        user_id=current_user.id,
        account=account,
        source=HistoricalImportSource.FLEX_XML,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )
    run_historical_import.delay(
        run_id=run.id,
        user_id=current_user.id,
        account_id=account.id,
        source=HistoricalImportSource.FLEX_XML.value,
        date_from=payload.date_from.isoformat(),
        date_to=payload.date_to.isoformat(),
        xml_content=payload.xml_content,
    )
    db.refresh(run)
    return _to_response(run)


@router.post("/{account_id}/historical-import-csv", response_model=HistoricalImportRunResponse)
def start_historical_import_csv(
    account_id: int,
    payload: HistoricalImportCsvRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = _require_user_account(db, current_user.id, account_id)
    run = HistoricalImportService(db).create_run(
        user_id=current_user.id,
        account=account,
        source=HistoricalImportSource.CSV,
        date_from=None,
        date_to=None,
    )
    run_historical_import.delay(
        run_id=run.id,
        user_id=current_user.id,
        account_id=account.id,
        source=HistoricalImportSource.CSV.value,
        csv_content=payload.csv_content,
    )
    db.refresh(run)
    return _to_response(run)


@router.get(
    "/{account_id}/historical-import/{run_id}",
    response_model=HistoricalImportRunResponse,
)
def get_historical_import_run(
    account_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_user_account(db, current_user.id, account_id)
    run = (
        db.query(HistoricalImportRun)
        .filter(
            HistoricalImportRun.id == run_id,
            HistoricalImportRun.user_id == current_user.id,
            HistoricalImportRun.account_id == account_id,
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Historical import run not found")
    return _to_response(run)
