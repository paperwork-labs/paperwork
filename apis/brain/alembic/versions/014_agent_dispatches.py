"""Create agent_dispatches table for PR T-Shirt Sizing cost discipline.

Every Task subagent dispatch is recorded here with its t_shirt_size (derived
from model_used) and estimated/actual cost. Enables cost rollups in Studio UI,
calibration loop, and CI validation.

Revision ID: 014
Revises: 013
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)

_AGENT_DISPATCH_LOG_REL = (
    Path(__file__).resolve().parents[3] / "data" / "agent_dispatch_log.json"
)

_MODEL_TO_SIZE: dict[str, str] = {
    "composer-1.5": "XS",
    "composer-2-fast": "S",
    "gpt-5.5-medium": "M",
    "claude-4.6-sonnet-medium-thinking": "L",
}

_SIZE_COST_CENTS: dict[str, int] = {
    "XS": 10,
    "S": 40,
    "M": 100,
    "L": 300,
    "XL": 0,
}

_OPUS_XL_MODELS = {
    "claude-4.5-opus-high-thinking",
    "claude-4.6-opus-high-thinking",
    "claude-opus-4-7-thinking-xhigh",
    "gpt-5.3-codex",
}

_ALL_ALLOWED_MODELS = (
    ",".join(f"'{m}'" for m in sorted(_MODEL_TO_SIZE.keys()))
    + ","
    + ",".join(f"'{m}'" for m in sorted(_OPUS_XL_MODELS))
)


def upgrade() -> None:
    op.execute(
        f"""
    CREATE TABLE IF NOT EXISTS agent_dispatches (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      organization_id TEXT NOT NULL DEFAULT 'paperwork-labs',
      workstream_id TEXT,
      t_shirt_size TEXT NOT NULL CHECK (t_shirt_size IN ('XS','S','M','L','XL')),
      model_used TEXT NOT NULL CHECK (model_used IN (
        'composer-1.5',
        'composer-2-fast',
        'gpt-5.5-medium',
        'claude-4.6-sonnet-medium-thinking',
        'claude-4.5-opus-high-thinking',
        'claude-4.6-opus-high-thinking',
        'claude-opus-4-7-thinking-xhigh',
        'gpt-5.3-codex'
      )),
      subagent_type TEXT,
      task_summary TEXT,
      branch TEXT,
      pr_number INT,
      pr_url TEXT,
      dispatched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      completed_at TIMESTAMPTZ,
      estimated_cost_cents INT,
      actual_cost_cents INT,
      outcome TEXT NOT NULL DEFAULT 'pending' CHECK (
        outcome IN ('pending','success','failed','blocked','cancelled')
      ),
      dispatched_by TEXT NOT NULL,
      CONSTRAINT no_opus_as_subagent CHECK (
        (dispatched_by != 'subagent') OR (model_used NOT LIKE '%opus%')
      )
    );
    """
    )

    op.execute(
        """
    CREATE INDEX IF NOT EXISTS idx_agent_dispatches_workstream_dispatched_at
      ON agent_dispatches (workstream_id, dispatched_at DESC);
    CREATE INDEX IF NOT EXISTS idx_agent_dispatches_t_shirt_size
      ON agent_dispatches (t_shirt_size);
    CREATE INDEX IF NOT EXISTS idx_agent_dispatches_outcome
      ON agent_dispatches (outcome);
    CREATE INDEX IF NOT EXISTS idx_agent_dispatches_dispatched_at
      ON agent_dispatches (dispatched_at DESC);
    """
    )

    _backfill_from_jsonl()


def _backfill_from_jsonl() -> None:
    """Read agent_dispatch_log.json and insert rows for existing entries."""
    log_path = _AGENT_DISPATCH_LOG_REL
    if not log_path.exists():
        logger.info("014: no agent_dispatch_log.json found, skipping backfill")
        return

    try:
        raw = json.loads(log_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("014: could not read dispatch log for backfill: %s", exc)
        return

    dispatches: list[dict] = raw.get("dispatches", [])
    if not dispatches:
        logger.info("014: dispatch log has no entries, skipping backfill")
        return

    rows: list[dict] = []
    for entry in dispatches:
        model_raw: str = str(entry.get("agent_model", "")).strip()
        if model_raw in _MODEL_TO_SIZE:
            size = _MODEL_TO_SIZE[model_raw]
            model = model_raw
            summary_suffix = ""
        elif "opus" in model_raw.lower():
            size = "XL"
            model = "claude-4.5-opus-high-thinking"
            summary_suffix = " (BACKFILLED, Opus orchestrator)"
        else:
            size = "M"
            model = "gpt-5.5-medium"
            summary_suffix = " (BACKFILLED, unknown size)"

        task_summary = str(entry.get("task_summary", ""))[:500]
        if summary_suffix:
            task_summary = (task_summary + summary_suffix)[:500]

        dispatched_at = entry.get("dispatched_at", "NOW()")

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "workstream_id": entry.get("workstream_id"),
                "t_shirt_size": size,
                "model_used": model,
                "subagent_type": entry.get("subagent_type"),
                "task_summary": task_summary or None,
                "branch": entry.get("branch"),
                "pr_number": entry.get("pr_number"),
                "dispatched_at": dispatched_at,
                "estimated_cost_cents": _SIZE_COST_CENTS.get(size, 100),
                "outcome": "success" if entry.get("outcome", {}).get("merged_at") else "pending",
                "dispatched_by": "backfill-014",
            }
        )

    if not rows:
        return

    connection = op.get_bind()
    for row in rows:
        dispatched_at_expr = (
            f"'{row['dispatched_at']}'" if row["dispatched_at"] != "NOW()" else "NOW()"
        )
        pr_number_expr = str(row["pr_number"]) if row["pr_number"] is not None else "NULL"
        est_cost = str(row["estimated_cost_cents"]) if row["estimated_cost_cents"] is not None else "NULL"

        def _sql_str(val: str | None) -> str:
            if val is None:
                return "NULL"
            escaped = val.replace("'", "''")
            return f"'{escaped}'"

        connection.execute(
            __import__("sqlalchemy").text(
                f"""
                INSERT INTO agent_dispatches
                  (id, workstream_id, t_shirt_size, model_used, subagent_type,
                   task_summary, branch, pr_number, dispatched_at, estimated_cost_cents,
                   outcome, dispatched_by)
                VALUES
                  ('{row["id"]}',
                   {_sql_str(row["workstream_id"])},
                   '{row["t_shirt_size"]}',
                   '{row["model_used"]}',
                   {_sql_str(row["subagent_type"])},
                   {_sql_str(row["task_summary"])},
                   {_sql_str(row["branch"])},
                   {pr_number_expr},
                   {dispatched_at_expr},
                   {est_cost},
                   '{row["outcome"]}',
                   '{row["dispatched_by"]}')
                ON CONFLICT (id) DO NOTHING
                """
            )
        )

    logger.info("014: backfilled %d rows from agent_dispatch_log.json", len(rows))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_dispatches;")
