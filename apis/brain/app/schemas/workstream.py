"""Pydantic models for Studio workstreams.json — parity with Zod in ``schema.ts``."""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Parity: Studio ``schema.ts`` — ``DISPATCH_COOLDOWN_MS`` / ``dispatchableWorkstreams``.
DISPATCH_COOLDOWN_MS = 4 * 60 * 60 * 1000

_ID_RE = re.compile(r"^WS-\d{2,3}-[a-z0-9-]+$")
_TRACK_RE = re.compile(r"^[A-Z][0-9A-Z]{0,2}$")
_BRIEF_TAG_RE = re.compile(r"^track:[a-z0-9-]+$")

WorkstreamStatus = Literal["pending", "in_progress", "blocked", "completed", "cancelled"]
WorkstreamOwner = Literal["brain", "founder", "opus"]


class Workstream(BaseModel):
    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=3, max_length=100)
    track: str
    priority: int = Field(..., ge=0)
    status: WorkstreamStatus
    percent_done: int = Field(..., ge=0, le=100)
    owner: WorkstreamOwner
    brief_tag: str
    blockers: list[str] = Field(default_factory=list)
    last_pr: int | None = Field(None, gt=0)
    last_activity: str
    last_dispatched_at: str | None
    notes: str = Field(default="", max_length=500)
    estimated_pr_count: int | None = Field(None, gt=0)
    github_actions_workflow: str | None = None
    related_plan: str | None = None
    updated_at: str | None = None
    override_percent: int | None = Field(None, ge=0, le=100)
    derived_percent: int | None = Field(None, ge=0, le=100)
    pr_url: str | None = None
    prs: list[int] | None = None
    pr_numbers: list[int] | None = None

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError("id must match WS-<NN>-<kebab-slug>")
        return v

    @field_validator("track")
    @classmethod
    def _track_shape(cls, v: str) -> str:
        if not _TRACK_RE.match(v):
            raise ValueError(
                "track must be uppercase letter optionally followed by 1-2 digits/letters"
            )
        return v

    @field_validator("brief_tag")
    @classmethod
    def _brief_tag_shape(cls, v: str) -> str:
        if not _BRIEF_TAG_RE.match(v):
            raise ValueError("brief_tag must be 'track:<kebab-slug>'")
        return v

    @field_validator("blockers")
    @classmethod
    def _blockers_min_len(cls, v: list[str]) -> list[str]:
        for b in v:
            if len(b) < 3:
                raise ValueError("each blocker string must be at least 3 characters")
        return v


class WorkstreamsFile(BaseModel):
    version: Literal[1]
    updated: str
    workstreams: list[Workstream]

    @model_validator(mode="after")
    def _cross_field_invariants(self) -> WorkstreamsFile:
        ids = [w.id for w in self.workstreams]
        if len(set(ids)) != len(ids):
            raise ValueError("Workstream ids must be unique")
        prios = [w.priority for w in self.workstreams]
        if len(set(prios)) != len(prios):
            raise ValueError(
                "Workstream priorities must be unique — drag-reorder relies on stable ordering"
            )
        for ws in self.workstreams:
            if ws.status == "completed" and ws.percent_done != 100:
                raise ValueError(
                    f"{ws.id}: completed status requires percent_done=100 (got {ws.percent_done})"
                )
            if ws.status == "cancelled" and ws.percent_done != 0:
                raise ValueError(
                    f"{ws.id}: cancelled status requires percent_done=0 (got {ws.percent_done})"
                )
            if ws.status == "blocked" and len(ws.blockers) == 0:
                raise ValueError(
                    f"{ws.id}: blocked status requires at least one entry in blockers[]"
                )
        return self


def _iso_to_unix_ms(iso: str) -> int | None:
    try:
        s = iso.replace("Z", "+00:00") if iso.endswith("Z") else iso
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def dispatchable_workstreams(
    file: WorkstreamsFile,
    n: int = 3,
    now_ms: int | None = None,
) -> list[Workstream]:
    """Mirror TS ``dispatchableWorkstreams`` in ``apps/studio/src/lib/workstreams/schema.ts``.

    Selection order and filters must stay identical for the same logical input.
    """
    if now_ms is None:
        now_ms = int(time.time() * 1000)

    def _last_dispatched_eligible(last_iso: str | None) -> bool:
        if last_iso is None:
            return True
        last_ms = _iso_to_unix_ms(last_iso)
        if last_ms is None:
            # Match JS: ``Date.parse`` invalid → NaN → comparison fails → not dispatchable.
            return False
        return now_ms - last_ms > DISPATCH_COOLDOWN_MS

    out: list[Workstream] = []
    for w in file.workstreams:
        if w.owner != "brain":
            continue
        if w.status not in ("pending", "in_progress"):
            continue
        if len(w.blockers) != 0:
            continue
        if not _last_dispatched_eligible(w.last_dispatched_at):
            continue
        out.append(w)
    out.sort(key=lambda x: x.priority)
    return out[:n]


def workstreams_file_to_json_dict(file: WorkstreamsFile) -> dict[str, Any]:
    """Serialize for ``json.dumps`` (plain dicts, JSON-friendly)."""
    return file.model_dump(mode="json")
