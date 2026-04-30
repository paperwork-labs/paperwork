"""Cheap-agent dispatch helpers — preflight stamping for agent_dispatch_log (WS-67.B).

medallion: ops

Future: append helpers that write to apis/brain/data/agent_dispatch_log.json can call
``stamp_preflight`` before persisting each dispatch row.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def stamp_preflight(
    dispatch_record: dict[str, Any],
    recall_memory_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mark dispatch record as preflight_consulted=True if a recall_memory call
    occurred in the orchestrator context within the last 5 minutes before dispatch.

    Pass ``recall_memory_calls`` as a list of dicts with optional ``timestamp`` keys
    (timezone-aware :class:`~datetime.datetime` instants, UTC).

    TODO(WS-67): When recall_memory persists invocations to a shared orchestrator context,
    wire that store here so callers do not need to thread an explicit list. Until then,
    callers that pass ``[]`` yield ``preflight_consulted=False`` (honest default per
    no-silent-fallback).
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=5)
    consulted = any(
        call.get("timestamp") is not None and call["timestamp"] >= cutoff
        for call in recall_memory_calls
    )
    dispatch_record["preflight_consulted"] = consulted
    return dispatch_record
