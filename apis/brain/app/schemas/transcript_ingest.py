"""Request/response models for Cursor transcript ingestion.

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic serializes datetimes

from pydantic import BaseModel, Field, model_validator


class TranscriptEpisode(BaseModel):
    """One extracted turn from a Cursor agent JSONL transcript."""

    transcript_id: str
    turn_index: int
    user_message: str
    assistant_message: str
    summary: str | None = None
    entities: list[str] = Field(default_factory=list)
    persona_slugs: list[str] = Field(default_factory=list)
    timestamp: datetime | None = None


class IngestResult(BaseModel):
    """Outcome of ingesting a single transcript file."""

    transcript_id: str
    episodes_created: int
    entities_extracted: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    skipped: bool = False


class TranscriptIngestRequest(BaseModel):
    """Single-file ingest: absolute path or transcript id under configured root."""

    file_path: str | None = None
    transcript_id: str | None = None

    @model_validator(mode="after")
    def _one_identifier(self) -> TranscriptIngestRequest:
        fp = (self.file_path or "").strip()
        tid = (self.transcript_id or "").strip()
        if bool(fp) == bool(tid):
            msg = "Provide exactly one of file_path or transcript_id"
            raise ValueError(msg)
        return self


class TranscriptIngestBatchRequest(BaseModel):
    """Batch ingest: recursively scan a directory for *.jsonl files."""

    directory: str = Field(..., min_length=1)


class TranscriptIngestBatchResult(BaseModel):
    """Aggregate stats for a directory ingest run."""

    scanned_files: int
    ingested_files: int
    skipped_files: int
    total_episodes_created: int
    errors: list[str]
    file_results: list[IngestResult]
