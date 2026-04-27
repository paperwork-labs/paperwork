from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.redis import get_redis
from app.services import auth_service
from app.utils.exceptions import ForbiddenError, UnauthorizedError


async def get_current_user(
    _request: Request,
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(None, alias="session"),
) -> User:
    """FastAPI dependency: extract session cookie, resolve to User."""
    if not session_token:
        raise UnauthorizedError("Authentication required")

    redis = get_redis()
    return await auth_service.get_current_user(db, redis, session_token)


async def require_csrf(
    _request: Request,
    x_csrf_token: str | None = Header(None, alias="X-CSRF-Token"),
    session_token: str | None = Cookie(None, alias="session"),
) -> None:
    """FastAPI dependency: validate CSRF token on state-changing requests."""
    if not session_token:
        raise UnauthorizedError("Authentication required")
    if not x_csrf_token:
        raise ForbiddenError("CSRF token required")

    redis = get_redis()
    valid = await auth_service.validate_csrf(redis, session_token, x_csrf_token)
    if not valid:
        raise ForbiddenError("Invalid CSRF token")
