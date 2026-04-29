"""One-time idempotent migration: read docs/FINANCIALS.md and seed the Expense store.

Usage (from repo root):
    python apis/brain/scripts/seed_expenses_from_financials_md.py

Behaviour:
  - Parses "One-Time Expenses" and "Monthly Recurring" markdown tables.
  - Maps each row to an Expense with source="imported", status="reimbursed"
    (historical — already paid).
  - Idempotent: uses a deterministic UUID derived from row content — re-runs
    will not duplicate entries.
  - Unparseable rows are logged to apis/brain/data/expenses_backfill_unparsed.txt.
  - Does NOT modify docs/FINANCIALS.md.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("seed_expenses")

# ---------------------------------------------------------------------------
# Repo root resolution
# ---------------------------------------------------------------------------

_ENV_REPO_ROOT = "REPO_ROOT"


def _repo_root() -> Path:
    env = os.environ.get(_ENV_REPO_ROOT, "").strip()
    if env:
        return Path(env)
    # scripts/ -> apis/brain -> apis -> repo root
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".cursor" / "rules").is_dir() and (candidate / "apis" / "brain").is_dir():
            return candidate
    raise RuntimeError("Cannot find repo root; set REPO_ROOT env var")


# ---------------------------------------------------------------------------
# Category mapping (best-effort)
# ---------------------------------------------------------------------------

_CATEGORY_MAP: dict[str, str] = {
    "domain": "domains",
    "domains": "domains",
    "legal": "legal",
    "legal/insurance": "legal",
    "insurance": "legal",
    "infrastructure": "infra",
    "infra": "infra",
    "operations": "ops",
    "operations (google workspace)": "ops",
    "ai/ml": "ai",
    "ai": "ai",
    "content": "misc",
    "tax": "tax",
    "subscription": "tools",
    "tools": "tools",
}

_VALID_CATEGORIES = frozenset(
    {"infra", "ai", "contractors", "tools", "legal", "tax", "misc", "domains", "ops"}
)


def _map_category(raw: str) -> str:
    normalized = raw.strip().lower()
    if normalized in _CATEGORY_MAP:
        return _CATEGORY_MAP[normalized]
    for key, val in _CATEGORY_MAP.items():
        if key in normalized:
            return val
    return "misc"


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------

_AMOUNT_RE = re.compile(r"[\$~]?\s*([\d,]+(?:\.\d+)?)")


def _parse_amount_cents(raw: str) -> int | None:
    """Extract a best-effort dollar amount and convert to cents."""
    raw = raw.strip().replace(",", "")
    # Handle ranges like "$3,201-$3,746" — take the lower bound
    if "-" in raw:
        raw = raw.split("-")[0]
    m = _AMOUNT_RE.search(raw)
    if not m:
        return None
    try:
        dollars = float(m.group(1))
        return int(dollars * 100)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Markdown table parser
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")


def _parse_table_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        m = _TABLE_ROW_RE.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        rows.append(cells)
    return rows


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.match(r"^-+$", c.replace(":", "").strip()) for c in cells if c)


def _find_section(content: str, header: str) -> list[str]:
    """Return lines from header until next ## heading."""
    lines = content.splitlines()
    in_section = False
    result: list[str] = []
    for line in lines:
        if line.startswith("## ") and header.lower() in line.lower():
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# Deterministic UUID from content
# ---------------------------------------------------------------------------


def _content_uuid(content: str) -> str:
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    # Format as UUID v4 (deterministic but UUID-shaped)
    return str(uuid.UUID(h[:32]))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    repo = _repo_root()
    financials_md = repo / "docs" / "FINANCIALS.md"
    if not financials_md.exists():
        logger.error("docs/FINANCIALS.md not found at %s", financials_md)
        sys.exit(1)

    content = financials_md.read_text(encoding="utf-8")
    unparsed: list[str] = []
    imported = 0
    skipped_dup = 0

    now_iso = datetime.now(UTC).isoformat()

    # Import expenses service
    sys.path.insert(0, str(repo / "apis" / "brain"))
    from app.schemas.expenses import Expense
    from app.services.expenses import upsert_expense_raw

    # --- One-Time Expenses ---
    one_time_lines = _find_section(content, "One-Time Expenses")
    rows = _parse_table_rows(one_time_lines)
    header: list[str] = []
    for row in rows:
        if not header:
            header = [c.lower() for c in row]
            continue
        if _is_separator_row(row):
            continue
        if len(row) < 3:
            continue
        try:
            date_str = row[0] if len(row) > 0 else "Unknown"
            item = row[1] if len(row) > 1 else ""
            amount_raw = row[2] if len(row) > 2 else ""
            category_raw = row[3] if len(row) > 3 else "misc"
            notes = row[4] if len(row) > 4 else ""

            if not item or item.startswith("**TOTAL"):
                continue

            amount_cents = _parse_amount_cents(amount_raw)
            if amount_cents is None:
                unparsed.append(f"ONE-TIME: {row}")
                continue

            # Parse date: "Mar 2026" → "2026-03-01"; "TBD" → "2026-01-01"
            occurred_at = _parse_date(date_str)
            category = _map_category(category_raw)

            uid = _content_uuid(f"one-time:{item}:{amount_raw}:{date_str}")
            expense = Expense(
                id=uid,
                vendor=item,
                amount_cents=amount_cents,
                currency="USD",
                category=category,
                status="reimbursed",
                source="imported",
                classified_by="imported",
                occurred_at=occurred_at,
                submitted_at=now_iso,
                approved_at=now_iso,
                reimbursed_at=now_iso,
                notes=notes,
            )
            if upsert_expense_raw(expense):
                imported += 1
                logger.info("Imported one-time: %s ($%.2f)", item, amount_cents / 100)
            else:
                skipped_dup += 1
        except Exception as exc:
            logger.warning("Failed to parse one-time row %s: %s", row, exc)
            unparsed.append(f"ONE-TIME: {row}")

    # --- Monthly Recurring ---
    monthly_lines = _find_section(content, "Monthly Recurring")
    rows = _parse_table_rows(monthly_lines)
    header = []
    for row in rows:
        if not header:
            header = [c.lower() for c in row]
            continue
        if _is_separator_row(row):
            continue
        if len(row) < 2:
            continue
        try:
            service = row[0] if len(row) > 0 else ""
            cost_raw = row[1] if len(row) > 1 else ""
            category_raw = row[2] if len(row) > 2 else "misc"
            notes = row[3] if len(row) > 3 else ""

            if not service or service.startswith("**TOTAL"):
                continue

            amount_cents = _parse_amount_cents(cost_raw)
            if amount_cents is None:
                unparsed.append(f"MONTHLY: {row}")
                continue

            category = _map_category(category_raw)
            uid = _content_uuid(f"monthly:{service}:{cost_raw}")
            expense = Expense(
                id=uid,
                vendor=service,
                amount_cents=amount_cents,
                currency="USD",
                category=category,
                status="reimbursed",
                source="subscription",
                classified_by="imported",
                occurred_at="2026-03-01",  # Representative month
                submitted_at=now_iso,
                approved_at=now_iso,
                reimbursed_at=now_iso,
                notes=f"Monthly recurring. {notes}".strip(". "),
            )
            if upsert_expense_raw(expense):
                imported += 1
                logger.info("Imported monthly: %s ($%.2f/mo)", service, amount_cents / 100)
            else:
                skipped_dup += 1
        except Exception as exc:
            logger.warning("Failed to parse monthly row %s: %s", row, exc)
            unparsed.append(f"MONTHLY: {row}")

    # Write unparsed log
    if unparsed:
        unparsed_path = repo / "apis" / "brain" / "data" / "expenses_backfill_unparsed.txt"
        unparsed_path.parent.mkdir(parents=True, exist_ok=True)
        with unparsed_path.open("a", encoding="utf-8") as f:
            f.write(f"\n--- Run at {now_iso} ---\n")
            f.writelines(line + "\n" for line in unparsed)
        logger.warning("%d rows could not be parsed; see %s", len(unparsed), unparsed_path)

    logger.info(
        "Done. Imported: %d  Skipped (already exists): %d  Unparsed: %d",
        imported,
        skipped_dup,
        len(unparsed),
    )


def _parse_date(raw: str) -> str:
    """Best-effort parse of dates like 'Mar 2026', 'TBD', '2026-03'. Returns YYYY-MM-DD."""
    raw = raw.strip()
    if not raw or raw.upper() == "TBD" or raw.startswith("**"):
        return "2026-01-01"
    # "Mar 2026"
    m = re.match(r"([A-Za-z]{3})\s+(\d{4})", raw)
    if m:
        month_abbr = m.group(1).capitalize()
        year = m.group(2)
        months = {
            "Jan": "01",
            "Feb": "02",
            "Mar": "03",
            "Apr": "04",
            "May": "05",
            "Jun": "06",
            "Jul": "07",
            "Aug": "08",
            "Sep": "09",
            "Oct": "10",
            "Nov": "11",
            "Dec": "12",
        }
        mo = months.get(month_abbr, "01")
        return f"{year}-{mo}-01"
    # "2026-03"
    m2 = re.match(r"(\d{4})-(\d{2})", raw)
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-01"
    return "2026-01-01"


if __name__ == "__main__":
    main()
