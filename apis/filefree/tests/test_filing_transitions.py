import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.filing import Filing, FilingStatus
from app.services.filing_service import VALID_TRANSITIONS, advance_status
from app.utils.exceptions import ConflictError, NotFoundError

_FILING_STATUS_VALUES = {s.value for s in FilingStatus}

_ALLOWED_PAIRS = [
    (src, tgt)
    for src, targets in VALID_TRANSITIONS.items()
    for tgt in targets
    if tgt in _FILING_STATUS_VALUES
]


def _make_filing(status_value: str, user_id: uuid.UUID | None = None) -> MagicMock:
    f = MagicMock(spec=Filing)
    st = MagicMock()
    st.value = status_value
    f.status = st
    f.user_id = user_id or uuid.uuid4()
    f.id = uuid.uuid4()
    return f


def _forbidden_pairs() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for current in VALID_TRANSITIONS:
        allowed = set(VALID_TRANSITIONS[current])
        for s in FilingStatus:
            if s.value not in allowed:
                out.append((current, s.value))
                break
        else:
            raise AssertionError(f"no forbidden target for state {current!r}")
    out.append((FilingStatus.ACCEPTED.value, FilingStatus.DRAFT.value))
    return out


def test_valid_transitions_completeness() -> None:
    terminal = {FilingStatus.ACCEPTED.value}
    keys = set(VALID_TRANSITIONS.keys())
    for s in FilingStatus:
        if s.value in terminal:
            continue
        assert s.value in keys, f"{s.value!r} missing from VALID_TRANSITIONS keys"


@pytest.mark.parametrize("current,target", _ALLOWED_PAIRS)
@patch("app.services.filing_service.FilingRepository")
async def test_allowed_transitions_succeed(
    mock_repo_cls: MagicMock,
    current: str,
    target: str,
) -> None:
    user_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    filing = _make_filing(current, user_id)
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=filing)
    mock_repo_cls.return_value = mock_repo
    db = AsyncMock()

    result = await advance_status(db, filing_id, user_id, target)

    assert result is filing
    assert result.status == FilingStatus(target)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(filing)


@pytest.mark.parametrize("current,forbidden_target", _forbidden_pairs())
@patch("app.services.filing_service.FilingRepository")
async def test_forbidden_transitions_raise_conflict(
    mock_repo_cls: MagicMock,
    current: str,
    forbidden_target: str,
) -> None:
    user_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    filing = _make_filing(current, user_id)
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=filing)
    mock_repo_cls.return_value = mock_repo
    db = AsyncMock()

    with pytest.raises(ConflictError, match=r"Cannot transition|Invalid status"):
        await advance_status(db, filing_id, user_id, forbidden_target)

    db.flush.assert_not_awaited()


@patch("app.services.filing_service.FilingRepository")
async def test_invalid_status_string_raises_conflict(mock_repo_cls: MagicMock) -> None:
    user_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    filing = _make_filing(FilingStatus.DRAFT.value, user_id)
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=filing)
    mock_repo_cls.return_value = mock_repo
    db = AsyncMock()

    with pytest.raises(ConflictError, match="Invalid status"):
        await advance_status(db, filing_id, user_id, "not_a_real_status")


@patch("app.services.filing_service.FilingRepository")
async def test_advance_status_wrong_user_raises_not_found(mock_repo_cls: MagicMock) -> None:
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    filing = _make_filing(FilingStatus.DRAFT.value, owner_id)
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=filing)
    mock_repo_cls.return_value = mock_repo
    db = AsyncMock()

    with pytest.raises(NotFoundError, match="Filing not found"):
        await advance_status(
            db,
            filing_id,
            other_id,
            FilingStatus.DOCUMENTS_UPLOADED.value,
        )

    db.flush.assert_not_awaited()
