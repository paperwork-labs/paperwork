from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def get_user_rate_limit_key(request: Request) -> str:
    """Per-user rate limit key. Uses session cookie if present, else IP."""
    session = request.cookies.get("session")
    if session:
        return f"user:{session}"
    return get_remote_address(request)
