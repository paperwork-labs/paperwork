"""Validator queue state machine for ``Candidate`` rows.

medallion: gold
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.picks import Candidate, CandidateQueueState, PicksAuditLog


class InvalidStateTransition(Exception):
    """Raised when a ``Candidate`` cannot move to the requested queue state."""

    def __init__(self, current: CandidateQueueState, requested: CandidateQueueState) -> None:
        self.current = current
        self.requested = requested
        super().__init__(f"Illegal transition {current.value!r} -> {requested.value!r}")


_ALLOWED: dict[CandidateQueueState, frozenset[CandidateQueueState]] = {
    CandidateQueueState.DRAFT: frozenset(
        {CandidateQueueState.APPROVED, CandidateQueueState.REJECTED}
    ),
    CandidateQueueState.APPROVED: frozenset(
        {CandidateQueueState.PUBLISHED, CandidateQueueState.REJECTED}
    ),
    CandidateQueueState.PUBLISHED: frozenset(),
    CandidateQueueState.REJECTED: frozenset(),
}


def transition(
    db: Session,
    candidate: Candidate,
    *,
    to_state: CandidateQueueState,
    actor_user_id: int,
    reason: str | None = None,
) -> Candidate:
    """Validate and apply a queue state change.

    Persists audit row and mutates ``candidate`` in memory; caller commits.
    """
    current = candidate.status
    if to_state not in _ALLOWED.get(current, frozenset()):
        raise InvalidStateTransition(current, to_state)

    now = datetime.now(UTC)
    entry = PicksAuditLog(
        candidate_id=candidate.id,
        from_state=current.value,
        to_state=to_state.value,
        actor_user_id=actor_user_id,
        reason=reason,
        created_at=now,
    )
    db.add(entry)

    candidate.status = to_state
    candidate.state_transitioned_at = now
    candidate.state_transitioned_by = actor_user_id

    if to_state == CandidateQueueState.PUBLISHED:
        candidate.published_at = now
    if to_state == CandidateQueueState.REJECTED:
        candidate.decided_at = now

    db.flush()
    return candidate
