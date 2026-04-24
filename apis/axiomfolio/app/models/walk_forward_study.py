"""WalkForwardStudy — persisted record of a hyperparameter optimization run.

A study is created from the API and processed by a Celery task on the
``heavy`` queue. Status transitions are PENDING -> RUNNING -> COMPLETED /
FAILED. The schema intentionally mirrors what the frontend needs to render
without a join: best params, best score, per-split breakdown, regime
attribution.

All money / score values are persisted as ``Numeric`` (Decimal) per the
iron law that monetary or risk-adjusted statistics must not round-trip
through float in storage.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class WalkForwardStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WalkForwardStudy(Base):
    """Hyperparameter optimization run scoped to a single user.

    Optimization is executed by Optuna against an existing rules-based
    backtest engine. Each trial is a full walk-forward
    (``n_splits`` rolling train/test windows) on the requested dataset;
    the trial score is the average out-of-sample objective across splits.

    Multi-tenancy: every read path filters by ``user_id``. There is no
    "shared" study concept.
    """

    __tablename__ = "walk_forward_studies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name = Column(String(200), nullable=False)
    strategy_class = Column(String(120), nullable=False)
    objective = Column(String(64), nullable=False, default="sharpe_ratio")

    param_space = Column(JSON, nullable=False)
    symbols = Column(JSON, nullable=False)

    train_window_days = Column(Integer, nullable=False)
    test_window_days = Column(Integer, nullable=False)
    n_splits = Column(Integer, nullable=False, default=5)
    n_trials = Column(Integer, nullable=False, default=50)
    regime_filter = Column(String(8), nullable=True)

    dataset_start = Column(DateTime, nullable=False)
    dataset_end = Column(DateTime, nullable=False)

    status = Column(
        SQLEnum(
            WalkForwardStatus,
            values_callable=lambda x: [e.value for e in x],
            name="walk_forward_status",
        ),
        nullable=False,
        default=WalkForwardStatus.PENDING,
    )

    best_params = Column(JSON, nullable=True)
    best_score = Column(Numeric(18, 8), nullable=True)
    total_trials = Column(Integer, nullable=False, default=0)

    per_split_results = Column(JSON, nullable=True)
    regime_attribution = Column(JSON, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index("idx_wf_study_user_status", "user_id", "status"),
        Index("idx_wf_study_created", "created_at"),
    )

    def to_summary(self) -> dict:
        """Compact response used by the list endpoint."""
        return {
            "id": self.id,
            "name": self.name,
            "strategy_class": self.strategy_class,
            "objective": self.objective,
            "status": self.status.value if self.status else None,
            "n_splits": self.n_splits,
            "n_trials": self.n_trials,
            "total_trials": self.total_trials,
            "regime_filter": self.regime_filter,
            "best_score": float(self.best_score) if self.best_score is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    def to_detail(self) -> dict:
        """Full response used by the detail endpoint and frontend renderer."""
        return {
            **self.to_summary(),
            "param_space": self.param_space,
            "symbols": self.symbols,
            "train_window_days": self.train_window_days,
            "test_window_days": self.test_window_days,
            "dataset_start": (
                self.dataset_start.isoformat() if self.dataset_start else None
            ),
            "dataset_end": (
                self.dataset_end.isoformat() if self.dataset_end else None
            ),
            "best_params": self.best_params,
            "per_split_results": self.per_split_results,
            "regime_attribution": self.regime_attribution,
            "error_message": self.error_message,
        }
