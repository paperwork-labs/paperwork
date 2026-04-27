"""Bridge to Agent M task generator. Optional import — safe when not shipped."""

from __future__ import annotations

import importlib
import inspect
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentTaskSpec:
    """Task envelope for rotation / drift / health follow-up (Agent M pipeline)."""

    title: str
    summary: str
    category: str = "secrets"
    metadata: dict[str, Any] = field(default_factory=dict)


async def try_queue_agent_task(spec: AgentTaskSpec) -> uuid.UUID | None:
    """Queue a task via Agent M if available; otherwise log and return None."""
    try:
        mod = importlib.import_module("app.services.agent_task_generator")
        enqueuer = getattr(mod, "enqueue_from_spec", None) or getattr(mod, "file_agent_task", None)
        if callable(enqueuer):
            out = enqueuer(spec)
            if inspect.isawaitable(out):
                return await out  # type: ignore[no-any-return]
            if isinstance(out, uuid.UUID):
                return out
    except ImportError:
        pass
    except Exception:
        logger.exception("Agent M task queue failed for %r", spec.title)
        return None
    logger.info(
        "Agent M not wired; would queue task: %s — %s",
        spec.title,
        spec.summary[:200],
    )
    return None
