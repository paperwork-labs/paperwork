"""medallion: ops"""

from fastapi import HTTPException, Request, status

from app.config import settings


async def require_session(request: Request) -> str:
    session = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return session
