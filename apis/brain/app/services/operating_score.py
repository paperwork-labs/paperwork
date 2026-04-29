"""Paperwork Operating Score (POS) composite — reads spec YAML, runs pillar collectors.

Weekly composite target and graduation gates drive L4/L5 autonomy narrative.

medallion: ops
"""

from __future__ import annotations

import fcntl
import importlib
import json
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import yaml

from app.schemas.operating_score import (
    OperatingScoreEntry,
    OperatingScoreFile,
    OperatingScoreSpec,
    Pillar,
    PillarScore,
    ScoreGates,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_ENV_SPEC = "BRAIN_OPERATING_SCORE_SPEC_YAML"
_ENV_JSON = "BRAIN_OPERATING_SCORE_JSON"
_TMP_SUFFIX = ".tmp"


def _brain_services_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _brain_data_dir() -> str:
    brain_app = os.path.dirname(_brain_services_dir())
    return os.path.join(brain_app, "data")


def operating_score_spec_path() -> str:
    env = os.environ.get(_ENV_SPEC, "").strip()
    if env:
        return env
    return os.path.join(_brain_data_dir(), "operating_score_spec.yaml")


def operating_score_file_path() -> str:
    env = os.environ.get(_ENV_JSON, "").strip()
    if env:
        return env
    return os.path.join(_brain_data_dir(), "operating_score.json")


def _lock_path() -> str:
    return operating_score_file_path() + ".lock"


def load_spec() -> OperatingScoreSpec:
    """Load POS spec from YAML — pillar weights MUST sum to 100 (validated by Pydantic)."""
    raw_path = Path(operating_score_spec_path())
    if not raw_path.is_file():
        msg = f"operating_score spec missing: {raw_path}"
        raise FileNotFoundError(msg)
    raw_doc = yaml.safe_load(raw_path.read_text(encoding="utf-8"))
    if not isinstance(raw_doc, dict):
        msg = "operating_score spec YAML must be a mapping"
        raise ValueError(msg)
    return OperatingScoreSpec.model_validate(raw_doc)


def _collect_pillar(p: Pillar) -> tuple[float, bool, str]:
    try:
        mod = importlib.import_module(f"app.services.operating_score_collectors.{p.id}")
        collector = getattr(mod, "collect", None)
        if not callable(collector):
            return (50.0, False, "not yet measurable")
        raw = collector()
        if raw is None:
            return (50.0, False, "not yet measurable")
        score_raw, measured, notes = raw
        score_f = float(score_raw)
        measured_b = bool(measured)
        notes_s = str(notes).strip()
        score_f = max(0.0, min(100.0, score_f))
        if not notes_s:
            notes_s = "not yet measurable"
        return (score_f, measured_b, notes_s)
    except Exception:
        logger.exception("operating_score: collector failed for pillar %s", p.id)
        return (50.0, False, "not yet measurable")


def _gates_for_entry(
    spec: OperatingScoreSpec,
    total: float,
    pillars_scores: dict[str, PillarScore],
    prior_totals_tail: list[float],
) -> ScoreGates:
    """``prior_totals_tail`` excludes the POS under construction (only prior weeks)."""
    lg = spec.graduation_gates
    lowest = (
        sorted(pillars_scores.items(), key=lambda kv: (kv[1].score, kv[0]))[0][0]
        if pillars_scores
        else ""
    )

    min_pillar_score = min((ps.score for ps in pillars_scores.values()), default=0.0)
    l4_pass = bool(total >= float(lg.l4.min_total) and min_pillar_score >= float(lg.l4.min_pillar))

    sus = max(1, int(lg.l5.sustained_weeks))
    min_total_l5 = float(lg.l5.min_total)
    chain = [*prior_totals_tail, total]
    tail_vals = chain[-sus:]
    l5_pass = len(tail_vals) >= sus and all(x >= min_total_l5 for x in tail_vals)

    return ScoreGates(
        l4_pass=l4_pass,
        l5_pass=l5_pass,
        lowest_pillar=lowest,
    )


def compute_score() -> OperatingScoreEntry:
    spec = load_spec()
    pillars_out: dict[str, PillarScore] = {}

    rolling_total_weighted = 0.0
    for pillar in spec.pillars:
        raw_s, measured, notes = _collect_pillar(pillar)
        w_frac = pillar.weight / 100.0
        weighted = raw_s * w_frac
        rolling_total_weighted += weighted
        pillars_out[pillar.id] = PillarScore(
            score=raw_s,
            weight=pillar.weight,
            weighted=weighted,
            measured=measured,
            notes=notes,
        )

    rounded_total = round(rolling_total_weighted, 4)

    file_before = read_operating_file()
    prior_hist = list(file_before.history)
    prior_totals = [float(e.total) for e in prior_hist]

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    gates = _gates_for_entry(spec, rounded_total, pillars_out, prior_totals)

    return OperatingScoreEntry(
        computed_at=now,
        total=rounded_total,
        pillars=pillars_out,
        gates=gates,
    )


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = f"{path}{_TMP_SUFFIX}"
    raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
    with open(tmp, "w", encoding="utf-8") as wf:
        wf.write(raw)
    os.replace(tmp, path)


def _with_file_lock_shared(fn: Callable[[], _T]) -> _T:
    lp = _lock_path()
    os.makedirs(os.path.dirname(lp) or ".", exist_ok=True)
    with open(lp, "a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_SH)
        try:
            return fn()
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def read_operating_file() -> OperatingScoreFile:
    """Read ``operating_score.json`` under a shared ``flock``."""
    return _with_file_lock_shared(latest_file_unlocked)


def latest_file_unlocked() -> OperatingScoreFile:
    path = operating_score_file_path()
    if not os.path.isfile(path):
        return OperatingScoreFile()
    try:
        with open(path, encoding="utf-8") as wf:
            raw = json.load(wf)
        if not isinstance(raw, dict):
            return OperatingScoreFile()
        return OperatingScoreFile.model_validate(raw)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("operating_score: could not read %s — %s; starting empty", path, e)
        return OperatingScoreFile()


def _write_unlocked(data: OperatingScoreFile) -> None:
    path = operating_score_file_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    _atomic_write_json(path, data.model_dump(mode="json", by_alias=True))


def _with_file_lock(fn: Callable[[], _T]) -> _T:
    lp = _lock_path()
    os.makedirs(os.path.dirname(lp) or ".", exist_ok=True)
    with open(lp, "a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def record_score(entry: OperatingScoreEntry) -> None:
    """Append entry to rotating history + set ``current``. Exclusive lock."""

    def _apply() -> None:
        blob = latest_file_unlocked()
        blob.current = entry
        blob.history = [*blob.history, entry]
        _write_unlocked(blob)

    _with_file_lock(_apply)


def latest_score() -> OperatingScoreEntry | None:
    return read_operating_file().current
