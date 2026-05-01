"""Lightweight Python adapter for Paperwork Brain error ingestion."""

from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

BrainEnv = Literal["production", "preview"]


@dataclass(frozen=True)
class _Config:
    product: str
    brain_url: str
    brain_token: str
    env: BrainEnv


_config: _Config | None = None


def _brain_env(env: str | None) -> BrainEnv:
    return "production" if env == "production" else "preview"


def init_observability(
    *,
    product: str,
    brain_url: str,
    brain_token: str,
    env: str | None = None,
) -> None:
    """Configure the module-level error capture client."""

    global _config
    _config = _Config(
        product=product,
        brain_url=brain_url.strip().rstrip("/"),
        brain_token=brain_token.strip(),
        env=_brain_env(env),
    )
    if not _config.brain_url or not _config.brain_token:
        logger.error(
            "observability_paperwork initialized without brain_url or brain_token; captures will be dropped"
        )


def capture_error(
    err: BaseException | str,
    context: dict[str, Any] | None = None,
    *,
    product: str | None = None,
    env: str | None = None,
    severity: Literal["error", "warning"] = "error",
) -> bool:
    """POST an error to Brain. Returns False on capture failure and never raises."""

    active = _config
    if active is None:
        logger.error("observability_paperwork is not initialized; dropping captured error")
        return False
    if not active.brain_url or not active.brain_token:
        logger.error("observability_paperwork missing brain_url or brain_token; dropping captured error")
        return False

    if isinstance(err, BaseException):
        message = str(err) or err.__class__.__name__
        stack = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    else:
        message = err
        stack = None

    payload = {
        "product": product or active.product,
        "env": _brain_env(env) if env is not None else active.env,
        "message": message,
        "stack": stack,
        "severity": severity,
        "context": context,
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{active.brain_url}/v1/errors/ingest",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {active.brain_token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=5) as response:
            if response.status >= 400:
                logger.error("Brain error capture failed with HTTP %s", response.status)
                return False
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        logger.error("Brain error capture failed: %s", exc)
        return False
    return True
