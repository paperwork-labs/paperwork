"""paperwork-auth: Python sidecar for the @paperwork-labs/auth-clerk package.

Provides Clerk JWT verification + a FastAPI dependency suitable for the brain,
filefree, axiomfolio, and any other FastAPI service that needs to authenticate
requests against the same Clerk session that the Next.js apps issue.

Example::

    from fastapi import FastAPI
    from paperwork_auth import require_clerk_user, ClerkUser

    app = FastAPI()

    @app.get("/me")
    async def me(user: ClerkUser = Depends(require_clerk_user())):
        return {"user_id": user.user_id}
"""

from .dependencies import (
    ClerkUser,
    require_clerk_user,
)
from .jwks import (
    ClerkAuthError,
    ClerkJwtConfig,
    verify_clerk_jwt,
)

__all__ = [
    "ClerkAuthError",
    "ClerkJwtConfig",
    "ClerkUser",
    "require_clerk_user",
    "verify_clerk_jwt",
]

__version__ = "0.2.0"
