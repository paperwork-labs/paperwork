"""Unified success / error JSON envelopes."""

from __future__ import annotations

from typing import Any

from starlette.responses import JSONResponse


def success_response(data: Any, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": data},
    )


def error_response(
    code: str,
    message: str,
    *,
    status_code: int = 400,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message}},
    )
