from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_csrf
from app.models.user import AuthProvider, User
from app.rate_limit import limiter
from app.redis import get_redis
from app.schemas.auth import (
    AppleAuthRequest,
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
)
from app.services import auth_service
from app.services.oauth_service import verify_apple_token, verify_google_token

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
    user, session_token, csrf_token = await auth_service.login(db, redis, data.email, data.password)

    resp = _make_response(
        {
            "user": auth_service.user_to_response(user),
            "csrf_token": csrf_token,
        }
    )
    _set_session_cookie(resp, session_token)
    return resp


@router.post("/google")
@limiter.limit("5/minute")
async def google_auth(
    request: Request,
    data: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    oauth_user = await verify_google_token(data.id_token)
    redis = get_redis()

    user, session_token, csrf_token = await auth_service.social_login(
        db, redis,
        provider=AuthProvider.GOOGLE,
        email=oauth_user.email,
        name=oauth_user.name,
        provider_id=oauth_user.provider_id,
    )

    resp = _make_response(
        {
            "user": auth_service.user_to_response(user),
            "csrf_token": csrf_token,
        }
    )
    _set_session_cookie(resp, session_token)
    return resp


@router.post("/apple")
@limiter.limit("5/minute")
async def apple_auth(
    request: Request,
    data: AppleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    oauth_user = await verify_apple_token(data.id_token, data.user)
    redis = get_redis()

    user, session_token, csrf_token = await auth_service.social_login(
        db, redis,
        provider=AuthProvider.APPLE,
        email=oauth_user.email,
        name=oauth_user.name,
        provider_id=oauth_user.provider_id,
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
