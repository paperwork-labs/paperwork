import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_session
from app.models.formation import Formation
from app.schemas.base import error_response, success_response
from app.schemas.formation import (
    FormationCreate,
    FormationResponse,
    FormationUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/formations", tags=["formations"])


def _formation_to_dict(formation: Formation) -> dict:
    return FormationResponse.model_validate(formation).model_dump(mode="json")


@router.post("")
async def create_formation(
    body: FormationCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_session),
):
    """Create a new LLC formation request."""
    formation = Formation(
        user_id=user_id,
        state_code=body.state_code.upper(),
        business_name=body.business_name,
        business_purpose=body.business_purpose,
        registered_agent=body.registered_agent.model_dump() if body.registered_agent else {},
        members=[m.model_dump() for m in body.members],
        principal_address=body.principal_address.model_dump() if body.principal_address else {},
        mailing_address=body.mailing_address.model_dump() if body.mailing_address else None,
    )

    db.add(formation)
    await db.flush()
    await db.refresh(formation)

    logger.info("Created formation %d for user %s in %s", formation.id, user_id, body.state_code)
    return success_response(_formation_to_dict(formation), status_code=201)


@router.get("")
async def list_formations(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_session),
):
    """List all formations for the current user."""
    result = await db.execute(
        select(Formation)
        .where(Formation.user_id == user_id)
        .order_by(Formation.created_at.desc())
    )
    formations = result.scalars().all()

    return success_response([_formation_to_dict(f) for f in formations])


@router.get("/{formation_id}")
async def get_formation(
    formation_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_session),
):
    """Get a specific formation by ID."""
    result = await db.execute(
        select(Formation).where(
            Formation.id == formation_id,
            Formation.user_id == user_id,
        )
    )
    formation = result.scalar_one_or_none()

    if not formation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formation not found",
        )

    return success_response(_formation_to_dict(formation))


@router.patch("/{formation_id}")
async def update_formation(
    formation_id: int,
    body: FormationUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_session),
):
    """Update a formation. Only allowed while status is draft or failed."""
    result = await db.execute(
        select(Formation).where(
            Formation.id == formation_id,
            Formation.user_id == user_id,
        )
    )
    formation = result.scalar_one_or_none()

    if not formation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formation not found",
        )

    if formation.status not in ("draft", "failed"):
        return error_response(
            "Cannot modify formation after submission",
            status_code=400,
        )

    update_data = body.model_dump(exclude_unset=True)

    if "registered_agent" in update_data:
        update_data["registered_agent"] = (
            body.registered_agent.model_dump() if body.registered_agent is not None else {}
        )
    if "members" in update_data:
        update_data["members"] = (
            [m.model_dump() for m in body.members] if body.members is not None else []
        )
    if "principal_address" in update_data:
        update_data["principal_address"] = (
            body.principal_address.model_dump() if body.principal_address is not None else {}
        )
    if "mailing_address" in update_data:
        update_data["mailing_address"] = (
            body.mailing_address.model_dump() if body.mailing_address is not None else None
        )
    if "screenshots" in update_data:
        update_data["screenshots"] = (
            list(body.screenshots) if body.screenshots is not None else []
        )
    if "error_log" in update_data:
        update_data["error_log"] = body.error_log if body.error_log is not None else {}

    for field, value in update_data.items():
        setattr(formation, field, value)

    await db.flush()
    await db.refresh(formation)

    logger.info("Updated formation %d for user %s", formation_id, user_id)
    return success_response(_formation_to_dict(formation))


@router.delete("/{formation_id}")
async def cancel_formation(
    formation_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_session),
):
    """Cancel a formation. Sets status to 'failed' with cancellation reason."""
    result = await db.execute(
        select(Formation).where(
            Formation.id == formation_id,
            Formation.user_id == user_id,
        )
    )
    formation = result.scalar_one_or_none()

    if not formation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formation not found",
        )

    if formation.status in ("submitted", "confirmed"):
        return error_response(
            "Cannot cancel a formation that has been submitted or confirmed",
            status_code=400,
        )

    formation.status = "failed"
    formation.error_log = {
        **(formation.error_log or {}),
        "cancelled": True,
        "cancelled_by": "user",
    }

    await db.flush()
    await db.refresh(formation)

    logger.info("Cancelled formation %d for user %s", formation_id, user_id)
    return success_response(_formation_to_dict(formation))
