"""Brain-canonical Bill (invoice) store — JSON-backed, file-locked.

State machine:
  pending → approved → paid
  pending → rejected
  approved → rejected

Terminal: paid, rejected (no further transitions).

WS-76 PR-26. Storage: apis/brain/data/bills.json

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import uuid
from collections.abc import Callable  # noqa: TC003
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.bill import Bill, BillCreate, BillsListPage, BillStatus, BillUpdate

logger = logging.getLogger(__name__)

_ALLOWED_TRANSITIONS: dict[BillStatus, set[BillStatus]] = {
    "pending": {"approved", "rejected"},
    "approved": {"paid", "rejected"},
    "paid": set(),
    "rejected": set(),
}

_ENV_BILLS_JSON = "BRAIN_BILLS_JSON"
_ENV_REPO_ROOT = "REPO_ROOT"


def _brain_root() -> Path:
    here = Path(__file__).resolve()
    return here.parent.parent.parent


def _data_dir() -> Path:
    env = os.environ.get(_ENV_REPO_ROOT, "").strip()
    if env:
        return Path(env) / "apis" / "brain" / "data"
    return _brain_root() / "data"


def _bills_json_path() -> Path:
    env = os.environ.get(_ENV_BILLS_JSON, "").strip()
    if env:
        return Path(env)
    return _data_dir() / "bills.json"


def _read_bills_raw() -> list[dict[str, Any]]:
    path = _bills_json_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "bills" in data:
            envelope = data["bills"]
            if isinstance(envelope, list):
                return envelope
        return []
    except (json.JSONDecodeError, OSError):
        logger.warning("bills.json unreadable — treating as empty")
        return []


def _write_bills_raw(rows: list[dict[str, Any]]) -> None:
    path = _bills_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _locked_read_write(
    fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> None:
    lock_path = _bills_json_path().with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            rows = _read_bills_raw()
            rows = fn(rows)
            _write_bills_raw(rows)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _parse_bill(raw: dict[str, Any]) -> Bill | None:
    try:
        return Bill.model_validate(raw)
    except Exception:
        logger.warning("Skipping unparseable bill row: %s", raw.get("id"))
        return None


def _assert_transition(current: BillStatus, target: BillStatus) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Cannot transition {current} → {target}")


def create_bill(payload: BillCreate) -> Bill:
    now = datetime.now(UTC).isoformat()
    bill = Bill(
        id=str(uuid.uuid4()),
        vendor_id=payload.vendor_id,
        status="pending",
        due_date=payload.due_date,
        amount_usd=payload.amount_usd,
        description=payload.description,
        attachments=list(payload.attachments),
        created_at=now,
        updated_at=now,
    )
    row = bill.model_dump(mode="json")

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows.append(row)
        return rows

    _locked_read_write(mutate)
    return bill


def get_bill(bill_id: str) -> Bill | None:
    rows = _read_bills_raw()
    for raw in rows:
        if raw.get("id") == bill_id:
            return _parse_bill(raw)
    return None


def list_bills(*, status: BillStatus | None = None) -> BillsListPage:
    rows = _read_bills_raw()
    items: list[Bill] = []
    for raw in rows:
        bill = _parse_bill(raw)
        if bill is None:
            continue
        if status is not None and bill.status != status:
            continue
        items.append(bill)
    items.sort(key=lambda b: b.created_at, reverse=True)
    return BillsListPage(items=items, total=len(items))


def update_bill(bill_id: str, patch: BillUpdate) -> Bill | None:
    result: list[Bill] = []

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, raw in enumerate(rows):
            if raw.get("id") != bill_id:
                continue
            bill = _parse_bill(raw)
            if bill is None:
                continue
            data = patch.model_dump(exclude_none=True)
            if not data:
                result.append(bill)
                return rows
            updated = bill.model_copy(update={**data, "updated_at": datetime.now(UTC).isoformat()})
            rows[i] = updated.model_dump(mode="json")
            result.append(updated)
            return rows
        return rows

    _locked_read_write(mutate)
    return result[0] if result else None


def delete_bill(bill_id: str) -> bool:
    removed: list[bool] = [False]

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        new_rows = [r for r in rows if r.get("id") != bill_id]
        removed[0] = len(new_rows) != len(rows)
        return new_rows

    _locked_read_write(mutate)
    return removed[0]


def _transition(bill_id: str, target: BillStatus) -> Bill | None:
    result: list[Bill] = []

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, raw in enumerate(rows):
            if raw.get("id") != bill_id:
                continue
            bill = _parse_bill(raw)
            if bill is None:
                continue
            _assert_transition(bill.status, target)
            now = datetime.now(UTC).isoformat()
            updated = bill.model_copy(update={"status": target, "updated_at": now})
            rows[i] = updated.model_dump(mode="json")
            result.append(updated)
            return rows
        return rows

    _locked_read_write(mutate)
    return result[0] if result else None


def approve_bill(bill_id: str) -> Bill | None:
    return _transition(bill_id, "approved")


def pay_bill(bill_id: str) -> Bill | None:
    return _transition(bill_id, "paid")


def reject_bill(bill_id: str) -> Bill | None:
    return _transition(bill_id, "rejected")
