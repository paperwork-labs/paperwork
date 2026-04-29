"""Read/write `apis/brain/data/pr_outcomes.json` — merge records + horizon outcomes (WS-62).

Follow-on work: scheduled polling to fill h1/h24/lagging horizons automatically.

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
from typing import TYPE_CHECKING, Any, TypeVar

from app.schemas.pr_outcomes import (
    HorizonLagging,
    OutcomeH1H24,
    OutcomeLaggingHorizon,
    PrOutcome,
    PrOutcomesFile,
    PrOutcomesOutcomes,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_ENV_PATH = "BRAIN_PR_OUTCOMES_JSON"
_TMP_SUFFIX = ".tmp"


def _brain_data_dir() -> str:
    # services/ -> app/ -> brain/ ; data lives at brain/data, not brain/app/data
    here = os.path.dirname(os.path.abspath(__file__))
    brain_app = os.path.dirname(here)
    brain_root = os.path.dirname(brain_app)
    d = os.path.join(brain_root, "data")
    os.makedirs(d, exist_ok=True)
    return d


def outcomes_file_path() -> str:
    """Path to `pr_outcomes.json`; override with ``BRAIN_PR_OUTCOMES_JSON`` for tests."""
    env = os.environ.get(_ENV_PATH, "").strip()
    if env:
        return env
    return os.path.join(_brain_data_dir(), "pr_outcomes.json")


def _lock_path() -> str:
    return outcomes_file_path() + ".lock"


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = f"{path}{_TMP_SUFFIX}"
    raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(raw)
    os.replace(tmp, path)


def _load_unlocked() -> PrOutcomesFile:
    path = outcomes_file_path()
    if not os.path.isfile(path):
        return PrOutcomesFile()
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return PrOutcomesFile()
        return PrOutcomesFile.model_validate(raw)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("pr_outcomes: could not read %s — %s; starting empty", path, e)
        return PrOutcomesFile()


def _write_unlocked(data: PrOutcomesFile) -> None:
    path = outcomes_file_path()
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    _atomic_write_json(path, data.model_dump(mode="json", by_alias=True))


def _with_file_lock(func: Callable[[], _T]) -> _T:
    """Exclusive flock around read-modify-write or read-only use of the JSON file."""
    lp = _lock_path()
    os.makedirs(os.path.dirname(lp) or ".", exist_ok=True)
    with open(lp, "a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            return func()
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def _mutate(mutator: Callable[[PrOutcomesFile], None]) -> None:
    def _go() -> None:
        f = _load_unlocked()
        mutator(f)
        _write_unlocked(f)

    _with_file_lock(_go)


def record_merged_pr(
    pr_number: int,
    merged_at: str,
    merged_by_agent: str,
    agent_model: str,
    subagent_type: str,
    workstream_ids: list[str],
    workstream_types: list[str],
) -> None:
    def _m(data: PrOutcomesFile) -> None:
        if any(r.pr_number == pr_number for r in data.outcomes):
            msg = f"pr_outcomes: PR #{pr_number} already recorded"
            raise ValueError(msg)
        data.outcomes.append(
            PrOutcome(
                pr_number=pr_number,
                merged_at=merged_at,
                merged_by_agent=merged_by_agent,
                agent_model=agent_model,
                subagent_type=subagent_type,
                workstream_ids=list(workstream_ids),
                workstream_types=list(workstream_types),
                outcomes=PrOutcomesOutcomes(),
            )
        )

    _mutate(_m)


def _set_h(
    pr_number: int,
    field: str,
    ci_pass: bool,
    deploy_success: bool,
    reverted: bool,
) -> None:
    snap = OutcomeH1H24(
        ci_pass=ci_pass,
        deploy_success=deploy_success,
        reverted=reverted,
    )

    def _m(data: PrOutcomesFile) -> None:
        for row in data.outcomes:
            if row.pr_number == pr_number:
                if field == "h1":
                    row.outcomes.h1 = snap
                else:
                    row.outcomes.h24 = snap
                return
        msg = f"pr_outcomes: unknown pr_number {pr_number}"
        raise ValueError(msg)

    _mutate(_m)


def update_outcome_h1(
    pr_number: int,
    ci_pass: bool,
    deploy_success: bool,
    reverted: bool,
) -> None:
    _set_h(pr_number, "h1", ci_pass, deploy_success, reverted)


def update_outcome_h24(
    pr_number: int,
    ci_pass: bool,
    deploy_success: bool,
    reverted: bool,
) -> None:
    _set_h(pr_number, "h24", ci_pass, deploy_success, reverted)


def update_outcome_lagging(
    pr_number: int,
    horizon: HorizonLagging,
    objective_metric_delta: dict[str, float],
) -> None:
    block = OutcomeLaggingHorizon(objective_metric_delta=dict(objective_metric_delta))

    def _m(data: PrOutcomesFile) -> None:
        for row in data.outcomes:
            if row.pr_number == pr_number:
                if horizon == "d7":
                    row.outcomes.d7 = block
                elif horizon == "d14":
                    row.outcomes.d14 = block
                else:
                    row.outcomes.d30 = block
                return
        msg = f"pr_outcomes: unknown pr_number {pr_number}"
        raise ValueError(msg)

    _mutate(_m)


def get_pr_outcome(pr_number: int) -> PrOutcome | None:
    def _read() -> PrOutcome | None:
        data = _load_unlocked()
        for row in data.outcomes:
            if row.pr_number == pr_number:
                return row
        return None

    return _with_file_lock(_read)


def list_outcomes_for_workstream(workstream_id: str) -> list[PrOutcome]:
    def _read() -> list[PrOutcome]:
        data = _load_unlocked()
        return [o for o in data.outcomes if workstream_id in o.workstream_ids]

    return _with_file_lock(_read)


def list_pr_outcomes_for_query(
    *,
    workstream_id: str | None = None,
    limit: int = 50,
) -> list[PrOutcome]:
    """Return outcomes, newest by ``merged_at`` first, for admin list API."""

    def _read() -> list[PrOutcome]:
        data = _load_unlocked()
        rows = data.outcomes
        if workstream_id is not None:
            rows = [o for o in rows if workstream_id in o.workstream_ids]
        rows = sorted(rows, key=lambda o: o.merged_at, reverse=True)
        return rows[: max(0, limit)]

    return _with_file_lock(_read)
