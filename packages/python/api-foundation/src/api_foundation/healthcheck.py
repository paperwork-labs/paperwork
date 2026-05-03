"""Liveness (/healthz) and readiness (/readyz) endpoints."""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import APIRouter, FastAPI
from starlette.responses import JSONResponse

_logger = logging.getLogger(__name__)


def register_healthcheck(
    app: FastAPI,
    *,
    check_db: Callable[[], bool] | None = None,
    check_redis: Callable[[], bool] | None = None,
) -> None:
    """Register ``GET /healthz`` (process alive) and ``GET /readyz`` (dependencies).

    Readiness probes run optional ``check_*`` callbacks. Any raised exception or
    ``False`` result fails the probe; failures are logged (no silent fallbacks)
    before returning HTTP 503.
    """

    router = APIRouter(tags=["health"])

    @router.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "alive"}, status_code=200)

    @router.get("/readyz")
    async def readyz() -> JSONResponse:
        probes: dict[str, bool | str | None] = {}

        checks: tuple[tuple[str, Callable[[], bool] | None], ...] = (
            ("database", check_db),
            ("redis", check_redis),
        )

        for name, checker in checks:
            if checker is None:
                probes[name] = "skipped"
                continue
            try:
                ok = bool(checker())
            except Exception:
                _logger.exception("readiness_probe_failed probe=%s", name)
                probes[name] = False
            else:
                if not ok:
                    _logger.error(
                        "readiness_probe_unhealthy_probe=%s (returned false)",
                        name,
                    )
                probes[name] = ok

        required = ("database", "redis")
        unhealthy = False
        for key in required:
            val = probes.get(key)
            if val == "skipped":
                continue
            if val is not True:
                unhealthy = True
                break

        if unhealthy:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "probes": probes},
            )

        return JSONResponse({"status": "ready", "probes": probes})

    app.include_router(router)
