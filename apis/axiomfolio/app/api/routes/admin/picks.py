"""Admin API: validator queue for ``Candidate`` rows."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_admin_user
from app.database import get_db
from app.models.picks import (
    Candidate,
    CandidateQueueState,
    EmailParse,
    PickAction,
)
from app.models.user import User
from app.services.gold.picks.state_machine import InvalidStateTransition, transition

router = APIRouter(dependencies=[Depends(get_admin_user)])


def _parse_queue_state(raw: str) -> CandidateQueueState:
    key = (raw or "").strip().upper()
    mapping = {
        "DRAFT": CandidateQueueState.DRAFT,
        "APPROVED": CandidateQueueState.APPROVED,
        "PUBLISHED": CandidateQueueState.PUBLISHED,
        "REJECTED": CandidateQueueState.REJECTED,
    }
    if key not in mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state filter: {raw!r}",
        )
    return mapping[key]


def _state_api(s: CandidateQueueState) -> str:
    return s.name


def _serialize_candidate(db: Session, c: Candidate, *, detail: bool) -> dict[str, Any]:
    email_subject: Optional[str] = None
    email_sender: Optional[str] = None
    parsed_at: Optional[str] = None
    if detail and c.source_email_parse_id:
        ep = (
            db.query(EmailParse)
            .options(joinedload(EmailParse.email))
            .filter(EmailParse.id == c.source_email_parse_id)
            .one_or_none()
        )
        if ep is not None:
            parsed_at = ep.parsed_at.isoformat() if ep.parsed_at else None
            if ep.email is not None:
                email_subject = ep.email.subject
                email_sender = ep.email.sender
    out: dict[str, Any] = {
        "id": c.id,
        "ticker": c.symbol,
        "action": c.action_suggestion.value.upper(),
        "state": _state_api(c.status),
        "confidence": float(c.score) if c.score is not None else None,
        "thesis": c.rationale_summary,
        "target_price": str(c.suggested_target) if c.suggested_target is not None else None,
        "stop_loss": str(c.suggested_stop) if c.suggested_stop is not None else None,
        "generator_name": c.generator_name,
        "generator_version": c.generator_version,
        "generated_at": c.generated_at.isoformat() if c.generated_at else None,
        "published_at": c.published_at.isoformat() if c.published_at else None,
        "state_transitioned_at": (
            c.state_transitioned_at.isoformat() if c.state_transitioned_at else None
        ),
        "state_transitioned_by": c.state_transitioned_by,
        "source_email_parse_id": c.source_email_parse_id,
    }
    if detail:
        out["email_subject"] = email_subject
        out["email_sender"] = email_sender
        out["parsed_at"] = parsed_at
    return out


class RejectBody(BaseModel):
    reason: str = ""


class PatchCandidateBody(BaseModel):
    ticker: Optional[str] = None
    action: Optional[str] = None
    target_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    thesis: Optional[str] = None


@router.get("/picks/queue/counts")
def picks_queue_counts(
    db: Session = Depends(get_db),
) -> dict[str, int]:
    rows = (
        db.query(Candidate.status, func.count())
        .group_by(Candidate.status)
        .all()
    )
    counts = {s.name: 0 for s in CandidateQueueState}
    for st, n in rows:
        counts[st.name] = int(n)
    return counts


@router.get("/picks/queue")
def picks_queue(
    db: Session = Depends(get_db),
    state: str = Query("DRAFT"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    st = _parse_queue_state(state)
    status_filter = Candidate.status == st
    total = db.execute(
        select(func.count()).select_from(Candidate).where(status_filter)
    ).scalar_one()
    q = (
        db.query(Candidate)
        .filter(status_filter)
        .order_by(Candidate.generated_at.desc(), Candidate.id.desc())
    )
    items = q.offset(offset).limit(limit).all()
    return {
        "items": [_serialize_candidate(db, c, detail=False) for c in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/picks/{candidate_id}")
def picks_candidate_detail(
    candidate_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    c = db.query(Candidate).filter(Candidate.id == candidate_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return _serialize_candidate(db, c, detail=True)


@router.post("/picks/{candidate_id}/approve", status_code=status.HTTP_200_OK)
def picks_approve(
    candidate_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    c = db.query(Candidate).filter(Candidate.id == candidate_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    try:
        transition(
            db,
            c,
            to_state=CandidateQueueState.APPROVED,
            actor_user_id=admin.id,
            reason=None,
        )
        db.commit()
    except InvalidStateTransition as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    db.refresh(c)
    return _serialize_candidate(db, c, detail=True)


@router.post("/picks/{candidate_id}/reject", status_code=status.HTTP_200_OK)
def picks_reject(
    candidate_id: int,
    body: RejectBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    c = db.query(Candidate).filter(Candidate.id == candidate_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    try:
        transition(
            db,
            c,
            to_state=CandidateQueueState.REJECTED,
            actor_user_id=admin.id,
            reason=body.reason or None,
        )
        db.commit()
    except InvalidStateTransition as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    db.refresh(c)
    return _serialize_candidate(db, c, detail=True)


@router.post("/picks/{candidate_id}/publish", status_code=status.HTTP_200_OK)
def picks_publish(
    candidate_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    c = db.query(Candidate).filter(Candidate.id == candidate_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    try:
        transition(
            db,
            c,
            to_state=CandidateQueueState.PUBLISHED,
            actor_user_id=admin.id,
            reason=None,
        )
        db.commit()
    except InvalidStateTransition as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    db.refresh(c)
    return _serialize_candidate(db, c, detail=True)


@router.patch("/picks/{candidate_id}", status_code=status.HTTP_200_OK)
def picks_patch_candidate(
    candidate_id: int,
    body: PatchCandidateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    c = db.query(Candidate).filter(Candidate.id == candidate_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    if c.status != CandidateQueueState.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Edits are only allowed while the candidate is in DRAFT state",
        )
    if body.ticker is not None:
        sym = body.ticker.strip().upper()
        if not sym:
            raise HTTPException(status_code=400, detail="ticker cannot be empty")
        c.symbol = sym
    if body.action is not None:
        raw = body.action.strip().lower()
        try:
            c.action_suggestion = PickAction(raw)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {body.action!r}",
            ) from e
    if body.target_price is not None:
        c.suggested_target = body.target_price
    if body.stop_loss is not None:
        c.suggested_stop = body.stop_loss
    if body.thesis is not None:
        c.rationale_summary = body.thesis
    db.add(c)
    db.commit()
    db.refresh(c)
    return _serialize_candidate(db, c, detail=True)
