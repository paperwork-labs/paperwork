"""Shared helpers and constants for IBKR sync pipeline."""

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_CURRENCY = "USD"
DEFAULT_ASSET_CATEGORY = "STK"


def serialize_for_json(data: Any) -> Any:
    """Convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(data, dict):
        return {k: serialize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [serialize_for_json(item) for item in data]
    if isinstance(data, datetime):
        return data.isoformat()
    return data


def coerce_date(value: Any) -> date | None:
    """Coerce various date-like values to a date object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        return None


def safe_float(value: Any, default: float = 0.0) -> float:
    """Parse a value to float, returning *default* on failure."""
    try:
        return float(value or default)
    except (ValueError, TypeError):
        return default


def delete_account_data(db: Session, account_id: int, model_class: type) -> int:
    """Delete all rows in *model_class* for a given broker account.

    Returns the number of rows deleted.
    """
    count = db.query(model_class).filter(
        model_class.account_id == account_id
    ).delete(synchronize_session="fetch")
    return count


def delete_account_data_by_broker(db: Session, broker_account_id: int, model_class: type) -> int:
    """Delete rows keyed on ``broker_account_id`` instead of ``account_id``."""
    count = db.query(model_class).filter(
        model_class.broker_account_id == broker_account_id
    ).delete(synchronize_session="fetch")
    return count
