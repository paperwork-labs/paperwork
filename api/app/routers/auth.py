from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_csrf
from app.models.user import User
from app.rate_limit import limiter
from app.redis import get_redis
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "session"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def _make_response(data: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content={"success": True, "data": data},
        status_code=status_code,
    )


def _set_session_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


def _clear_session_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        path="/",
    )


@router.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    redis = get_redis()
    user, session_token, csrf_token = await auth_service.register(db, redis, data)

    resp = _make_response(
        {
            "user": auth_service.user_to_response(user),
            "csrf_token": csrf_token,
        },
        status_code=201,
    )
    _set_session_cookie(resp, session_token)
    return resp


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    redis = get_redis()
    user, session_token, csrf_token = await auth_service.login(
        db, redis, data.email, data.password
    )

    resp = _make_response(
        {
            "user": auth_service.user_to_response(user),
            "csrf_token": csrf_token,
        }
    )
    _set_session_cookie(resp, session_token)
    return resp


@router.post("/logout")
async def logout(
    _csrf: None = Depends(require_csrf),
    session_token: str | None = Cookie(None, alias="session"),
):
    if session_token:
        redis = get_redis()
        await auth_service.logout(redis, session_token)

    resp = _make_response({"message": "Logged out"})
    _clear_session_cookie(resp)
    return resp


@router.get("/me")
async def me(
    user: User = Depends(get_current_user),
    session_token: str | None = Cookie(None, alias="session"),
):
    redis = get_redis()
    csrf_token = await auth_service.get_csrf_token(redis, session_token or "")
    data: dict = {"user": auth_service.user_to_response(user)}
    if csrf_token:
        data["csrf_token"] = csrf_token
    return _make_response(data)


@router.delete("/account")
async def delete_account(
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session_token: str | None = Cookie(None, alias="session"),
    db: AsyncSession = Depends(get_db),
):
    redis = get_redis()
    await auth_service.delete_account(db, redis, user, session_token or "")

    resp = _make_response({"message": "Account deleted"})
    _clear_session_cookie(resp)
    return resp
