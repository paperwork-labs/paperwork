"""Request/response models for persona-driven PR review (Brain Autopilot).

medallion: brain-autopilot
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PersonaReviewVerdict = Literal["approve", "request_changes", "comment"]
CommentSeverity = Literal["info", "warning", "error"]


class PersonaReviewRequest(BaseModel):
    """Body for POST /admin/persona-review."""

    pr_number: int = Field(..., ge=1, description="GitHub (or host) pull request number.")
    persona_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Persona slug, e.g. cto, cfo.",
    )
    diff_summary: str = Field(
        ...,
        min_length=1,
        description="Summary or excerpt of the PR diff to review.",
    )


class PersonaReviewComment(BaseModel):
    """A single review comment (file/line optional when the note is general)."""

    file: str = Field(..., description="Path relative to repo root, or '*' for general.")
    line: int | None = Field(None, description="1-based line in the file, if applicable.")
    body: str = Field(..., min_length=1)
    severity: CommentSeverity = "info"


class MemoryCitation(BaseModel):
    """A cited memory result supporting the review."""

    source: str = Field(..., description="Episode source or provenance label.")
    snippet: str = Field(..., description="Short excerpt (e.g. summary line).")


class PersonaReviewResult(BaseModel):
    """Structured persona review payload returned inside success_response data."""

    persona_id: str
    verdict: PersonaReviewVerdict
    comments: list[PersonaReviewComment]
    memory_citations: list[MemoryCitation]
