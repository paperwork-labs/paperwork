"""Walk-forward optimizer API.

Three endpoints, all scoped to ``current_user.id`` so cross-tenant reads
are impossible by construction:

- ``POST /api/v1/backtest/walk-forward/studies``  — create + enqueue
- ``GET  /api/v1/backtest/walk-forward/studies``  — list mine
- ``GET  /api/v1/backtest/walk-forward/studies/{id}`` — poll one of mine

The router is gated by the ``research.walk_forward_optimizer`` feature
key; tier policy lives in ``feature_catalog.py``, not inline here.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, require_feature
from backend.database import get_db
from backend.models.user import User
from backend.models.walk_forward_study import (
    WalkForwardStatus,
    WalkForwardStudy,
)
from backend.services.backtest.objectives import list_objectives
from backend.services.backtest.regime_attribution import REGIME_LABELS
from backend.services.backtest.walk_forward import validate_param_space

logger = logging.getLogger(__name__)

# Sane upper bounds — the actual hard timeout is the Celery task's
# ``time_limit``. These are gut-check guards so a bad input doesn't queue
# a study that obviously cannot finish in 60 minutes.
MAX_TRIALS = 200
MAX_SPLITS = 10
MAX_SYMBOLS = 100
MIN_TRAIN_DAYS = 30
MIN_TEST_DAYS = 5

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateStudyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    strategy_class: str = Field(..., description="Key in STRATEGY_REGISTRY")
    objective: str = Field(default="sharpe_ratio")
    param_space: Dict[str, Dict[str, Any]] = Field(...)
    symbols: List[str] = Field(..., min_length=1, max_length=MAX_SYMBOLS)
    dataset_start: date
    dataset_end: date
    train_window_days: int = Field(..., ge=MIN_TRAIN_DAYS)
    test_window_days: int = Field(..., ge=MIN_TEST_DAYS)
    n_splits: int = Field(default=5, ge=1, le=MAX_SPLITS)
    n_trials: int = Field(default=50, ge=1, le=MAX_TRIALS)
    regime_filter: Optional[str] = Field(default=None)

    @field_validator("regime_filter")
    @classmethod
    def _validate_regime(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in REGIME_LABELS:
            raise ValueError(
                f"regime_filter must be one of {REGIME_LABELS} or null"
            )
        return v

    @field_validator("objective")
    @classmethod
    def _validate_objective(cls, v: str) -> str:
        if v not in list_objectives():
            raise ValueError(
                f"objective must be one of {list_objectives()}"
            )
        return v

    @field_validator("symbols")
    @classmethod
    def _normalize_symbols(cls, v: List[str]) -> List[str]:
        # Deduplicate + uppercase so the engine query is deterministic.
        seen, out = set(), []
        for s in v:
            ss = s.strip().upper()
            if ss and ss not in seen:
                seen.add(ss)
                out.append(ss)
        if not out:
            raise ValueError("symbols must contain at least one ticker")
        return out


class StudySummaryResponse(BaseModel):
    id: int
    name: str
    strategy_class: str
    objective: str
    status: str
    n_splits: int
    n_trials: int
    total_trials: int
    regime_filter: Optional[str]
    best_score: Optional[float]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


class StudyDetailResponse(StudySummaryResponse):
    param_space: Dict[str, Any]
    symbols: List[str]
    train_window_days: int
    test_window_days: int
    dataset_start: Optional[str]
    dataset_end: Optional[str]
    best_params: Optional[Dict[str, Any]]
    per_split_results: Optional[List[Dict[str, Any]]]
    regime_attribution: Optional[Dict[str, Any]]
    error_message: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_window_fits_dataset(req: CreateStudyRequest) -> None:
    if req.dataset_end <= req.dataset_start:
        raise HTTPException(
            status_code=400, detail="dataset_end must be after dataset_start"
        )
    span = (req.dataset_end - req.dataset_start).days
    needed = req.train_window_days + req.test_window_days * req.n_splits
    if span < needed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dataset spans {span} days but the requested layout needs "
                f"at least {needed} days "
                f"(train={req.train_window_days} + {req.n_splits} * "
                f"test={req.test_window_days})."
            ),
        )


def _enqueue_study(study_id: int) -> None:
    """Send the study to the heavy worker.

    Imported lazily so unit tests that patch the task can swap the
    implementation without import-time side effects.
    """
    from backend.tasks.backtest.walk_forward_runner import run_walk_forward_study

    run_walk_forward_study.delay(study_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/walk-forward/studies",
    response_model=StudyDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_feature("research.walk_forward_optimizer"))],
)
def create_study(
    payload: CreateStudyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudyDetailResponse:
    """Create a study row, enqueue the Celery task, return the row.

    The frontend immediately starts polling ``GET /studies/{id}`` after
    receiving the response.
    """
    # Lazy import keeps the strategy registry out of the route module's
    # import-time graph.
    from backend.tasks.backtest.walk_forward_runner import (
        list_strategy_classes,
        get_strategy_builder,
    )

    if payload.strategy_class not in list_strategy_classes():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown strategy_class '{payload.strategy_class}'. "
                f"Available: {list_strategy_classes()}"
            ),
        )
    # Cheap upfront param-space sanity check so a bad config never
    # reaches the heavy worker.
    try:
        validate_param_space(payload.param_space)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Confirm the builder accepts dummy params (catches a registry bug
    # before we burn a task slot).
    try:
        sample_params = {name: spec.get("low", spec.get("choices", [None])[0])
                         for name, spec in payload.param_space.items()}
        get_strategy_builder(payload.strategy_class)(sample_params)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"strategy_class smoke-test failed: {e}"
        )

    _validate_window_fits_dataset(payload)

    study = WalkForwardStudy(
        user_id=current_user.id,
        name=payload.name,
        strategy_class=payload.strategy_class,
        objective=payload.objective,
        param_space=payload.param_space,
        symbols=payload.symbols,
        train_window_days=payload.train_window_days,
        test_window_days=payload.test_window_days,
        n_splits=payload.n_splits,
        n_trials=payload.n_trials,
        regime_filter=payload.regime_filter,
        dataset_start=datetime.combine(
            payload.dataset_start, datetime.min.time(), tzinfo=timezone.utc
        ),
        dataset_end=datetime.combine(
            payload.dataset_end, datetime.min.time(), tzinfo=timezone.utc
        ),
        status=WalkForwardStatus.PENDING,
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    try:
        _enqueue_study(study.id)
    except Exception as e:
        # Failure to enqueue is recoverable — the row exists in PENDING
        # and an admin can retry. We *do not* zero out the row or pretend
        # it succeeded.
        logger.exception(
            "failed to enqueue walk-forward study %s: %s", study.id, e
        )
        study.status = WalkForwardStatus.FAILED
        study.error_message = f"enqueue failed: {e}"
        db.commit()

    return StudyDetailResponse(**study.to_detail())


@router.get(
    "/walk-forward/studies",
    response_model=List[StudySummaryResponse],
    dependencies=[Depends(require_feature("research.walk_forward_optimizer"))],
)
def list_my_studies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> List[StudySummaryResponse]:
    """Return the calling user's studies, newest first.

    Cross-tenant safety: every query filters on ``current_user.id``.
    """
    rows = (
        db.query(WalkForwardStudy)
        .filter(WalkForwardStudy.user_id == current_user.id)
        .order_by(WalkForwardStudy.created_at.desc())
        .limit(min(max(limit, 1), 200))
        .all()
    )
    return [StudySummaryResponse(**r.to_summary()) for r in rows]


@router.get(
    "/walk-forward/studies/{study_id}",
    response_model=StudyDetailResponse,
    dependencies=[Depends(require_feature("research.walk_forward_optimizer"))],
)
def get_study(
    study_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudyDetailResponse:
    """Fetch one study by id, only if it belongs to the caller.

    A study owned by another user returns 404 (never 403) so the endpoint
    does not leak existence.
    """
    row = (
        db.query(WalkForwardStudy)
        .filter(
            WalkForwardStudy.id == study_id,
            WalkForwardStudy.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Study not found")
    return StudyDetailResponse(**row.to_detail())


@router.get(
    "/walk-forward/strategies",
    dependencies=[Depends(require_feature("research.walk_forward_optimizer"))],
)
def list_available_strategies(
    _: User = Depends(get_current_user),
) -> Dict[str, List[str]]:
    """Return the registered strategy classes and objective names.

    The frontend StudyForm uses this to populate two dropdowns instead of
    hardcoding a list (which would drift the moment a new strategy or
    objective lands).
    """
    from backend.tasks.backtest.walk_forward_runner import list_strategy_classes

    return {
        "strategies": list_strategy_classes(),
        "objectives": list_objectives(),
        "regimes": list(REGIME_LABELS),
    }
