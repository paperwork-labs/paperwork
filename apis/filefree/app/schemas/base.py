from typing import Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None


def success_response(data: object, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content={"success": True, "data": data},
        status_code=status_code,
    )


def error_response(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        content={"success": False, "error": message},
        status_code=status_code,
    )
