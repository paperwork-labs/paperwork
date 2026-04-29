"""Brain self-merge graduation gate and track record.

medallion: ops
"""

from __future__ import annotations

import fcntl
import fnmatch
import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, TypeVar

from app.schemas.self_merge import (
    MergeTier,
    PromotionRecord,
    RevertRecord,
    SelfMergePromotionsFile,
    SelfMergeRecord,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_T = TypeVar("_T")

_ENV_PATH = "BRAIN_SELF_MERGE_PROMOTIONS_JSON"
_TMP_PREFIX = ".self_merge_promotions."
_GRADUATION_THRESHOLD = 50
_CLEAN_REVERT_WINDOW = timedelta(days=30)
_RECENT_REVERT_BLOCK_WINDOW = timedelta(days=7)

_DATA_ONLY_PATTERNS = ("apis/brain/data/**", "docs/**", ".cursor/rules/**")
_NEXT_TIER: dict[MergeTier, MergeTier] = {
    "data-only": "brain-code",
    "brain-code": "app-code",
    "app-code": "app-code",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalise_dt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _brain_data_dir() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, "data")
    os.makedirs(d, exist_ok=True)
    return d


def promotions_file_path() -> str:
    """Path to ``self_merge_promotions.json``; override for tests."""
    env = os.environ.get(_ENV_PATH, "").strip()
    if env:
        return env
    return os.path.join(_brain_data_dir(), "self_merge_promotions.json")


def _lock_path() -> str:
    return promotions_file_path() + ".lock"


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=d,
            prefix=_TMP_PREFIX,
            suffix=".tmp",
            encoding="utf-8",
            delete=False,
        ) as f:
            tmp_path = f.name
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _load_unlocked() -> SelfMergePromotionsFile:
    path = promotions_file_path()
    if not os.path.isfile(path):
        return SelfMergePromotionsFile()
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        msg = f"self_merge_promotions: expected object at {path}"
        raise ValueError(msg)
    return SelfMergePromotionsFile.model_validate(raw)


def _write_unlocked(data: SelfMergePromotionsFile) -> None:
    _atomic_write_json(
        promotions_file_path(),
        data.model_dump(mode="json", by_alias=True),
    )


def _with_file_lock(func: Callable[[], _T]) -> _T:
    lp = _lock_path()
    os.makedirs(os.path.dirname(lp) or ".", exist_ok=True)
    with open(lp, "a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            return func()
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def _merge_tier_by_pr(data: SelfMergePromotionsFile, pr_number: int) -> MergeTier | None:
    for merge in data.merges:
        if merge.pr_number == pr_number:
            return merge.tier
    return None


def _reverted_original_prs(
    data: SelfMergePromotionsFile,
    *,
    tier: MergeTier,
    since: datetime,
) -> set[int]:
    cutoff = _normalise_dt(since)
    reverted: set[int] = set()
    for revert in data.reverts:
        if _normalise_dt(revert.reverted_at) < cutoff:
            continue
        if _merge_tier_by_pr(data, revert.original_pr) == tier:
            reverted.add(revert.original_pr)
    return reverted


def _clean_merge_count(data: SelfMergePromotionsFile, *, now: datetime) -> int:
    tier = data.current_tier
    reverted = _reverted_original_prs(
        data,
        tier=tier,
        since=_normalise_dt(now) - _CLEAN_REVERT_WINDOW,
    )
    return sum(1 for merge in data.merges if merge.tier == tier and merge.pr_number not in reverted)


def _has_recent_revert(data: SelfMergePromotionsFile, *, now: datetime) -> bool:
    tier = data.current_tier
    recent_reverted = _reverted_original_prs(
        data,
        tier=tier,
        since=_normalise_dt(now) - _RECENT_REVERT_BLOCK_WINDOW,
    )
    return bool(recent_reverted)


def _eligible_for_promotion(data: SelfMergePromotionsFile, *, now: datetime) -> bool:
    return (
        data.current_tier != "app-code"
        and _clean_merge_count(data, now=now) >= _GRADUATION_THRESHOLD
        and not _has_recent_revert(data, now=now)
    )


def load_promotions_file() -> SelfMergePromotionsFile:
    """Read the graduation log under the same lock used for writes."""
    return _with_file_lock(_load_unlocked)


def current_tier() -> MergeTier:
    return load_promotions_file().current_tier


def tier_allows_path(path: str, tier: MergeTier) -> bool:
    """Return whether ``tier`` may self-merge a PR touching ``path``."""
    normalised = path.strip()
    while normalised.startswith("./"):
        normalised = normalised[2:]
    if tier == "app-code":
        return True
    if tier == "brain-code" and fnmatch.fnmatchcase(normalised, "apis/brain/**"):
        return True
    return any(fnmatch.fnmatchcase(normalised, pattern) for pattern in _DATA_ONLY_PATTERNS)


def pr_qualifies_for_self_merge(pr_paths: list[str]) -> tuple[bool, str]:
    tier = current_tier()
    disallowed = [path for path in pr_paths if not tier_allows_path(path, tier)]
    if disallowed:
        preview = ", ".join(disallowed[:5])
        suffix = "" if len(disallowed) <= 5 else f", +{len(disallowed) - 5} more"
        return False, f"paths outside current tier ({tier}): {preview}{suffix}"
    return True, f"all paths allowed by current tier ({tier})"


def record_merge(pr_number: int, paths_touched: list[str], merged_at: datetime) -> None:
    """Append a successful Brain self-merge to the graduation log."""

    def _mutate() -> None:
        data = _load_unlocked()
        if any(row.pr_number == pr_number for row in data.merges):
            msg = f"self_merge_promotions: PR #{pr_number} already recorded as merged"
            raise ValueError(msg)
        data.merges.append(
            SelfMergeRecord(
                pr_number=pr_number,
                merged_at=_normalise_dt(merged_at),
                tier=data.current_tier,
                paths_touched=list(paths_touched),
                graduation_eligible=False,
            )
        )
        data.merges[-1].graduation_eligible = _eligible_for_promotion(data, now=merged_at)
        _write_unlocked(data)

    _with_file_lock(_mutate)


def record_revert(
    pr_number: int,
    original_pr: int,
    reason: str,
    reverted_at: datetime,
) -> None:
    """Append a revert record for a Brain self-merged PR."""

    def _mutate() -> None:
        data = _load_unlocked()
        if any(row.pr_number == pr_number for row in data.reverts):
            msg = f"self_merge_promotions: revert PR #{pr_number} already recorded"
            raise ValueError(msg)
        data.reverts.append(
            RevertRecord(
                pr_number=pr_number,
                original_pr=original_pr,
                reverted_at=_normalise_dt(reverted_at),
                reason=reason,
            )
        )
        _write_unlocked(data)

    _with_file_lock(_mutate)


def clean_merge_count() -> int:
    now = _utcnow()

    def _read() -> int:
        return _clean_merge_count(_load_unlocked(), now=now)

    return _with_file_lock(_read)


def eligible_for_promotion() -> bool:
    now = _utcnow()

    def _read() -> bool:
        return _eligible_for_promotion(_load_unlocked(), now=now)

    return _with_file_lock(_read)


def promote() -> PromotionRecord | None:
    """Promote Brain to the next self-merge tier when the N=50 gate is clean."""
    now = _utcnow()

    def _mutate() -> PromotionRecord | None:
        data = _load_unlocked()
        from_tier = data.current_tier
        if from_tier == "app-code" or not _eligible_for_promotion(data, now=now):
            return None
        to_tier = _NEXT_TIER[from_tier]
        count = _clean_merge_count(data, now=now)
        record = PromotionRecord(
            from_tier=from_tier,
            to_tier=to_tier,
            promoted_at=now,
            clean_merge_count_at_promotion=count,
            notes=(
                f"WS-44 graduation: {count} clean {from_tier} self-merges "
                "with no current-tier revert in the last 7 days."
            ),
        )
        data.current_tier = to_tier
        data.promotions.append(record)
        _write_unlocked(data)
        return record

    return _with_file_lock(_mutate)
