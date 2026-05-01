"""Append-only error ingestion store for Wave PROBE PR-PB3.

medallion: ops
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from app.schemas.error_ingest import (
    ErrorAggregate,
    ErrorAggregatesFile,
    ErrorIngestRecord,
    ErrorIngestRequest,
)

ERROR_CAP = 10_000
_TMP_SUFFIX = ".tmp"
_ENV_DATA_DIR = "BRAIN_DATA_DIR"
_ENV_ERRORS_JSONL = "BRAIN_ERROR_INGEST_JSONL"
_ENV_AGGREGATES_JSON = "BRAIN_ERROR_AGGREGATES_JSON"
_WHITESPACE = re.compile(r"\s+")

_T = TypeVar("_T")


def _brain_data_dir() -> Path:
    env = os.environ.get(_ENV_DATA_DIR, "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data"


def errors_jsonl_path() -> Path:
    env = os.environ.get(_ENV_ERRORS_JSONL, "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "error_ingest.jsonl"


def aggregates_json_path() -> Path:
    env = os.environ.get(_ENV_AGGREGATES_JSON, "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "error_aggregates.json"


def _lock_path() -> Path:
    return errors_jsonl_path().with_suffix(".lock")


def _with_lock(func: Callable[[], _T]) -> _T:
    lock = _lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            return func()
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, data: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + _TMP_SUFFIX)
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _normalize_message(message: str) -> str:
    return _WHITESPACE.sub(" ", message.strip().lower())


def _first_stack_frames(stack: str | None) -> list[str]:
    if not stack:
        return []
    return [_WHITESPACE.sub(" ", line.strip()) for line in stack.splitlines() if line.strip()][:3]


def compute_fingerprint(message: str, stack: str | None) -> str:
    source = "\n".join([_normalize_message(message), *_first_stack_frames(stack)])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _read_records_unlocked() -> list[ErrorIngestRecord]:
    path = errors_jsonl_path()
    if not path.is_file():
        return []

    records: list[ErrorIngestRecord] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            records.append(ErrorIngestRecord.model_validate(raw))
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(
                f"Invalid error ingest record at {path}:{line_number}: {exc}"
            ) from exc
    return records


def _write_records_unlocked(records: list[ErrorIngestRecord]) -> None:
    path = errors_jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        json.dumps(record.model_dump(mode="json"), sort_keys=True) for record in records
    )
    path.write_text(f"{payload}\n" if payload else "", encoding="utf-8")


def _read_aggregates_unlocked() -> ErrorAggregatesFile:
    path = aggregates_json_path()
    if not path.is_file():
        return ErrorAggregatesFile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ErrorAggregatesFile.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Invalid error aggregate store at {path}: {exc}") from exc


def _write_aggregates_unlocked(store: ErrorAggregatesFile) -> None:
    _atomic_write(aggregates_json_path(), store.model_dump(mode="json", by_alias=True))


def append_error(body: ErrorIngestRequest) -> ErrorIngestRecord:
    now = datetime.now(UTC)
    fingerprint = body.fingerprint or compute_fingerprint(body.message, body.stack)
    record = ErrorIngestRecord(
        **body.model_dump(exclude={"fingerprint"}),
        id=str(uuid.uuid4()),
        ingested_at=now,
        fingerprint=fingerprint,
    )

    def _write() -> ErrorIngestRecord:
        path = errors_jsonl_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")

        store = _read_aggregates_unlocked()
        existing = store.fingerprints.get(fingerprint)
        if existing is None:
            store.fingerprints[fingerprint] = ErrorAggregate(
                fingerprint=fingerprint,
                count=1,
                first_seen=now,
                last_seen=now,
                products_affected=[body.product],
                message=body.message,
                severity=body.severity,
            )
        else:
            products = sorted({*existing.products_affected, body.product})
            store.fingerprints[fingerprint] = existing.model_copy(
                update={
                    "count": existing.count + 1,
                    "last_seen": now,
                    "products_affected": products,
                    "message": body.message,
                    "severity": body.severity,
                }
            )
        _write_aggregates_unlocked(store)
        return record

    return _with_lock(_write)


def prune_errors_if_needed() -> None:
    def _prune() -> None:
        records = _read_records_unlocked()
        if len(records) <= ERROR_CAP:
            return
        _write_records_unlocked(records[-ERROR_CAP:])

    _with_lock(_prune)


def query_recent_errors(
    *,
    product: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    since_utc = _as_utc(since)

    def _query() -> list[dict[str, Any]]:
        records = _read_records_unlocked()
        matched: list[ErrorIngestRecord] = []
        for record in reversed(records):
            if product and record.product != product:
                continue
            if since_utc and record.ingested_at < since_utc:
                continue
            matched.append(record)
            if len(matched) >= limit:
                break
        return [record.model_dump(mode="json") for record in matched]

    return _with_lock(_query)


def query_aggregates(*, since: datetime | None = None, limit: int = 50) -> list[dict[str, Any]]:
    since_utc = _as_utc(since)

    def _query_from_recent() -> list[dict[str, Any]]:
        records = [
            record
            for record in _read_records_unlocked()
            if since_utc is None or record.ingested_at >= since_utc
        ]
        by_fingerprint: dict[str, list[ErrorIngestRecord]] = {}
        for record in records:
            by_fingerprint.setdefault(record.fingerprint, []).append(record)

        counts = Counter({fingerprint: len(items) for fingerprint, items in by_fingerprint.items()})
        rows: list[dict[str, Any]] = []
        for fingerprint, _count in counts.most_common(limit):
            items = by_fingerprint[fingerprint]
            first = min(items, key=lambda item: item.ingested_at)
            last = max(items, key=lambda item: item.ingested_at)
            rows.append(
                {
                    "fingerprint": fingerprint,
                    "count": len(items),
                    "first_seen": first.ingested_at.isoformat(),
                    "last_seen": last.ingested_at.isoformat(),
                    "products_affected": sorted({item.product for item in items}),
                    "message": last.message,
                    "severity": last.severity,
                }
            )
        return rows

    def _query_from_store() -> list[dict[str, Any]]:
        store = _read_aggregates_unlocked()
        rows = sorted(
            store.fingerprints.values(),
            key=lambda item: (item.count, item.last_seen),
            reverse=True,
        )
        return [row.model_dump(mode="json") for row in rows[:limit]]

    return _with_lock(_query_from_recent if since_utc is not None else _query_from_store)
