"""One-shot backfill: migrate legacy JSON conversation files → Postgres.

Run ONCE on the first production deploy of the T1.0d Postgres-canonical
migration BEFORE restarting the Brain service.  See the full runbook at
``docs/runbooks/BRAIN_CONVERSATIONS_BACKFILL.md``.

Usage (from repo root or from apis/brain/):

    # dry-run first — shows what WOULD be written:
    python -m apis.brain.scripts.backfill_conversations_to_postgres --dry-run

    # actual backfill:
    python -m apis.brain.scripts.backfill_conversations_to_postgres

    # override data directory (default: auto-detected from REPO_ROOT or file layout):
    python -m apis.brain.scripts.backfill_conversations_to_postgres \\
        --data-dir /path/to/apis/brain/data

Exit codes
----------
0 — success (inserted + skipped == scanned, errors == 0)
1 — errors > 0 OR counter drift detected (inserted + skipped ≠ scanned)

Safety invariants (no-silent-fallback.mdc)
------------------------------------------
- ``--dry-run`` reads every JSON file but commits nothing.
- Idempotent: existing rows (matched by ``conversations.id``) are skipped.
- Counter assertion: ``inserted + skipped + errors == scanned`` checked at end.
- Non-zero exit code on any error or counter drift.
- JSON files are NOT deleted by this script — remove them in a follow-up PR
  after verifying production reads from Postgres successfully.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("backfill_conversations")


def _resolve_data_dir(override: str | None) -> Path:
    if override:
        return Path(override)
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data"
    # Heuristic: walk up from this script to the brain root
    here = Path(__file__).resolve()
    brain_root = here.parent.parent  # scripts/ -> brain/
    return brain_root / "data"


def _load_json_file(path: Path) -> dict[str, Any] | None:
    """Load a single conversation JSON file.  Returns None on parse error."""
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("backfill: failed to read %s: %s", path, exc)
        return None


def _coerce_datetime(val: Any) -> datetime | None:
    """Parse an ISO datetime string or passthrough a datetime; returns None on failure."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=UTC)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


async def _row_exists(conn: Any, table: str, row_id: uuid.UUID) -> bool:
    from sqlalchemy import text

    result = await conn.execute(
        text(f"SELECT 1 FROM {table} WHERE id = :id"),
        {"id": row_id},
    )
    return result.first() is not None


async def _backfill(data_dir: Path, dry_run: bool) -> int:
    """Core async backfill logic.  Returns exit code (0 = success)."""
    conversations_dir = data_dir / "conversations"

    if not conversations_dir.exists():
        logger.info("backfill: no conversations dir at %s — nothing to do", conversations_dir)
        return 0

    json_files = sorted(conversations_dir.glob("*.json"))
    scanned = len(json_files)
    inserted = 0
    skipped = 0
    errors = 0

    logger.info("backfill: scanned=%d file_count (dry_run=%s)", scanned, dry_run)

    if scanned == 0:
        logger.info("backfill: scanned=0 file_count, inserted=0, skipped=0, errors=0 — done")
        return 0

    # Import app modules here so sys.path is resolved by the time we call them.
    # The script is expected to run from the repo root or with PYTHONPATH set.
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.config import settings
    except ImportError as exc:
        logger.error(
            "backfill: cannot import app modules — run from repo root with "
            "PYTHONPATH=apis/brain or `python -m apis.brain.scripts...`: %s",
            exc,
        )
        return 1

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    try:
        for json_path in json_files:
            conv_id_str = json_path.stem  # filename without .json
            try:
                conv_uuid = uuid.UUID(conv_id_str)
            except ValueError:
                logger.warning(
                    "backfill: skipping %s — stem %r is not a UUID", json_path.name, conv_id_str
                )
                errors += 1
                continue

            raw = _load_json_file(json_path)
            if raw is None:
                errors += 1
                continue

            # Validate required fields
            title = raw.get("title", "").strip()
            if not title:
                logger.warning("backfill: skipping %s — missing title", json_path.name)
                errors += 1
                continue

            created_at = _coerce_datetime(raw.get("created_at")) or datetime.now(UTC)
            updated_at = _coerce_datetime(raw.get("updated_at")) or created_at

            # Build metadata JSONB (same structure as conversations.py)
            meta: dict[str, Any] = {
                "tags": raw.get("tags", []),
                "urgency": raw.get("urgency", "normal"),
                "persona": raw.get("persona"),
                "product_slug": raw.get("product_slug"),
                "sentiment": raw.get("sentiment"),
                "participants": raw.get("participants", []),
                "status": raw.get("status", "open"),
                "snooze_until": raw.get("snooze_until"),
                "parent_action_id": raw.get("parent_action_id"),
                "links": raw.get("links"),
                "needs_founder_action": raw.get("needs_founder_action", False),
                "organization_id": raw.get("organization_id"),
            }

            messages: list[dict[str, Any]] = raw.get("messages", [])

            if dry_run:
                logger.info(
                    "backfill [DRY-RUN]: would insert conv %s (%r) with %d message(s)",
                    conv_uuid,
                    title,
                    len(messages),
                )
                inserted += 1
                continue

            async with engine.connect() as conn, conn.begin():
                # Check for existing row
                exists_result = await conn.execute(
                    text("SELECT 1 FROM conversations WHERE id = :id"),
                    {"id": conv_uuid},
                )
                if exists_result.first() is not None:
                    logger.debug("backfill: skipping existing conv %s", conv_uuid)
                    skipped += 1
                    continue

                # Insert conversation row
                try:
                    await conn.execute(
                        text(
                            "INSERT INTO conversations "
                            "(id, title, created_at, updated_at, metadata) "
                            "VALUES (:id, :title, :created_at, :updated_at, :meta::jsonb) "
                            "ON CONFLICT (id) DO NOTHING"
                        ),
                        {
                            "id": conv_uuid,
                            "title": title,
                            "created_at": created_at,
                            "updated_at": updated_at,
                            "meta": json.dumps(meta),
                        },
                    )
                except Exception as exc:
                    logger.error("backfill: failed to insert conv %s: %s", conv_uuid, exc)
                    errors += 1
                    continue

                # Insert messages
                msg_errors = 0
                for msg_raw in messages:
                    msg_id_str = msg_raw.get("id", "")
                    try:
                        msg_uuid = uuid.UUID(str(msg_id_str))
                    except ValueError:
                        logger.warning(
                            "backfill: skipping message with invalid id %r in conv %s",
                            msg_id_str,
                            conv_uuid,
                        )
                        msg_errors += 1
                        continue

                    body_md = msg_raw.get("body_md", "")
                    msg_created_at = _coerce_datetime(msg_raw.get("created_at")) or created_at

                    author_raw = msg_raw.get("author", {})
                    author_kind = (
                        author_raw.get("kind", "founder")
                        if isinstance(author_raw, dict)
                        else "founder"
                    )
                    role = "persona" if author_kind == "persona" else "user"
                    persona_slug = (
                        author_raw.get("id")
                        if isinstance(author_raw, dict) and author_kind == "persona"
                        else None
                    )

                    message_metadata: dict[str, Any] = {
                        "author": author_raw if isinstance(author_raw, dict) else {},
                        "attachments": msg_raw.get("attachments", []),
                        "reactions": msg_raw.get("reactions", {}),
                        "parent_message_id": msg_raw.get("parent_message_id"),
                    }

                    try:
                        await conn.execute(
                            text(
                                "INSERT INTO conversation_messages "
                                "  (id, conversation_id, role, content, persona_slug, "
                                "   model_used, created_at, content_tsv, message_metadata) "
                                "VALUES "
                                "  (:id, :conv_id, :role, :content, :persona_slug, "
                                "   NULL, :created_at, "
                                "   to_tsvector('english', :content), "
                                "   :msg_meta::jsonb) "
                                "ON CONFLICT (id) DO NOTHING"
                            ),
                            {
                                "id": msg_uuid,
                                "conv_id": conv_uuid,
                                "role": role,
                                "content": body_md,
                                "persona_slug": persona_slug,
                                "created_at": msg_created_at,
                                "msg_meta": json.dumps(message_metadata),
                            },
                        )
                    except Exception as exc:
                        logger.error(
                            "backfill: failed to insert msg %s for conv %s: %s",
                            msg_uuid,
                            conv_uuid,
                            exc,
                        )
                        msg_errors += 1

                if msg_errors > 0:
                    logger.warning(
                        "backfill: conv %s inserted with %d message error(s)",
                        conv_uuid,
                        msg_errors,
                    )
                    errors += 1
                    # Still count the conversation as inserted (partial import)
                inserted += 1
                logger.info(
                    "backfill: inserted conv %s (%r) with %d message(s)",
                    conv_uuid,
                    title,
                    len(messages) - msg_errors,
                )
    finally:
        await engine.dispose()

    # ----------------------------------------------------------------- summary
    logger.info(
        "backfill: scanned=%d file_count, inserted=%d conversations, "
        "skipped=%d existing, errors=%d",
        scanned,
        inserted,
        skipped,
        errors,
    )

    # Counter-drift assertion (no-silent-fallback.mdc pattern)
    if inserted + skipped + errors != scanned:
        logger.error(
            "backfill: COUNTER DRIFT — inserted=%d + skipped=%d + errors=%d != scanned=%d",
            inserted,
            skipped,
            errors,
            scanned,
        )
        return 1

    if errors > 0:
        logger.error("backfill: completed with %d errors — review logs above", errors)
        return 1

    if dry_run:
        logger.info("backfill [DRY-RUN]: would have inserted %d conversations", inserted)
    else:
        logger.info("backfill: SUCCESS — %d inserted, %d skipped", inserted, skipped)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill legacy conversation JSON files to Postgres (T1.0d)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be written without committing any changes.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override the data directory containing conversations/ subdir.",
    )
    args = parser.parse_args()

    data_dir = _resolve_data_dir(args.data_dir)
    logger.info("backfill: using data_dir=%s", data_dir)

    exit_code = asyncio.run(_backfill(data_dir, dry_run=args.dry_run))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
